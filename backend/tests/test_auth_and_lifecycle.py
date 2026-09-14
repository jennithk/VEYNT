import io
import time
import uuid
import wave

from fastapi.testclient import TestClient

from app.main import app


def wav_bytes():
    output = io.BytesIO()
    with wave.open(output, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(16000)
        wav_file.writeframes(b"\x00\x00" * 16000)
    return output.getvalue()


def test_account_and_analysis_are_authorized():
    client = TestClient(app)
    email = f"test-{uuid.uuid4()}@example.com"
    credentials = {"email": email, "password": "a-secure-password"}

    unauthorized = client.get("/api/analyses")
    assert unauthorized.status_code == 401

    signup = client.post("/api/auth/signup", json=credentials)
    assert signup.status_code == 201
    token = signup.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    created = client.post("/api/analyses?language=te", headers=headers, files={"audio": ("voice.wav", wav_bytes(), "audio/wav")})
    assert created.status_code == 201
    analysis_id = created.json()["id"]

    for _ in range(300):
        detail = client.get(f"/api/analyses/{analysis_id}", headers=headers).json()
        if detail["status"] not in {"QUEUED", "PROCESSING"}:
            break
        time.sleep(0.05)

    assert detail["language"] == "Telugu"
    assert detail["status"] in {"INCONCLUSIVE", "FAILED"}
    assert client.get(f"/api/analyses/{analysis_id}", headers={"Authorization": "Bearer invalid"}).status_code == 401

    assert client.delete(f"/api/analyses/{analysis_id}", headers=headers).status_code == 204
