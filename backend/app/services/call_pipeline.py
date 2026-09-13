from __future__ import annotations

from datetime import datetime, timezone

from app.risk_engine.risk_engine import compute_risk
from app.services.context_analysis import ContextAnalyzer
from app.services.demo_detector import DemoVoiceDetector
from app.services.stream_simulator import StreamSimulator


def build_analysis_result(payload: dict) -> dict:
    detector = DemoVoiceDetector()
    detector_result = detector.analyze({"synthetic_score": payload.get("ai_voice_probability", 18.0) / 100})

    context = ContextAnalyzer().analyze(payload["transcript"])
    risk = compute_risk(
        ai_voice_probability=detector_result["ai_generated_probability"],
        speaker_match=float(payload.get("speaker_match", 92.0)),
        context_risk=max(float(payload.get("context_risk", 12.0)), float(context["context_risk"])),
    )

    explanations = []
    if detector_result["ai_generated_probability"] >= 70:
        explanations.append("Synthetic voice characteristics detected")
    if float(payload.get("speaker_match", 92.0)) < 50:
        explanations.append("Speaker does not strongly match enrolled profile")
    for signal in context["signals"]:
        if signal == "financial_request":
            explanations.append("Urgent financial request detected")
        elif signal == "urgency":
            explanations.append("High urgency instruction detected")
        elif signal == "secrecy":
            explanations.append("Secrecy instruction detected")
        elif signal == "credential_request":
            explanations.append("Credential or OTP request detected")

    chunks = StreamSimulator().generate_chunks(
        payload["transcript"],
        detector_result["ai_generated_probability"],
        float(payload.get("speaker_match", 92.0)),
        max(float(payload.get("context_risk", 12.0)), float(context["context_risk"])),
    )

    classification = risk["classification"]
    event = {
        "call_id": payload.get("call_id", "demo-call"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "classification": classification,
        "overall_risk_score": risk["overall_risk_score"],
        "ai_generated_probability": detector_result["ai_generated_probability"],
        "speaker_match": float(payload.get("speaker_match", 92.0)),
        "context_risk": max(float(payload.get("context_risk", 12.0)), float(context["context_risk"])),
        "recommended_action": risk["recommended_action"],
        "explanations": explanations,
        "transcript": payload["transcript"],
        "chunks": chunks,
        "verification_status": "VERIFICATION_REQUIRED" if classification != "LOW" else "VERIFIED",
        "alert": (
            "HIGH RISK: AI-generated voice impersonation likely"
            if classification == "HIGH"
            else "LOW RISK"
            if classification == "LOW"
            else "MEDIUM RISK: additional verification recommended"
        ),
    }
    return event
