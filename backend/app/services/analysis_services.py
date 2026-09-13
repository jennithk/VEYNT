from __future__ import annotations

import os
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
    if provider == "none":
        return UnconfiguredSpeechToText()
    raise RuntimeError(f"Unsupported STT provider: {provider}")


def build_authenticity_service() -> VoiceAuthenticityService:
    provider = os.getenv("VEYNT_AUTHENTICITY_PROVIDER", "none").lower()
    if provider == "http":
        return HttpAuthenticityService()
    if provider == "none":
        return UnconfiguredVoiceAuthenticity()
    raise RuntimeError(f"Unsupported authenticity provider: {provider}")


def build_speaker_verification() -> SpeakerVerificationService:
    provider = os.getenv("VEYNT_SPEAKER_PROVIDER", "none").lower()
    if provider == "http":
        return HttpSpeakerVerification()
    if provider == "none":
        return UnconfiguredSpeakerVerification()
    raise RuntimeError(f"Unsupported speaker provider: {provider}")