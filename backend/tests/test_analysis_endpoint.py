from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_analyze_call_endpoint_returns_risk_summary():
    response = client.post(
        "/api/analyze",
        json={
            "call_id": "call-001",
            "transcript": "I need you to urgently transfer ₹10 lakh to this account. Don't tell anyone until I confirm.",
            "ai_voice_probability": 91.0,
            "speaker_match": 18.0,
            "context_risk": 80.0,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["classification"] in {"HIGH", "MEDIUM"}
    assert body["overall_risk_score"] >= 70
    assert body["recommended_action"] == "DO NOT AUTHORIZE" or body["recommended_action"] == "ADDITIONAL VERIFICATION REQUIRED"
    assert len(body["chunks"]) > 0


def test_analyze_uploaded_audio_returns_file_analysis():
    response = client.post(
        "/api/analyze-upload",
        files={"audio": ("sample.wav", b"demo audio bytes", "audio/wav")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["call_id"] == "upload-sample.wav"
    assert body["classification"] in {"MEDIUM", "HIGH"}
    assert "sample.wav" in body["explanations"][0]
