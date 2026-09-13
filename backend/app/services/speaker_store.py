from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


class SpeakerStore:
    def __init__(self, database_path: str | None = None):
        self.database_path = database_path or str(Path(__file__).resolve().parents[3] / "data" / "analysis.sqlite3")
        Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.database_path) as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS speaker_verifications (id TEXT PRIMARY KEY, user_id TEXT NOT NULL, created_at TEXT NOT NULL, payload TEXT NOT NULL)")

    def create(self, user_id: str, payload: dict) -> dict:
        record = {"id": str(uuid4()), "user_id": user_id, "created_at": datetime.now(timezone.utc).isoformat(), **payload}
        with sqlite3.connect(self.database_path) as connection:
            connection.execute("INSERT INTO speaker_verifications VALUES (?, ?, ?, ?)", (record["id"], user_id, record["created_at"], json.dumps(record)))
        return record