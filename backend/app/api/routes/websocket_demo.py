from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


SCENARIO_DATA = {
    "genuine": {
        "call_id": "call-genuine-01",
        "transcript": "Good morning, I am confirming the project review schedule and will be available for our planned call tomorrow.",
        "ai_voice_probability": 18,
        "speaker_match": 94,
        "context_risk": 10,
    },
    "cloned": {
        "call_id": "call-cloned-02",
        "transcript": "This is urgent. I need you to send the internal credentials and authorize the payment before the board meeting starts.",
        "ai_voice_probability": 91,
        "speaker_match": 18,
        "context_risk": 82,
    },
    "impersonation": {
        "call_id": "call-impersonation-03",
        "transcript": "I need you to urgently transfer ₹10 lakh to this account. Don't tell anyone until I confirm and share the OTP immediately.",
        "ai_voice_probability": 93,
        "speaker_match": 21,
        "context_risk": 88,
    },
}


@router.websocket("/ws/{call_id}")
async def call_stream(websocket: WebSocket, call_id: str):
    await websocket.accept()

    scenario_name = "genuine"
    if "cloned" in call_id:
        scenario_name = "cloned"
    elif "impersonation" in call_id:
        scenario_name = "impersonation"

    base = SCENARIO_DATA.get(scenario_name, SCENARIO_DATA["genuine"])
    transcript_parts = [part.strip() for part in base["transcript"].split(".") if part.strip()]

    try:
        await websocket.send_json({
            "type": "status",
            "message": "ANALYZING",
            "call_id": call_id,
            "scenario": scenario_name,
        })

        for index, part in enumerate(transcript_parts, start=1):
            progress = index / max(len(transcript_parts), 1)
            ai_probability = min(100, max(0, base["ai_voice_probability"] * (0.45 + progress * 0.75)))
            speaker_match = max(0, base["speaker_match"] * (1.0 - progress * 0.35))
            context_risk = min(100, base["context_risk"] * (0.55 + progress * 0.6))
            overall_risk = round(min(100, max(0, ai_probability * 0.5 + (100 - speaker_match) * 0.25 + context_risk * 0.25)))

            if overall_risk >= 70:
                classification = "HIGH"
                action = "DO NOT AUTHORIZE"
                alert = "HIGH RISK: AI-generated voice impersonation likely"
            elif overall_risk >= 40:
                classification = "MEDIUM"
                action = "ADDITIONAL VERIFICATION REQUIRED"
                alert = "MEDIUM RISK: additional verification recommended"
            else:
                classification = "LOW"
                action = "CONTINUE"
                alert = "LOW RISK"

            await websocket.send_json(
                {
                    "type": "chunk",
                    "call_id": call_id,
                    "chunk_index": index,
                    "timestamp": f"00:{index * 2:02d}",
                    "transcript_segment": part,
                    "ai_generated_probability": round(ai_probability, 1),
                    "speaker_match": round(speaker_match, 1),
                    "context_risk": round(context_risk, 1),
                    "overall_risk_score": overall_risk,
                    "classification": classification,
                    "recommended_action": action,
                    "alert": alert,
                }
            )

        await websocket.send_json(
            {
                "type": "final",
                "call_id": call_id,
                "transcript": base["transcript"],
                "ai_generated_probability": round(base["ai_voice_probability"], 1),
                "speaker_match": round(base["speaker_match"], 1),
                "context_risk": round(base["context_risk"], 1),
                "overall_risk_score": round(min(100, max(0, base["ai_voice_probability"] * 0.5 + (100 - base["speaker_match"]) * 0.25 + base["context_risk"] * 0.25))),
                "classification": "HIGH" if base["ai_voice_probability"] >= 70 else "MEDIUM" if base["ai_voice_probability"] >= 40 else "LOW",
                "recommended_action": "DO NOT AUTHORIZE" if base["ai_voice_probability"] >= 70 else "ADDITIONAL VERIFICATION REQUIRED" if base["ai_voice_probability"] >= 40 else "CONTINUE",
                "alert": "HIGH RISK: AI-generated voice impersonation likely" if base["ai_voice_probability"] >= 70 else "MEDIUM RISK: additional verification recommended" if base["ai_voice_probability"] >= 40 else "LOW RISK",
                "explanations": [
                    "Synthetic voice characteristics detected" if base["ai_voice_probability"] >= 70 else "Voice appears consistent with trusted enrollment",
                    "Speaker does not strongly match enrolled profile" if base["speaker_match"] < 50 else "Speaker matches enrolled identity profile",
                    "Urgent financial request detected" if "transfer" in base["transcript"].lower() or "payment" in base["transcript"].lower() else "No suspicious financial action observed",
                    "Secrecy instruction detected" if "don't tell" in base["transcript"].lower() or "until i confirm" in base["transcript"].lower() else "No secrecy instruction observed",
                ],
            }
        )
    except WebSocketDisconnect:
        return
