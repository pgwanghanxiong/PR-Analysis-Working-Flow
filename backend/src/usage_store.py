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
        CREATE TABLE IF NOT EXISTS uploaded_studies (
            study_name TEXT PRIMARY KEY,
            upload_count INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_uploaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS usage_migrations (
            migration_name TEXT PRIMARY KEY,
            completed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
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


def record_uploaded_study(study_name: str) -> None:
    normalized_name = study_name.strip()
    if not normalized_name:
        return
    with closing(_connect(USAGE_DB_PATH)) as connection:
        with connection:
            connection.execute(
                """INSERT INTO uploaded_studies (study_name)
                   VALUES (?)
                   ON CONFLICT(study_name) DO UPDATE SET
                       upload_count = uploaded_studies.upload_count + 1,
                       last_uploaded_at = CURRENT_TIMESTAMP""",
                (normalized_name,),
            )


def get_uploaded_study_names() -> list[str]:
    with closing(_connect(USAGE_DB_PATH)) as connection:
        rows = connection.execute(
            "SELECT study_name FROM uploaded_studies ORDER BY study_name COLLATE NOCASE"
        ).fetchall()
    return [row[0] for row in rows]


def study_migration_applied(migration_name: str) -> bool:
    with closing(_connect(USAGE_DB_PATH)) as connection:
        row = connection.execute(
            "SELECT 1 FROM usage_migrations WHERE migration_name = ?",
            (migration_name,),
        ).fetchone()
    return row is not None


def backfill_uploaded_studies(study_names: list[str], migration_name: str) -> None:
    with closing(_connect(USAGE_DB_PATH)) as connection:
        with connection:
            already_applied = connection.execute(
                "SELECT 1 FROM usage_migrations WHERE migration_name = ?",
                (migration_name,),
            ).fetchone()
            if already_applied:
                return
            connection.executemany(
                "INSERT OR IGNORE INTO uploaded_studies (study_name) VALUES (?)",
                [(name.strip(),) for name in set(study_names) if name.strip()],
            )
            connection.execute(
                "INSERT INTO usage_migrations (migration_name) VALUES (?)",
                (migration_name,),
            )