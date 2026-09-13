from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4


class AuthService:
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
            connection.execute("CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, created_at TEXT NOT NULL)")
            connection.execute("CREATE TABLE IF NOT EXISTS sessions (token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL, expires_at TEXT NOT NULL)")

    def create_user(self, email: str, password: str) -> dict:
        if len(password) < 10:
            raise ValueError("Password must be at least 10 characters long")
        normalized_email = email.strip().lower()
        if "@" not in normalized_email:
            raise ValueError("Enter a valid email address")
        user_id = str(uuid4())
        with self._connect() as connection:
            try:
                connection.execute("INSERT INTO users VALUES (?, ?, ?, ?)", (user_id, normalized_email, self._hash_password(password), datetime.now(timezone.utc).isoformat()))
            except sqlite3.IntegrityError as exc:
                raise ValueError("An account with that email already exists") from exc
        return {"id": user_id, "email": normalized_email}

    def sign_in(self, email: str, password: str) -> tuple[str, dict]:
        with self._connect() as connection:
            user = connection.execute("SELECT * FROM users WHERE email = ?", (email.strip().lower(),)).fetchone()
        if not user or not self._verify_password(password, user["password_hash"]):
            raise ValueError("Email or password is incorrect")
        token = secrets.token_urlsafe(32)
        expires = datetime.now(timezone.utc) + timedelta(days=30)
        with self._connect() as connection:
            connection.execute("INSERT INTO sessions VALUES (?, ?, ?)", (self._token_hash(token), user["id"], expires.isoformat()))
        return token, {"id": user["id"], "email": user["email"]}

    def user_for_token(self, token: str | None) -> dict | None:
        if not token:
            return None
        with self._connect() as connection:
            row = connection.execute("SELECT users.id, users.email, sessions.expires_at FROM sessions JOIN users ON users.id = sessions.user_id WHERE sessions.token_hash = ?", (self._token_hash(token),)).fetchone()
        if not row or datetime.fromisoformat(row["expires_at"]) <= datetime.now(timezone.utc):
            return None
        return {"id": row["id"], "email": row["email"]}

    def sign_out(self, token: str | None):
        if token:
            with self._connect() as connection:
                connection.execute("DELETE FROM sessions WHERE token_hash = ?", (self._token_hash(token),))

    @staticmethod
    def _hash_password(password: str) -> str:
        salt = secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 210_000)
        return f"pbkdf2_sha256$210000${salt.hex()}${digest.hex()}"

    @staticmethod
    def _verify_password(password: str, encoded: str) -> bool:
        _, iterations, salt_hex, digest_hex = encoded.split("$", 3)
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations)).hex()
        return hmac.compare_digest(candidate, digest_hex)

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()