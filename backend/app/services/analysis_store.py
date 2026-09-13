from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any
from uuid import uuid4
from datetime import datetime, timezone


class AnalysisStore:
    def __init__(self, database_path: str | None = None):
        self.database_path = database_path or str(Path(__file__).resolve().parents[3] / "data" / "analysis.sqlite3")
        Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        self._create_tables()

    def _connect(self):
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _create_tables(self):
        with self._connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS analyses (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    recording_name TEXT NOT NULL,
                    language TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
            """)

    def create(self, user_id: str, recording_name: str, language: str, payload: dict[str, Any], status: str = "COMPLETED") -> dict[str, Any]:
        analysis_id = str(uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        record = {"id": analysis_id, "user_id": user_id, "recording_name": recording_name, "language": language, "status": status, "created_at": created_at, **payload}
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO analyses (id, user_id, created_at, status, recording_name, language, payload) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (analysis_id, user_id, created_at, status, recording_name, language, json.dumps(record)),
            )
        return record

    def list(self, user_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute("SELECT payload FROM analyses WHERE user_id = ? ORDER BY created_at DESC", (user_id,)).fetchall()
        return [json.loads(row["payload"]) for row in rows]

    def get(self, user_id: str, analysis_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT payload FROM analyses WHERE user_id = ? AND id = ?", (user_id, analysis_id)).fetchone()
        return json.loads(row["payload"]) if row else None

    def delete(self, user_id: str, analysis_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM analyses WHERE user_id = ? AND id = ?", (user_id, analysis_id))
        return cursor.rowcount > 0

    def update(self, user_id: str, analysis_id: str, **changes: Any) -> dict[str, Any] | None:
        record = self.get(user_id, analysis_id)
        if not record:
            return None
        record.update(changes)
        with self._connect() as connection:
            connection.execute("UPDATE analyses SET status = ?, payload = ? WHERE user_id = ? AND id = ?", (record.get("status", "COMPLETED"), json.dumps(record), user_id, analysis_id))
        return record