from __future__ import annotations

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
    def transcribe(self, audio: bytes, language: str) -> TranscriptionResult:
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
    ) -> SpeakerVerificationResult:
        raise RuntimeError(
            "Speaker verification provider is not configured"
        )


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
    ) -> TranscriptionResult:

        if not audio:
            raise RuntimeError(
                "Audio data is empty"
            )

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

            if language in {"en", "hi", "te"}:
                whisper_language = language

            segments_iterator, info = model.transcribe(
                temporary_path,
                language=whisper_language,
                beam_size=5,
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

            return TranscriptionResult(
                text=transcript_text,
                language=detected_language or language,
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

    if provider == "http":
        return HttpSpeakerVerification()

    if provider == "none":
        return UnconfiguredSpeakerVerification()

    raise RuntimeError(
        f"Unsupported speaker provider: {provider}"
    )