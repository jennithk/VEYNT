from pydantic import BaseModel, Field
from typing import List, Optional


class AudioChunk(BaseModel):
    chunk_index: int
    timestamp: str
    ai_probability: float
    speaker_match: float
    context_risk: float
    overall_risk: int
    transcript_segment: str


class AnalysisRequest(BaseModel):
    call_id: str = Field(..., description="Unique call identifier")
    transcript: str = Field(..., description="Transcript of the suspected call")
    ai_voice_probability: float = Field(default=18.0)
    speaker_match: float = Field(default=92.0)
    context_risk: float = Field(default=12.0)


class AnalysisResponse(BaseModel):
    call_id: str
    classification: str
    overall_risk_score: int
    ai_generated_probability: float
    speaker_match: float
    context_risk: float
    recommended_action: str
    explanations: List[str]
    transcript: str
    chunks: List[AudioChunk]
    verification_status: str
    alert: str
