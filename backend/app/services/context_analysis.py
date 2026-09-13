from __future__ import annotations

import re


class ContextAnalyzer:
    """Transparent rule-based analyzer for suspicious financial requests."""

    def analyze(self, transcript: str) -> dict:
        normalized = transcript.lower()
        signals = []

        if re.search(r"transfer|send money|wire|remit|deposit|pay|account", normalized):
            signals.append("financial_request")
        if re.search(r"urgent|immediately|asap|today|now|quickly|emergency", normalized):
            signals.append("urgency")
        if re.search(r"don't tell|secret|confidential|keep it private|until i confirm|do not disclose|silent", normalized):
            signals.append("secrecy")
        if re.search(r"otp|password|credentials|token|pin|login|verify code|access", normalized):
            signals.append("credential_request")
        if re.search(r"executive|ceo|director|board|president|funds|approval|authorise|authorize", normalized):
            signals.append("executive_impersonation_risk")

        risk_score = 0
        if "financial_request" in signals:
            risk_score += 35
        if "urgency" in signals:
            risk_score += 25
        if "secrecy" in signals:
            risk_score += 20
        if "credential_request" in signals:
            risk_score += 20
        if "executive_impersonation_risk" in signals:
            risk_score += 15

        context_risk = min(100, max(0, risk_score))
        return {
            "transcript": transcript,
            "signals": signals,
            "context_risk": context_risk,
            "summary": "Potential impersonation or suspicious financial instruction detected." if context_risk >= 60 else "Context appears normal.",
            "risk_level": "HIGH" if context_risk >= 70 else "MEDIUM" if context_risk >= 40 else "LOW",
        }
