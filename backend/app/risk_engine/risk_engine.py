from __future__ import annotations

from app.services.analysis_services import AuthenticityResult, TranscriptionResult


def classify_risk(score: float) -> str:
    if score < 40:
        return "LOW"
    if score < 70:
        return "MEDIUM"
    return "HIGH"


def compute_risk(ai_voice_probability: float, speaker_match: float, context_risk: float) -> dict:
    """Combine audio, speaker, and context evidence into an overall risk score.

    The weights are prototype-configurable and intentionally transparent.
    """
    weighted_score = (
        (ai_voice_probability * 0.5)
        + ((100 - speaker_match) * 0.25)
        + (context_risk * 0.25)
    )

    overall_risk_score = round(min(100, max(0, weighted_score)))
    classification = classify_risk(overall_risk_score)

    if classification == "LOW":
        recommended_action = "CONTINUE"
    elif classification == "MEDIUM":
        recommended_action = "ADDITIONAL VERIFICATION REQUIRED"
    else:
        recommended_action = "DO NOT AUTHORIZE"

    return {
        "overall_risk_score": overall_risk_score,
        "classification": classification,
        "recommended_action": recommended_action,
        "input_summary": {
            "ai_voice_probability": ai_voice_probability,
            "speaker_match": speaker_match,
            "context_risk": context_risk,
        },
    }


def compute_evidence_risk(
    authenticity: AuthenticityResult,
    transcript: TranscriptionResult,
) -> dict:
    """
    Compute risk only when genuine independent evidence exists.

    A transcript alone cannot establish whether a voice is
    AI-generated. Missing model output must remain inconclusive.
    """

    if not transcript.text.strip():
        return {
            "level": "INCONCLUSIVE",
            "reasons": [
                "No speech transcript was produced"
            ],
        }

    if authenticity.ai_probability is None:
        return {
            "level": "INCONCLUSIVE",
            "reasons": [
                "AI-voice probability was not returned "
                "by a trained authenticity model"
            ],
        }

    if authenticity.confidence is None:
        return {
            "level": "INCONCLUSIVE",
            "reasons": [
                "Detection confidence was not returned "
                "by a trained authenticity model"
            ],
        }

    if not 0 <= authenticity.ai_probability <= 100:
        return {
            "level": "INCONCLUSIVE",
            "reasons": [
                "AI-voice probability is outside the "
                "valid 0-100 range"
            ],
        }

    if not 0 <= authenticity.confidence <= 100:
        return {
            "level": "INCONCLUSIVE",
            "reasons": [
                "Detection confidence is outside the "
                "valid 0-100 range"
            ],
        }

    evidence = (
        authenticity.ai_probability
        * authenticity.confidence
        / 100
    )

    if evidence >= 70:
        level = "HIGH"
    elif evidence >= 40:
        level = "MEDIUM"
    else:
        level = "LOW"

    return {
        "level": level,
        "reasons": (
            authenticity.signals
            or [
                "No high-risk signals returned "
                "by the authenticity provider"
            ]
        ),
    }
