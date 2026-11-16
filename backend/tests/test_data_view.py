import asyncio
from decimal import Decimal

import httpx
import pandas as pd

from backend.src import main as app_module, usage_store
from backend.src.data_view import build_wide_view
from backend.src.database import DatabaseUnavailable, LONG_COLUMNS


def test_wide_view_preserves_identifiers_days_and_duplicate_answers() -> None:
    data = pd.DataFrame(
        [
            ("Study A", "001", 1, "A", "Question 1", Decimal("72.50")),
            ("Study A", "001", 1, "A", "Question 1", Decimal("73.00")),
            ("Study A", "001", 1, "A", "Question 2", Decimal("80")),
            ("Study A", "001", 7, "A", "Question 2", Decimal("85")),
        ],
        columns=LONG_COLUMNS,
    )

    result = build_wide_view(data)

    assert result["columns"] == [*LONG_COLUMNS[:4], "Question 1", "Question 2"]
    assert result["rows"] == [
        ["Study A", "001", 1, "A", ["72.50", "73.00"], ["80"]],
        ["Study A", "001", 7, "A", [], ["85"]],
    ]
    assert result["duplicate_cells"] == 1


def test_empty_wide_view_keeps_identity_columns() -> None:
    result = build_wide_view(pd.DataFrame(columns=LONG_COLUMNS))

    assert result == {"columns": LONG_COLUMNS[:4], "rows": [], "duplicate_cells": 0}


def test_data_view_endpoint_requires_session_and_reads_selected_study(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(usage_store, "USAGE_DB_PATH", tmp_path / "usage.sqlite3")
    selected_studies = []

    def fetch_rows(_url, _table, study_name):
        selected_studies.append(study_name)
        return pd.DataFrame(
            [(study_name, "001", 1, "A", "Question 1", Decimal("72.50"))],
            columns=LONG_COLUMNS,
        )

    monkeypatch.setattr(app_module, "fetch_study_rows", fetch_rows)

    async def request_data():
        transport = httpx.ASGITransport(app=app_module.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            unauthorized = await client.get("/api/questionnaire-data", params={"study_name": "Study A"})
            access = await client.post(
                "/api/access/confirm",
                json={"email": "viewer@example.com", "business_unit": "Research"},
            )
            authorized = await client.get(
                "/api/questionnaire-data",
                params={"study_name": "Study A"},
                headers={"Authorization": f"Bearer {access.json()['session_token']}"},
            )
            return unauthorized, authorized

    unauthorized, authorized = asyncio.run(request_data())
    assert unauthorized.status_code == 401
    assert authorized.status_code == 200
    assert selected_studies == ["Study A"]
    assert authorized.json()["rows"] == [["Study A", "001", 1, "A", ["72.50"]]]


def test_data_view_reports_empty_study_and_database_failure(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(usage_store, "USAGE_DB_PATH", tmp_path / "usage.sqlite3")

    def fetch_rows(_url, _table, study_name):
        if study_name == "Offline":
            raise DatabaseUnavailable("DATABASE_URL is not configured.")
        return pd.DataFrame(columns=LONG_COLUMNS)

    monkeypatch.setattr(app_module, "fetch_study_rows", fetch_rows)

    async def request_data():
        transport = httpx.ASGITransport(app=app_module.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            access = await client.post(
                "/api/access/confirm",
                json={"email": "viewer@example.com", "business_unit": "Research"},
            )
            headers = {"Authorization": f"Bearer {access.json()['session_token']}"}
            empty = await client.get("/api/questionnaire-data", params={"study_name": "Empty"}, headers=headers)
            offline = await client.get("/api/questionnaire-data", params={"study_name": "Offline"}, headers=headers)
            return empty, offline

    empty, offline = asyncio.run(request_data())
    assert empty.status_code == 404
    assert offline.status_code == 503
    assert "DATABASE_URL is not configured" in offline.json()["detail"]