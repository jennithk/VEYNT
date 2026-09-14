from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from app.risk_engine.risk_engine import compute_evidence_risk
from app.services.analysis_services import (
    TranscriptionResult,
    build_authenticity_service,
    build_speech_to_text,
)
from app.services.analysis_store import AnalysisStore


class AnalysisJobManager:
    def __init__(self, store: AnalysisStore):
        self.store = store

        self.executor = ThreadPoolExecutor(
            max_workers=2,
            thread_name_prefix="veynt-analysis",
        )

    def submit(
        self,
        user_id: str,
        analysis_id: str,
        audio: bytes,
        language: str,
        filename: str | None = None,
    ):
        self.executor.submit(
            self._run,
            user_id,
            analysis_id,
            audio,
            language,
            filename,
        )

    def _run(
        self,
        user_id: str,
        analysis_id: str,
        audio: bytes,
        language: str,
        filename: str | None = None,
    ):
        started = time.perf_counter()

        self.store.update(
            user_id,
            analysis_id,
            status="PROCESSING",
        )

        try:
            # ------------------------------------------------
            # STEP 1: REAL LOCAL WHISPER TRANSCRIPTION
            # ------------------------------------------------
            transcript_warning = None
            try:
                transcript_service = build_speech_to_text()
                transcript = transcript_service.transcribe(
                    audio,
                    language,
                    filename,
                )
            except RuntimeError as exc:
                transcript_warning = f"Transcript unavailable: {exc}"
                transcript = TranscriptionResult(
                    text="",
                    language=language,
                    confidence=None,
                    segments=[],
                )

            # ------------------------------------------------
            # STEP 2: REAL AI-VOICE AUTHENTICITY PROVIDER
            # ------------------------------------------------
            authenticity_service = (
                build_authenticity_service()
            )

            authenticity = authenticity_service.analyze(
                audio,
                transcript.language,
            )

            # ------------------------------------------------
            # STEP 3: EVIDENCE-BASED RISK
            # ------------------------------------------------
            risk = compute_evidence_risk(
                authenticity,
                transcript,
            )

            processing_time = round(
                (time.perf_counter() - started) * 1000
            )

            self.store.update(
                user_id,
                analysis_id,
                status=(
                    "COMPLETED"
                    if risk["level"] != "INCONCLUSIVE"
                    else "INCONCLUSIVE"
                ),
                classification=(
                    authenticity.classification
                ),
                ai_probability=(
                    authenticity.ai_probability
                ),
                detection_confidence=(
                    authenticity.confidence
                ),
                signals=(
                    [*authenticity.signals, transcript_warning]
                    if transcript_warning
                    else authenticity.signals
                ),
                model_version=(
                    authenticity.model_version
                ),
                transcript={
                    "text": transcript.text,
                    "language": transcript.language,
                    "confidence": transcript.confidence,
                    "segments": [
                        segment.__dict__
                        for segment in transcript.segments
                    ],
                },
                risk=risk,
                processing_time_ms=processing_time,
            )

        except RuntimeError as exc:
            processing_time = round(
                (time.perf_counter() - started) * 1000
            )

            self.store.update(
                user_id,
                analysis_id,
                status="INCONCLUSIVE",
                classification="INCONCLUSIVE",
                ai_probability=None,
                detection_confidence=None,
                signals=[
                    str(exc),
                    "A trained AI-voice detection model "
                    "is required for a genuine prediction.",
                ],
                risk={
                    "level": "INCONCLUSIVE",
                    "reasons": [
                        str(exc),
                    ],
                },
                processing_time_ms=processing_time,
            )

            print(
                f"[VEYNT] Analysis inconclusive: {exc}"
            )

        except Exception as exc:
            processing_time = round(
                (time.perf_counter() - started) * 1000
            )

            self.store.update(
                user_id,
                analysis_id,
                status="FAILED",
                classification="INCONCLUSIVE",
                ai_probability=None,
                detection_confidence=None,
                signals=[
                    "The analysis service failed safely",
                    str(exc),
                ],
                risk={
                    "level": "INCONCLUSIVE",
                    "reasons": [
                        "Retry the analysis or use a "
                        "clearer recording.",
                    ],
                },
                processing_time_ms=processing_time,
            )

            print(
                f"[VEYNT] Analysis failed: {exc}"
            )