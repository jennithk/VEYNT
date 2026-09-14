from __future__ import annotations

import io
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import httpx


SUPPORTED_LANGUAGES = {
    "en": "English",
    "hi": "Hindi",
    "te": "Telugu",
}


def _normalize_detected_language(language: str, transcript: str) -> str:
    if any("\u0c00" <= character <= "\u0c7f" for character in transcript):
        return "te"
    if any("\u0900" <= character <= "\u097f" for character in transcript):
        return "hi"
    return language


@dataclass(frozen=True)
class TranscriptSegment:
    start: float
    end: float
    text: str


@dataclass(frozen=True)
class TranscriptionResult:
    text: str
    language: str
    confidence: float | None
    segments: list[TranscriptSegment]


@dataclass(frozen=True)
class AuthenticityResult:
    classification: str
    ai_probability: float | None
    confidence: float | None
    signals: list[str]
    model_version: str


class SpeechToTextService(Protocol):
    def transcribe(
        self,
        audio: bytes,
        language: str,
        filename: str | None = None,
    ) -> TranscriptionResult:
        ...


class VoiceAuthenticityService(Protocol):
    def analyze(self, audio: bytes, language: str) -> AuthenticityResult:
        ...


@dataclass(frozen=True)
class SpeakerVerificationResult:
    status: str
    similarity: float | None
    confidence: float | None
    provider: str


class SpeakerVerificationService(Protocol):
    def compare(
        self,
        reference_audio: bytes,
        test_audio: bytes,
        reference_filename: str | None = None,
        test_filename: str | None = None,
    ) -> SpeakerVerificationResult:
        ...


# ============================================================
# UNCONFIGURED SERVICES
# ============================================================

class UnconfiguredSpeechToText:
    def transcribe(
        self,
        audio: bytes,
        language: str,
        filename: str | None = None,
    ) -> TranscriptionResult:
        raise RuntimeError(
            "Speech-to-text provider is not configured"
        )


class UnconfiguredVoiceAuthenticity:
    def analyze(
        self,
        audio: bytes,
        language: str,
    ) -> AuthenticityResult:
        raise RuntimeError(
            "AI-voice authenticity provider is not configured"
        )


class UnconfiguredSpeakerVerification:
    def compare(
        self,
        reference_audio: bytes,
        test_audio: bytes,
        reference_filename: str | None = None,
        test_filename: str | None = None,
    ) -> SpeakerVerificationResult:
        raise RuntimeError(
            "Speaker verification provider is not configured"
        )


def _ensure_torchaudio_compatibility() -> None:
    if os.name == "nt" and hasattr(os, "add_dll_directory"):
        dll_candidates = [
            Path(os.getenv("VEYNT_FFMPEG_BIN", "")),
            Path(r"C:\Program Files\FFmpeg\bin"),
            Path(os.getenv("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages",
        ]
        for candidate in dll_candidates:
            if candidate.name == "Packages":
                candidate = next(
                    candidate.glob("Gyan.FFmpeg.Shared_*/*/bin"),
                    Path(),
                )
            if candidate.is_dir() and any(candidate.glob("avcodec-*.dll")):
                os.add_dll_directory(str(candidate))
                break

    try:
        import torchaudio
    except Exception:
        return

    if not hasattr(torchaudio, "list_audio_backends"):
        torchaudio.list_audio_backends = lambda: ["soundfile"]


# ============================================================
# LOCAL WHISPER SPEECH-TO-TEXT
# ============================================================

class LocalWhisperSpeechToText:
    """
    Local speech-to-text using faster-whisper.

    This class performs transcription only.
    It is NOT an AI-voice detector.
    """

    def __init__(self):
        self.model_name = os.getenv(
            "VEYNT_STT_MODEL",
            "small",
        )

        self.device = os.getenv(
            "VEYNT_STT_DEVICE",
            "cpu",
        )

        self.compute_type = os.getenv(
            "VEYNT_STT_COMPUTE_TYPE",
            "int8",
        )

        self._model = None

    def _get_model(self):
        if self._model is None:
            try:
                from faster_whisper import WhisperModel
            except ImportError as exc:
                raise RuntimeError(
                    "faster-whisper is not installed"
                ) from exc

            print(
                f"[VEYNT] Loading Whisper model: "
                f"{self.model_name}"
            )

            self._model = WhisperModel(
                self.model_name,
                device=self.device,
                compute_type=self.compute_type,
            )

            print("[VEYNT] Whisper model loaded")

        return self._model

    def transcribe(
        self,
        audio: bytes,
        language: str,
        filename: str | None = None,
    ) -> TranscriptionResult:

        if not audio:
            raise RuntimeError(
                "Audio data is empty"
            )

        suffix = Path(filename or "recording.wav").suffix.lower()
        if suffix not in {".aac", ".m4a", ".mp3", ".wav", ".webm"}:
            suffix = ".wav"

        with tempfile.NamedTemporaryFile(
            suffix=suffix,
            delete=False,
        ) as temporary_file:
            temporary_file.write(audio)
            temporary_path = temporary_file.name

        try:
            model = self._get_model()

            whisper_language = None
            initial_prompt = None

            if language in {"en", "hi", "te"}:
                whisper_language = language
                if language == "te":
                    initial_prompt = "ఇది తెలుగు భాషలో మాట్లాడిన మాటలు."

            segments_iterator, info = model.transcribe(
                temporary_path,
                language=whisper_language,
                task="transcribe",
                beam_size=5,
                temperature=0.0,
                condition_on_previous_text=False,
                initial_prompt=initial_prompt,
                vad_filter=True,
            )

            segments = []
            text_parts = []

            for segment in segments_iterator:
                segment_text = segment.text.strip()

                if segment_text:
                    text_parts.append(segment_text)

                segments.append(
                    TranscriptSegment(
                        start=float(segment.start),
                        end=float(segment.end),
                        text=segment_text,
                    )
                )

            transcript_text = " ".join(text_parts).strip()

            detected_language = getattr(
                info,
                "language",
                language,
            )

            language_probability = getattr(
                info,
                "language_probability",
                None,
            )

            if language in {"en", "hi", "te"}:
                detected_language = language
            else:
                detected_language = _normalize_detected_language(
                    detected_language or language,
                    transcript_text,
                )

            return TranscriptionResult(
                text=transcript_text,
                language=detected_language,
                confidence=(
                    float(language_probability)
                    if language_probability is not None
                    else None
                ),
                segments=segments,
            )

        except Exception as exc:
            raise RuntimeError(
                f"Local Whisper transcription failed: {exc}"
            ) from exc

        finally:
            try:
                Path(temporary_path).unlink(
                    missing_ok=True
                )
            except Exception:
                pass


# ============================================================
# LOCAL AASIST AUTHENTICITY SERVICE
# ============================================================

class LocalAASISTAuthenticity:
    """
    Local AASIST anti-spoofing inference service.

    Uses the official AASIST architecture and checkpoint.
    This is an anti-spoofing model, not a general-purpose
    detector for every possible AI voice generator.
    """

    def analyze(self, audio: bytes, language: str) -> AuthenticityResult:
        from app.services.aasist_runtime import run_aasist

        result = run_aasist(audio)

        return AuthenticityResult(
            classification=result["classification"],
            ai_probability=result["ai_probability"],
            confidence=result["confidence"],
            signals=result["signals"],
            model_version=result["model_version"],
        )


# ============================================================
# HTTP AUTHENTICITY SERVICE
# ============================================================

class HttpAuthenticityService:
    """
    Calls an external AI-voice detection provider.

    The provider must return a genuine model prediction.
    """

    def __init__(self):
        self.url = os.environ[
            "VEYNT_AUTHENTICITY_URL"
        ]

        self.api_key = os.environ.get(
            "VEYNT_AUTHENTICITY_API_KEY"
        )

    def analyze(
        self,
        audio: bytes,
        language: str,
    ) -> AuthenticityResult:

        headers = {}

        if self.api_key:
            headers["Authorization"] = (
                f"Bearer {self.api_key}"
            )

        response = httpx.post(
            self.url,
            headers=headers,
            files={
                "audio": (
                    "recording.bin",
                    audio,
                    "application/octet-stream",
                )
            },
            data={
                "language": language,
            },
            timeout=180,
        )

        response.raise_for_status()

        body = response.json()

        return AuthenticityResult(
            classification=body["classification"],
            ai_probability=body.get(
                "ai_probability"
            ),
            confidence=body.get(
                "confidence"
            ),
            signals=body.get(
                "signals",
                [],
            ),
            model_version=body.get(
                "model_version",
                "external-provider",
            ),
        )


# ============================================================
# LOCAL SPEAKER VERIFICATION
# ============================================================

class LocalSpeakerVerification:
    def __init__(self):
        self.model_ref = os.getenv(
            "VEYNT_SPEAKER_MODEL",
            "speechbrain/spkrec-ecapa-voxceleb",
        )
        self.match_threshold = float(
            os.getenv("VEYNT_SPEAKER_MATCH_THRESHOLD", "70")
        ) / 100.0
        self._model = None

    def _resolve_model_source(self) -> Path:
        model_ref = self.model_ref.strip()
        if model_ref and os.path.exists(model_ref):
            return Path(model_ref).resolve()

        local_candidates = [
            Path(__file__).resolve().parents[2] / "pretrained_models" / "spkrec-ecapa-voxceleb",
            Path(__file__).resolve().parents[2] / "pretrained_models" / (Path(model_ref).name or "spkrec-ecapa-voxceleb"),
        ]

        for candidate in local_candidates:
            if candidate.exists():
                return candidate

        return Path(__file__).resolve().parents[2] / "pretrained_models" / "spkrec-ecapa-voxceleb"

    def _get_model(self):
        if self._model is not None:
            return self._model

        _ensure_torchaudio_compatibility()

        try:
            from speechbrain.inference.speaker import SpeakerRecognition
        except Exception as exc:
            raise RuntimeError(
                "Local speech verification model is not available. Install SpeechBrain and its audio backend compatibility."
            ) from exc

        model_source = self._resolve_model_source()
        model_path = Path(model_source)
        local_model_ready = (model_path / "hyperparams.yaml").exists()
        source = str(model_path) if local_model_ready else self.model_ref
        savedir = (
            str(model_path)
            if local_model_ready
            else str(Path(__file__).resolve().parents[2] / "pretrained_models" / Path(self.model_ref).name)
        )

        print(f"[VEYNT] Loading speaker verification model from: {model_source}")

        try:
            from speechbrain.utils.fetching import LocalStrategy

            self._model = SpeakerRecognition.from_hparams(
                source=source,
                savedir=savedir,
                hparams_file="hyperparams.yaml",
                local_strategy=LocalStrategy.COPY,
            )
        except Exception as exc:
            raise RuntimeError(
                f"Speaker verification model failed to load from {model_source}: {exc}"
            ) from exc

        return self._model

    def compare(
        self,
        reference_audio: bytes,
        test_audio: bytes,
        reference_filename: str | None = None,
        test_filename: str | None = None,
    ) -> SpeakerVerificationResult:
        if not reference_audio or not test_audio:
            raise RuntimeError("Both reference and test audio are required for speaker verification.")

        model = self._get_model()

        reference_suffix = Path(reference_filename or "reference.wav").suffix.lower()
        test_suffix = Path(test_filename or "test.wav").suffix.lower()
        supported_suffixes = {".aac", ".m4a", ".mp3", ".wav", ".webm"}
        if reference_suffix not in supported_suffixes:
            reference_suffix = ".wav"
        if test_suffix not in supported_suffixes:
            test_suffix = ".wav"

        with tempfile.NamedTemporaryFile(suffix=reference_suffix, delete=False) as reference_file, tempfile.NamedTemporaryFile(suffix=test_suffix, delete=False) as test_file:
            reference_file.write(reference_audio)
            test_file.write(test_audio)
            reference_path = reference_file.name
            test_path = test_file.name

        try:
            import av
            import numpy as np
            import torch
            import torchaudio

            def decode(path):
                with av.open(path) as container:
                    stream = container.streams.audio[0]
                    frames = [
                        frame.to_ndarray()
                        for frame in container.decode(stream)
                    ]

                if not frames:
                    raise RuntimeError("No audio frames were decoded")

                normalized_frames = [
                    frame[np.newaxis, :] if frame.ndim == 1 else frame
                    for frame in frames
                ]
                samples = np.concatenate(normalized_frames, axis=1)
                samples = samples.astype("float32")
                if np.max(np.abs(samples)) > 1.5:
                    samples /= 32768.0
                return torch.from_numpy(samples), int(stream.rate)

            reference_waveform, reference_rate = decode(reference_path)
            test_waveform, test_rate = decode(test_path)

            if reference_waveform.ndim == 2:
                reference_waveform = reference_waveform.mean(dim=0)
            if test_waveform.ndim == 2:
                test_waveform = test_waveform.mean(dim=0)

            if reference_rate != 16000:
                reference_waveform = torchaudio.functional.resample(reference_waveform, reference_rate, 16000)
            if test_rate != 16000:
                test_waveform = torchaudio.functional.resample(test_waveform, test_rate, 16000)

            batch_x = reference_waveform.unsqueeze(0)
            batch_y = test_waveform.unsqueeze(0)

            emb1 = model.encode_batch(batch_x, normalize=False)
            emb2 = model.encode_batch(batch_y, normalize=False)
            score = model.similarity(emb1, emb2)

            if hasattr(score, "item"):
                score = score.item()
            score = float(score)

            similarity = max(0.0, min(1.0, (score + 1.0) / 2.0))
            status = "MATCH" if similarity >= self.match_threshold else "NO_MATCH"
            confidence = similarity

            return SpeakerVerificationResult(
                status=status,
                similarity=similarity,
                confidence=confidence,
                provider="local_speechbrain",
            )
        finally:
            for path in (reference_path, test_path):
                try:
                    Path(path).unlink(missing_ok=True)
                except Exception:
                    pass


# ============================================================
# HTTP SPEAKER VERIFICATION
# ============================================================

class HttpSpeakerVerification:
    def __init__(self):
        self.url = os.environ[
            "VEYNT_SPEAKER_URL"
        ]

        self.api_key = os.environ.get(
            "VEYNT_SPEAKER_API_KEY"
        )

    def compare(
        self,
        reference_audio: bytes,
        test_audio: bytes,
        reference_filename: str | None = None,
        test_filename: str | None = None,
    ) -> SpeakerVerificationResult:

        headers = {}

        if self.api_key:
            headers["Authorization"] = (
                f"Bearer {self.api_key}"
            )

        response = httpx.post(
            self.url,
            headers=headers,
            files={
                "reference": (
                    "reference.bin",
                    reference_audio,
                ),
                "test": (
                    "test.bin",
                    test_audio,
                ),
            },
            timeout=180,
        )

        response.raise_for_status()

        body = response.json()

        return SpeakerVerificationResult(
            status=body["status"],
            similarity=body.get(
                "similarity"
            ),
            confidence=body.get(
                "confidence"
            ),
            provider=body.get(
                "provider",
                "provider",
            ),
        )


# ============================================================
# SERVICE BUILDERS
# ============================================================

def build_speech_to_text() -> SpeechToTextService:
    provider = os.getenv(
        "VEYNT_STT_PROVIDER",
        "none",
    ).lower()

    if provider == "local":
        return LocalWhisperSpeechToText()

    if provider == "openai":
        raise RuntimeError(
            "OpenAI STT adapter is not enabled "
            "in this version."
        )

    if provider == "none":
        return UnconfiguredSpeechToText()

    raise RuntimeError(
        f"Unsupported STT provider: {provider}"
    )


def build_authenticity_service() -> VoiceAuthenticityService:
    provider = os.getenv(
        "VEYNT_AUTHENTICITY_PROVIDER",
        "none",
    ).lower()

    if provider == "local_aasist":
        return LocalAASISTAuthenticity()

    if provider == "http":
        return HttpAuthenticityService()

    if provider == "none":
        return UnconfiguredVoiceAuthenticity()

    raise RuntimeError(
        f"Unsupported authenticity provider: {provider}"
    )


def build_speaker_verification() -> SpeakerVerificationService:
    provider = os.getenv(
        "VEYNT_SPEAKER_PROVIDER",
        "none",
    ).lower()

    if provider == "local":
        return LocalSpeakerVerification()

    if provider == "http":
        return HttpSpeakerVerification()

    if provider == "none":
        return UnconfiguredSpeakerVerification()

    raise RuntimeError(
        f"Unsupported speaker provider: {provider}"
    )