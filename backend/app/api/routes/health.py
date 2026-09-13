from datetime import datetime, timezone

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "service": "voice-clone-defense",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
