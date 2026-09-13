from app.risk_engine.risk_engine import classify_risk, compute_risk
from app.services.context_analysis import ContextAnalyzer


def test_context_analysis_detects_suspicious_financial_request():
    analysis = ContextAnalyzer().analyze(
        "I need you to urgently transfer ₹10 lakh to this account and don't tell anyone until I confirm."
    )

    assert analysis["context_risk"] >= 75
    assert "financial_request" in analysis["signals"]
    assert "urgency" in analysis["signals"]
    assert "secrecy" in analysis["signals"]


def test_risk_engine_classifies_high_risk_score():
    risk = compute_risk(91, 18, 92)
    assert risk["overall_risk_score"] >= 70
    assert risk["classification"] == "HIGH"
    assert risk["recommended_action"] == "DO NOT AUTHORIZE"


def test_risk_engine_classifies_low_risk_score():
    risk = compute_risk(18, 94, 12)
    assert risk["classification"] == "LOW"
    assert risk["recommended_action"] == "CONTINUE"


def test_classify_risk_helpers():
    assert classify_risk(12) == "LOW"
    assert classify_risk(55) == "MEDIUM"
    assert classify_risk(85) == "HIGH"
