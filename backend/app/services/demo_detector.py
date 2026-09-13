"""Demo-only AI voice detection adapter.

This module intentionally exposes a clearly labeled demo detector so the
surrounding detection pipeline can work without pretending to have a trained
model.
"""

from __future__ import annotations

from typing import Dict, List


class DemoVoiceDetector:
    """Synthetic detector used for prototype demonstration only."""

    def analyze(self, audio_features: Dict | None = None) -> Dict:
        """Return a demo probabilistic score and a structured explanation.

        The score is meant for simulation purposes only and should be replaced by
        a trained detector in a later phase.
        """
        feature_payload = audio_features or {}
        base_probability = float(feature_payload.get("synthetic_score", 0.18))
        adjusted_probability = min(max(base_probability, 0.0), 0.99)

        return {
            "detector": "demo_only",
            "ai_generated_probability": round(adjusted_probability * 100, 1),
            "confidence": "demo_only",
            "explanations": [
                "Demo-only synthetic voice adapter active",
                "Model replacement required before production evaluation",
            ],
        }


def build_demo_detector() -> DemoVoiceDetector:
    return DemoVoiceDetector()
