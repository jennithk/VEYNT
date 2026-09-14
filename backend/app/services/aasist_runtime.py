from __future__ import annotations

import io
import os
import threading
from pathlib import Path

import torch
import torchaudio


_MODEL = None
_MODEL_LOCK = threading.Lock()


def _model_path() -> Path:
    configured = os.getenv("VEYNT_AASIST_MODEL_PATH")

    if configured:
        path = Path(configured)
        if not path.is_absolute():
            path = Path.cwd() / path
    else:
        path = (
            Path(__file__).resolve().parent
            / "aasist_model"
            / "AASIST.pth"
        )

    return path.resolve()


def _architecture_path() -> Path:
    return (
        Path(__file__).resolve().parent
        / "aasist_model"
        / "AASIST.py"
    )


def _load_model():
    global _MODEL

    if _MODEL is not None:
        return _MODEL

    with _MODEL_LOCK:
        if _MODEL is not None:
            return _MODEL

        model_path = _model_path()
        architecture_path = _architecture_path()

        if not model_path.exists():
            raise RuntimeError(
                f"AASIST checkpoint not found: {model_path}"
            )

        if not architecture_path.exists():
            raise RuntimeError(
                f"AASIST architecture not found: {architecture_path}"
            )

        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "veynt_aasist_architecture",
            str(architecture_path),
        )

        if spec is None or spec.loader is None:
            raise RuntimeError("Could not load AASIST architecture")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        model_config = {
            "nb_samp": 64600,
            "first_conv": 128,
            "filts": [
                70,
                [1, 32],
                [32, 32],
                [32, 64],
                [64, 64],
            ],
            "gat_dims": [64, 32],
            "pool_ratios": [0.5, 0.7, 0.5, 0.5],
            "temperatures": [2.0, 2.0, 100.0, 100.0],
        }

        model = module.Model(model_config)

        checkpoint = torch.load(
            str(model_path),
            map_location="cpu",
            weights_only=True,
        )

        if not isinstance(checkpoint, dict):
            raise RuntimeError(
                "AASIST checkpoint is not a state dictionary"
            )

        missing, unexpected = model.load_state_dict(
            checkpoint,
            strict=False,
        )

        if missing or unexpected:
            raise RuntimeError(
                "AASIST checkpoint does not match the architecture. "
                f"Missing keys: {missing[:5]}; "
                f"Unexpected keys: {unexpected[:5]}"
            )

        model.eval()
        model.to("cpu")

        _MODEL = model

        print("[VEYNT] AASIST model loaded successfully")
        print(f"[VEYNT] AASIST checkpoint: {model_path}")

        return _MODEL


def _decode_audio(audio: bytes) -> tuple[torch.Tensor, int]:
    """
    Decode uploaded audio using PyAV.

    This avoids torchaudio's TorchCodec-dependent load path.
    """
    if not audio:
        raise RuntimeError("Audio data is empty")

    try:
        import av
    except ImportError as exc:
        raise RuntimeError(
            "PyAV is required for audio decoding. "
            "Install it with: python -m pip install av"
        ) from exc

    try:
        container = av.open(io.BytesIO(audio))
        stream = container.streams.audio[0]

        frames = []
        for frame in container.decode(stream):
            frames.append(frame.to_ndarray())

        if not frames:
            raise RuntimeError("No audio frames were decoded")

        import numpy as np

        samples = np.concatenate(frames, axis=1)

        # Convert to mono.
        if samples.ndim == 2:
            samples = samples.mean(axis=0)

        waveform = torch.from_numpy(samples.astype("float32"))

        # Normalize integer-like audio if necessary.
        if waveform.abs().max() > 1.5:
            waveform = waveform / 32768.0

        return waveform.unsqueeze(0), int(stream.rate)

    except Exception as exc:
        raise RuntimeError(
            f"Audio decoding failed: {exc}"
        ) from exc


def _prepare_waveform(audio: bytes) -> torch.Tensor:
    """
    Convert audio to mono, resample to 16 kHz,
    and deterministically crop/pad to 64600 samples.
    """
    waveform, sample_rate = _decode_audio(audio)

    # Convert stereo/multichannel audio to mono.
    waveform = waveform.mean(dim=0, keepdim=True)

    # AASIST expects 16 kHz audio.
    if sample_rate != 16000:
        waveform = torchaudio.functional.resample(
            waveform,
            sample_rate,
            16000,
        )

    waveform = waveform.squeeze(0).float()

    target_length = 64600

    if waveform.numel() >= target_length:
        waveform = waveform[:target_length]
    else:
        padding = target_length - waveform.numel()
        waveform = torch.nn.functional.pad(
            waveform,
            (0, padding),
        )

    # Shape: [batch, samples]
    return waveform.unsqueeze(0)


def run_aasist(audio: bytes) -> dict:
    """
    Run official AASIST inference.

    AASIST output index 1 is the bona-fide class
    in the official ASVspoof training/evaluation setup.

    Therefore:
        spoof_probability = 1 - bona_fide_probability
    """
    model = _load_model()
    waveform = _prepare_waveform(audio)

    with torch.inference_mode():
        _, logits = model(waveform)

        probabilities = torch.softmax(logits, dim=1)[0]

        bona_fide_probability = float(probabilities[1].item())
        spoof_probability = float(probabilities[0].item())

    spoof_percent = round(spoof_probability * 100.0, 2)
    confidence_percent = round(
        max(bona_fide_probability, spoof_probability) * 100.0,
        2,
    )

    if spoof_percent >= 70:
        classification = "HIGH"
    elif spoof_percent >= 40:
        classification = "MEDIUM"
    else:
        classification = "LOW"

    return {
        "classification": classification,
        "ai_probability": spoof_percent,
        "confidence": confidence_percent,
        "signals": [
            "Official AASIST anti-spoofing model evaluated the audio",
            f"AASIST spoof probability: {spoof_percent}%",
            f"AASIST bona-fide probability: {round(bona_fide_probability * 100, 2)}%",
        ],
        "model_version": "AASIST-ASVspoof2019-LA",
        "bona_fide_probability": round(
            bona_fide_probability * 100.0,
            2,
        ),
        "spoof_probability": spoof_percent,
    }