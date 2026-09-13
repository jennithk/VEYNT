from datetime import datetime, timezone

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.risk_engine.risk_engine import compute_risk
from app.schemas.analysis import AnalysisRequest, AnalysisResponse
from app.services.context_analysis import ContextAnalyzer
from app.services.demo_detector import DemoVoiceDetector
from app.services.stream_simulator import StreamSimulator

router = APIRouter()


def _build_analysis(payload: AnalysisRequest) -> AnalysisResponse:
    detector = DemoVoiceDetector()
    detector_result = detector.analyze({"synthetic_score": payload.ai_voice_probability / 100})
    context = ContextAnalyzer().analyze(payload.transcript)
    effective_context_risk = max(payload.context_risk, context["context_risk"])
    risk = compute_risk(
        ai_voice_probability=detector_result["ai_generated_probability"],
        speaker_match=payload.speaker_match,
        context_risk=effective_context_risk,
    )

    explanations = []
    if detector_result["ai_generated_probability"] >= 70:
        explanations.append("Synthetic voice characteristics detected (demo-only adapter)")
    if payload.speaker_match < 50:
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
        payload.transcript,
        detector_result["ai_generated_probability"],
        payload.speaker_match,
        effective_context_risk,
    )
    return AnalysisResponse(
        call_id=payload.call_id,
        classification=risk["classification"],
        overall_risk_score=risk["overall_risk_score"],
        ai_generated_probability=detector_result["ai_generated_probability"],
        speaker_match=payload.speaker_match,
        context_risk=effective_context_risk,
        recommended_action=risk["recommended_action"],
        explanations=explanations,
        transcript=payload.transcript,
        chunks=chunks,
        verification_status="VERIFICATION_REQUIRED" if risk["classification"] != "LOW" else "VERIFIED",
        alert="HIGH RISK: AI-generated voice impersonation likely" if risk["classification"] == "HIGH" else "LOW RISK" if risk["classification"] == "LOW" else "MEDIUM RISK: additional verification recommended",
    )


@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_call(payload: AnalysisRequest) -> AnalysisResponse:
    return _build_analysis(payload)


@router.post("/analyze-upload", response_model=AnalysisResponse)
async def analyze_uploaded_audio(audio: UploadFile = File(...)) -> AnalysisResponse:
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="The uploaded audio file is empty")

    payload = AnalysisRequest(
        call_id=f"upload-{audio.filename or 'audio'}",
        transcript="Uploaded audio received. Live transcription is not enabled in this prototype.",
        ai_voice_probability=72.0,
        speaker_match=58.0,
        context_risk=24.0,
    )
    result = _build_analysis(payload)
    result.explanations.insert(0, f"Audio file received: {audio.filename or 'unnamed file'} ({len(audio_bytes)} bytes)")
    return result
