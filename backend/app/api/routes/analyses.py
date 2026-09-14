from __future__ import annotations

import os

from fastapi import APIRouter, File, Header, HTTPException, Query, UploadFile
from pydantic import BaseModel

from app.api.routes.auth import auth
from app.services.analysis_jobs import AnalysisJobManager
from app.services.analysis_services import SUPPORTED_LANGUAGES
from app.services.analysis_store import AnalysisStore
from app.services.audio_validation import AudioValidationError, validate_audio

router = APIRouter(prefix="/analyses", tags=["analyses"])
store = AnalysisStore()
jobs = AnalysisJobManager(store)


class AnalysisStartResponse(BaseModel):
    id: str
    status: str
    message: str


def _bearer(authorization: str | None) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


def _current_user(authorization: str | None) -> str:
    user = auth.user_for_token(_bearer(authorization))
    if user:
        return user["id"]
    if os.getenv("VEYNT_ALLOW_ANONYMOUS", "0") == "1":
        return "local-user"
    raise HTTPException(status_code=401, detail="Sign in to manage analyses")


@router.post("", response_model=AnalysisStartResponse, status_code=201)
async def create_analysis(
    audio: UploadFile = File(...),
    language: str = Query("auto", pattern="^(auto|en|hi|te)$"),
    authorization: str | None = Header(None),
):
    user_id = _current_user(authorization)
    content = await audio.read()
    try:
        metadata = validate_audio(content, audio.content_type, audio.filename)
    except AudioValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    selected_language = "auto" if language == "auto" else SUPPORTED_LANGUAGES[language]
    record = store.create(
        user_id,
        audio.filename or "recording",
        selected_language,
        {
            "duration_seconds": metadata.duration_seconds,
            "audio_quality": metadata.quality,
            "sample_rate": metadata.sample_rate,
            "channels": metadata.channels,
            "classification": None,
            "ai_probability": None,
            "detection_confidence": None,
            "signals": [],
            "transcript": {"text": "", "language": selected_language, "confidence": None, "segments": []},
            "risk": {"level": "INCONCLUSIVE", "reasons": ["Analysis has not completed"]},
            "model_version": None,
            "processing_time_ms": None,
        },
        status="QUEUED",
    )
    jobs.submit(
        user_id,
        record["id"],
        content,
        language,
        audio.filename,
    )
    return AnalysisStartResponse(id=record["id"], status="QUEUED", message="Analysis queued")


@router.get("")
def list_analyses(authorization: str | None = Header(None)):
    return {"items": store.list(_current_user(authorization))}


@router.get("/{analysis_id}")
def get_analysis(analysis_id: str, authorization: str | None = Header(None)):
    record = store.get(_current_user(authorization), analysis_id)
    if not record:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return record


@router.delete("/{analysis_id}", status_code=204)
def delete_analysis(analysis_id: str, authorization: str | None = Header(None)):
    if not store.delete(_current_user(authorization), analysis_id):
        raise HTTPException(status_code=404, detail="Analysis not found")
