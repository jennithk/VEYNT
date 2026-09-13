from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor

from app.risk_engine.risk_engine import compute_evidence_risk
from app.services.analysis_services import build_authenticity_service, build_speech_to_text
from app.services.analysis_store import AnalysisStore


class AnalysisJobManager:
    def __init__(self, store: AnalysisStore):
        self.store = store
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ve ynt-analysis")

    def submit(self, user_id: str, analysis_id: str, audio: bytes, language: str):
        self.executor.submit(self._run, user_id, analysis_id, audio, language)

    def _run(self, user_id: str, analysis_id: str, audio: bytes, language: str):
        started = time.perf_counter()
        self.store.update(user_id, analysis_id, status="PROCESSING")
        try:
            transcript_service = build_speech_to_text()
            transcript = transcript_service.transcribe(audio, language)
            detector = build_authenticity_service()
            authenticity = detector.analyze(audio, transcript.language)
            risk = compute_evidence_risk(authenticity, transcript)
            self.store.update(
                user_id,
                analysis_id,
                status="COMPLETED" if risk["level"] != "INCONCLUSIVE" else "INCONCLUSIVE",
                classification=authenticity.classification,
                ai_probability=authenticity.ai_probability,
                detection_confidence=authenticity.confidence,
                signals=authenticity.signals,
                model_version=authenticity.model_version,
                transcript={"text": transcript.text, "language": transcript.language, "confidence": transcript.confidence, "segments": [segment.__dict__ for segment in transcript.segments]},
                risk=risk,
                processing_time_ms=round((time.perf_counter() - started) * 1000),
            )
        except RuntimeError as exc:
            self.store.update(user_id, analysis_id, status="INCONCLUSIVE", signals=[str(exc), "Configure verified providers before treating this as a production result"], risk={"level": "INCONCLUSIVE", "reasons": [str(exc)]}, processing_time_ms=round((time.perf_counter() - started) * 1000))
        except Exception as exc:
            self.store.update(user_id, analysis_id, status="FAILED", signals=["The analysis service failed safely", str(exc)], risk={"level": "INCONCLUSIVE", "reasons": ["Retry the analysis or use a clearer recording"]}, processing_time_ms=round((time.perf_counter() - started) * 1000))