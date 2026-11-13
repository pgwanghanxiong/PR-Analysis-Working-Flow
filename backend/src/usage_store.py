from __future__ import annotations

import hashlib
import os
import secrets
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any


BASELINE_USAGE_COUNT = 66
USAGE_DB_PATH = Path(
    os.getenv(
        "USAGE_DB_PATH",
        Path(__file__).resolve().parents[2] / "output" / "usage.sqlite3",
    )
).resolve()


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS usage_counters (
            counter_name TEXT PRIMARY KEY,
            counter_value INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS usage_visits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            business_unit TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS usage_visits_email_idx ON usage_visits (email);
        CREATE TABLE IF NOT EXISTS access_sessions (
            token_hash TEXT PRIMARY KEY,
            email TEXT NOT NULL,
            business_unit TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    connection.execute(
        "INSERT OR IGNORE INTO usage_counters (counter_name, counter_value) VALUES ('total', ?)",
        (BASELINE_USAGE_COUNT,),
    )
    connection.commit()
    return connection


def create_access_session(email: str, business_unit: str) -> dict[str, Any]:
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

    with closing(_connect(USAGE_DB_PATH)) as connection:
        with connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "UPDATE usage_counters SET counter_value = counter_value + 1 WHERE counter_name = 'total'"
            )
            connection.execute(
                "INSERT INTO usage_visits (email, business_unit) VALUES (?, ?)",
                (email, business_unit),
            )
            connection.execute(
                "INSERT INTO access_sessions (token_hash, email, business_unit) VALUES (?, ?, ?)",
                (token_hash, email, business_unit),
            )
            total_uses = connection.execute(
                "SELECT counter_value FROM usage_counters WHERE counter_name = 'total'"
            ).fetchone()[0]
            user_uses = connection.execute(
                "SELECT COUNT(*) FROM usage_visits WHERE email = ?", (email,)
            ).fetchone()[0]

    return {
        "session_token": token,
        "email": email,
        "business_unit": business_unit,
        "user_uses": user_uses,
        "total_uses": total_uses,
    }


def get_access_session(token: str) -> dict[str, str] | None:
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    with closing(_connect(USAGE_DB_PATH)) as connection:
        row = connection.execute(
            "SELECT email, business_unit FROM access_sessions WHERE token_hash = ?",
            (token_hash,),
        ).fetchone()
    return dict(row) if row is not None else None


def get_usage_summary(email: str) -> dict[str, int]:
    with closing(_connect(USAGE_DB_PATH)) as connection:
        total_uses = connection.execute(
            "SELECT counter_value FROM usage_counters WHERE counter_name = 'total'"
        ).fetchone()[0]
        user_uses = connection.execute(
            "SELECT COUNT(*) FROM usage_visits WHERE email = ?", (email,)
        ).fetchone()[0]
    return {"total_uses": total_uses, "user_uses": user_uses}


def get_total_usage() -> int:
    with closing(_connect(USAGE_DB_PATH)) as connection:
        return connection.execute(
            "SELECT counter_value FROM usage_counters WHERE counter_name = 'total'"
        ).fetchone()[0]