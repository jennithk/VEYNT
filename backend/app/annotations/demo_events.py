from dataclasses import dataclass, field
from typing import List


@dataclass
class EventExplanation:
    label: str
    detail: str


@dataclass
class RiskEvent:
    call_id: str
    timestamp: str
    risk_score: int
    ai_probability: float
    speaker_match: float
    context_risk: float
    classification: str
    alert: str
    recommended_action: str
    verification_status: str
    explanations: List[str] = field(default_factory=list)
