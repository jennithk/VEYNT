from __future__ import annotations

from fastapi import APIRouter, File, Header, HTTPException, UploadFile

from app.api.routes.analyses import _current_user
from app.api.routes.auth import _bearer, auth
from app.services.analysis_services import build_speaker_verification
from app.services.audio_validation import AudioValidationError, validate_audio
from app.services.speaker_store import SpeakerStore

router = APIRouter(prefix="/speaker-verification", tags=["speaker-verification"])
store = SpeakerStore()


@router.post("")
async def verify_speaker(reference: UploadFile = File(...), test: UploadFile = File(...), authorization: str | None = Header(None)):
    user_id = _current_user(authorization)
    reference_bytes = await reference.read()
    test_bytes = await test.read()
    try:
        validate_audio(reference_bytes, reference.content_type, reference.filename)
        validate_audio(test_bytes, test.content_type, test.filename)
    except AudioValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        result = build_speaker_verification().compare(
            reference_bytes,
            test_bytes,
            reference.filename,
            test.filename,
        )
        payload = {"status": result.status, "similarity": result.similarity, "confidence": result.confidence, "provider": result.provider}
    except RuntimeError as exc:
        payload = {"status": "INCONCLUSIVE", "similarity": None, "confidence": None, "provider": "unconfigured", "reason": str(exc)}
    return store.create(user_id, payload)