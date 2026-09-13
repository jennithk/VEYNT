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


def compute_evidence_risk(authenticity: AuthenticityResult, transcript: TranscriptionResult) -> dict:
    if authenticity.ai_probability is None or authenticity.confidence is None or not transcript.text:
        return {"level": "INCONCLUSIVE", "reasons": ["Insufficient independent evidence"]}
    evidence = authenticity.ai_probability * authenticity.confidence
    if evidence >= 70:
        level = "HIGH"
    elif evidence >= 40:
        level = "MEDIUM"
    else:
        level = "LOW"
    return {"level": level, "reasons": authenticity.signals or ["No high-risk signals returned by the provider"]}
