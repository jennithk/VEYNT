from __future__ import annotations

import io
import wave
from dataclasses import dataclass


SUPPORTED_CONTENT_TYPES = {
    "audio/aac",
    "audio/mp4",
    "audio/m4a",
    "audio/mpeg",
    "audio/wav",
    "audio/webm",
    "audio/x-m4a",
    "audio/x-wav",
}
MAX_AUDIO_BYTES = 25 * 1024 * 1024
MIN_DURATION_SECONDS = 1.0
MAX_DURATION_SECONDS = 15 * 60


@dataclass(frozen=True)
class AudioMetadata:
    duration_seconds: float
    sample_rate: int | None
    channels: int | None
    quality: str


class AudioValidationError(ValueError):
    pass


def validate_audio(content: bytes, content_type: str | None, filename: str | None) -> AudioMetadata:
    if not content:
        raise AudioValidationError("The audio file is empty. Choose a recording with speech and try again.")
    if len(content) > MAX_AUDIO_BYTES:
        raise AudioValidationError("The audio file is larger than 25 MB. Choose a shorter recording.")

    extension = (filename or "").lower().rsplit(".", 1)[-1]
    if content_type not in SUPPORTED_CONTENT_TYPES and extension not in {"aac", "m4a", "mp3", "wav", "webm"}:
        raise AudioValidationError("Unsupported audio format. Use WAV, MP3, M4A, AAC, or WebM.")

    metadata = _read_wav_metadata(content)
    if metadata and metadata.duration_seconds < MIN_DURATION_SECONDS:
        raise AudioValidationError("The recording is too short. Record at least one second of audio.")
    if metadata and metadata.duration_seconds > MAX_DURATION_SECONDS:
        raise AudioValidationError("The recording is longer than 15 minutes. Choose a shorter recording.")
    return metadata or AudioMetadata(0.0, None, None, "unknown")


def _read_wav_metadata(content: bytes) -> AudioMetadata | None:
    try:
        with wave.open(io.BytesIO(content), "rb") as wav_file:
            frames = wav_file.getnframes()
            sample_rate = wav_file.getframerate()
            duration = frames / sample_rate if sample_rate else 0.0
            quality = "poor" if sample_rate < 16000 or wav_file.getnchannels() < 1 else "good"
            return AudioMetadata(duration, sample_rate, wav_file.getnchannels(), quality)
    except (wave.Error, EOFError):
        return None