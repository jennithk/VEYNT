from __future__ import annotations

import io
import os
import threading

import httpx
from dataclasses import dataclass
from typing import Protocol


SUPPORTED_LANGUAGES = {"en": "English", "hi": "Hindi", "te": "Telugu"}


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
    def transcribe(self, audio: bytes, language: str) -> TranscriptionResult: ...


class VoiceAuthenticityService(Protocol):
    def analyze(self, audio: bytes, language: str) -> AuthenticityResult: ...


@dataclass(frozen=True)
class SpeakerVerificationResult:
    status: str
    similarity: float | None
    confidence: float | None
    provider: str


class SpeakerVerificationService(Protocol):
    def compare(self, reference_audio: bytes, test_audio: bytes) -> SpeakerVerificationResult: ...


class UnconfiguredSpeechToText:
    def transcribe(self, audio: bytes, language: str) -> TranscriptionResult:
        raise RuntimeError("Speech-to-text provider is not configured")


class UnconfiguredVoiceAuthenticity:
    def analyze(self, audio: bytes, language: str) -> AuthenticityResult:
        raise RuntimeError("Voice authenticity provider is not configured")


class UnconfiguredSpeakerVerification:
    def compare(self, reference_audio: bytes, test_audio: bytes) -> SpeakerVerificationResult:
        raise RuntimeError("Speaker verification provider is not configured")


class LocalAasistAuthenticity:
    def analyze(self, audio: bytes, language: str) -> AuthenticityResult:
        checkpoint = os.getenv("VEYNT_AUTHENTICITY_MODEL_PATH", "")
        if not checkpoint:
            raise RuntimeError("Set VEYNT_AUTHENTICITY_MODEL_PATH to an official AASIST checkpoint")
        raise RuntimeError("The configured AASIST checkpoint needs a model adapter before it can be used")


class LocalSpeakerVerification:
    _model = None
    _lock = threading.Lock()

    def _encoder(self):
        with self._lock:
            if self._model is None:
                try:
                    import torchaudio

                    if not hasattr(torchaudio, "list_audio_backends"):
                        torchaudio.list_audio_backends = lambda: ["soundfile"]
                    from speechbrain.utils.fetching import LocalStrategy
                    from speechbrain.inference.speaker import EncoderClassifier
                except ImportError as exc:
                    raise RuntimeError("Install speechbrain to use local speaker verification") from exc
                self._model = EncoderClassifier.from_hparams(
                    source=os.getenv("VEYNT_SPEAKER_MODEL", "speechbrain/spkrec-ecapa-voxceleb"),
                    savedir=os.getenv("VEYNT_SPEAKER_MODEL_DIR", "pretrained_models/spkrec-ecapa-voxceleb"),
                    local_strategy=LocalStrategy.COPY,
                )
            return self._model

    def compare(self, reference_audio: bytes, test_audio: bytes) -> SpeakerVerificationResult:
        try:
            import av
            import numpy as np
            import torch

            def embedding(audio_bytes):
                container = av.open(io.BytesIO(audio_bytes))
                resampler = av.audio.resampler.AudioResampler(format="fltp", layout="mono", rate=16000)
                chunks = []
                for frame in container.decode(audio=0):
                    chunks.extend(resampler.resample(frame))
                samples = [frame.to_ndarray() for frame in chunks]
                if not samples:
                    raise RuntimeError("The recording contains no decodable audio")
                waveform = torch.from_numpy(np.concatenate(samples, axis=1)).float()
                with torch.no_grad():
                    return self._encoder().encode_batch(waveform)

            reference_embedding = embedding(reference_audio)
            test_embedding = embedding(test_audio)
            similarity = float(torch.nn.functional.cosine_similarity(reference_embedding.flatten(), test_embedding.flatten(), dim=0).item())
            similarity_percent = round(max(0.0, min(1.0, (similarity + 1) / 2)) * 100, 1)
            threshold = float(os.getenv("VEYNT_SPEAKER_MATCH_THRESHOLD", "70"))
            status = "MATCH" if similarity_percent >= threshold else "NO_MATCH"
            return SpeakerVerificationResult(status, similarity_percent, similarity_percent, "speechbrain-ecapa")
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError(f"Local speaker verification failed: {exc}") from exc


class OpenAISpeechToText:
    def __init__(self):
        self.api_key = os.environ["VEYNT_STT_API_KEY"]
        self.url = os.getenv("VEYNT_STT_URL", "https://api.openai.com/v1/audio/transcriptions")
        self.model = os.getenv("VEYNT_STT_MODEL", "whisper-1")

    def transcribe(self, audio: bytes, language: str) -> TranscriptionResult:
        data = {"model": self.model, "response_format": "verbose_json", "temperature": "0"}
        if language != "auto":
            data["language"] = language
        response = httpx.post(self.url, headers={"Authorization": f"Bearer {self.api_key}"}, files={"file": ("recording.wav", audio, "application/octet-stream")}, data=data, timeout=120)
        response.raise_for_status()
        body = response.json()
        segments = [TranscriptSegment(float(item.get("start", 0)), float(item.get("end", 0)), item.get("text", "").strip()) for item in body.get("segments", [])]
        return TranscriptionResult(body.get("text", "").strip(), body.get("language", language), body.get("confidence"), segments)


class LocalWhisperSpeechToText:
    _models = {}
    _lock = threading.Lock()

    def __init__(self):
        self.model_name = os.getenv("VEYNT_STT_MODEL", "tiny")
        self.device = os.getenv("VEYNT_STT_DEVICE", "cpu")
        self.compute_type = os.getenv("VEYNT_STT_COMPUTE_TYPE", "int8")

    def _model(self):
        key = (self.model_name, self.device, self.compute_type)
        with self._lock:
            if key not in self._models:
                try:
                    from faster_whisper import WhisperModel
                except ImportError as exc:
                    raise RuntimeError(f"Local speech-to-text dependencies are unavailable: {exc}") from exc
                self._models[key] = WhisperModel(self.model_name, device=self.device, compute_type=self.compute_type)
            return self._models[key]

    def transcribe(self, audio: bytes, language: str) -> TranscriptionResult:
        options = {"beam_size": 5}
        if language != "auto":
            options["language"] = language
        try:
            segments, info = self._model().transcribe(io.BytesIO(audio), **options)
            materialized = [TranscriptSegment(float(item.start), float(item.end), item.text.strip()) for item in segments]
        except Exception as exc:
            raise RuntimeError(f"Local speech-to-text failed: {exc}") from exc
        return TranscriptionResult(
            " ".join(segment.text for segment in materialized).strip(),
            info.language,
            getattr(info, "language_probability", None),
            materialized,
        )


class HttpAuthenticityService:
    def __init__(self):
        self.url = os.environ["VEYNT_AUTHENTICITY_URL"]
        self.api_key = os.environ.get("VEYNT_AUTHENTICITY_API_KEY")

    def analyze(self, audio: bytes, language: str) -> AuthenticityResult:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        response = httpx.post(self.url, headers=headers, files={"audio": ("recording.bin", audio, "application/octet-stream")}, data={"language": language}, timeout=180)
        response.raise_for_status()
        body = response.json()
        return AuthenticityResult(body["classification"], body.get("ai_probability"), body.get("confidence"), body.get("signals", []), body.get("model_version", "provider"))


class HttpSpeakerVerification:
    def __init__(self):
        self.url = os.environ["VEYNT_SPEAKER_URL"]
        self.api_key = os.environ.get("VEYNT_SPEAKER_API_KEY")

    def compare(self, reference_audio: bytes, test_audio: bytes) -> SpeakerVerificationResult:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        response = httpx.post(self.url, headers=headers, files={"reference": ("reference.bin", reference_audio), "test": ("test.bin", test_audio)}, timeout=180)
        response.raise_for_status()
        body = response.json()
        return SpeakerVerificationResult(body["status"], body.get("similarity"), body.get("confidence"), body.get("provider", "provider"))


def build_speech_to_text() -> SpeechToTextService:
    provider = os.getenv("VEYNT_STT_PROVIDER", "none").lower()
    if provider == "openai":
        return OpenAISpeechToText()
    if provider == "local":
        return LocalWhisperSpeechToText()
    if provider == "none":
        return UnconfiguredSpeechToText()
    raise RuntimeError(f"Unsupported STT provider: {provider}")


def build_authenticity_service() -> VoiceAuthenticityService:
    provider = os.getenv("VEYNT_AUTHENTICITY_PROVIDER", "none").lower()
    if provider == "http":
        return HttpAuthenticityService()
    if provider == "local_aasist":
        return LocalAasistAuthenticity()
    if provider == "none":
        return UnconfiguredVoiceAuthenticity()
    raise RuntimeError(f"Unsupported authenticity provider: {provider}")


def build_speaker_verification() -> SpeakerVerificationService:
    provider = os.getenv("VEYNT_SPEAKER_PROVIDER", "none").lower()
    if provider == "http":
        return HttpSpeakerVerification()
    if provider == "local":
        return LocalSpeakerVerification()
    if provider == "none":
        return UnconfiguredSpeakerVerification()
    raise RuntimeError(f"Unsupported speaker provider: {provider}")