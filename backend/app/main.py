import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.analysis import router as analysis_router
from app.api.routes.analyses import router as analyses_router
from app.api.routes.auth import router as auth_router
from app.api.routes.speaker_verification import router as speaker_router
from app.api.routes.health import router as health_router
from app.api.routes.websocket_demo import router as websocket_router

app = FastAPI(
    title="Voice Clone Defense",
    version="0.1.0",
    description="Prototype pipeline for detecting AI-generated voice impersonation and evaluating risk.",
)

allowed_origins = [origin.strip() for origin in os.getenv("VEYNT_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api")
app.include_router(analysis_router, prefix="/api")
app.include_router(analyses_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(speaker_router, prefix="/api")
app.include_router(websocket_router)


@app.get("/")
async def root() -> dict:
    return {"message": "Voice Clone Defense API is running"}
