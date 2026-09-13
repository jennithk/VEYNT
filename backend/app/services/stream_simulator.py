from __future__ import annotations

from typing import Dict, List


class StreamSimulator:
    """Simulate near-real-time processing of audio chunks for demo purposes."""

    def __init__(self, chunk_duration_seconds: float = 2.0):
        self.chunk_duration_seconds = chunk_duration_seconds

    def generate_chunks(self, transcript: str, ai_probability: float, speaker_match: float, context_risk: float) -> List[Dict]:
        sentence_parts = [
            sentence.strip() for sentence in transcript.split(".") if sentence.strip()
        ]
        chunks: List[Dict] = []

        for idx, sentence in enumerate(sentence_parts, start=1):
            progress = idx / max(len(sentence_parts), 1)
            simulated_ai = min(100, max(0, ai_probability * (0.4 + progress * 0.8)))
            simulated_speaker = max(0, speaker_match * (1.0 - progress * 0.35))
            simulated_context = min(100, context_risk * (0.55 + progress * 0.6))
            overall = round(min(100, max(0, simulated_ai * 0.5 + (100 - simulated_speaker) * 0.25 + simulated_context * 0.25)))

            chunks.append(
                {
                    "chunk_index": idx,
                    "timestamp": f"00:{idx * int(self.chunk_duration_seconds):02d}",
                    "ai_probability": round(simulated_ai, 1),
                    "speaker_match": round(simulated_speaker, 1),
                    "context_risk": round(simulated_context, 1),
                    "overall_risk": overall,
                    "transcript_segment": sentence,
                }
            )

        return chunks
