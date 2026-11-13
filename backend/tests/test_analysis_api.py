import asyncio
import json

import httpx
import pandas as pd
import pytest

from backend.src import main as app_module
from backend.src import usage_store
from backend.src.database import LONG_COLUMNS
from calculation.input_schema import expected_columns
from calculation.report_pipeline import transform_database_data


def wide_sample() -> pd.DataFrame:
    columns = expected_columns()
    sample_rows = []
    for respondent_id, product, score_offset, respondent_variation in (
        ("A001", "A", 60, 0),
        ("A002", "A", 60, 1),
        ("A003", "A", 60, 3),
        ("A004", "A", 60, 7),
        ("B001", "B", 80, 0),
        ("B002", "B", 80, 2),
        ("B003", "B", 80, 4),
        ("B004", "B", 80, 9),
    ):
        sample_rows.append(
            [respondent_id, product]
            + [
                score_offset + (metric_index % 3) + respondent_variation
                for metric_index in range(len(columns) - 2)
            ]
        )
    return pd.DataFrame(sample_rows, columns=columns)


def test_wide_upload_is_transformed_and_persisted(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(usage_store, "USAGE_DB_PATH", tmp_path / "usage.sqlite3")
    monkeypatch.setenv("DATABASE_URL", "postgresql://test")
    captured: dict[str, object] = {}

    def fake_insert(data, _database_url, _table_name):
        captured["data"] = data.copy()
        return len(data)

    monkeypatch.setattr(app_module, "insert_uploaded_rows", fake_insert)
    raw = wide_sample()

    async def upload() -> httpx.Response:
        transport = httpx.ASGITransport(app=app_module.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            access = await client.post(
                "/api/access/confirm",
                json={"email": "wide@example.com", "business_unit": "Research"},
            )
            token = access.json()["session_token"]
            return await client.post(
                "/api/uploads",
                data={"study_name": "Wide Study"},
                files={"file": ("wide.csv", raw.to_csv(index=False).encode(), "text/csv")},
                headers={"Authorization": f"Bearer {token}"},
            )

    response = asyncio.run(upload())
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["format"] == "wide"
    assert result["status"] == "saved"
    assert result["study_names"] == ["Wide Study"]
    assert list(captured["data"].columns) == LONG_COLUMNS
    assert captured["data"]["1_Study"].eq("Wide Study").all()
    assert len(captured["data"]) == len(raw) * (len(expected_columns()) - 2)


def test_long_upload_keeps_row_study_name_and_persists(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(usage_store, "USAGE_DB_PATH", tmp_path / "usage.sqlite3")
    monkeypatch.setenv("DATABASE_URL", "postgresql://test")
    captured: dict[str, object] = {}

    def fake_insert(data, _database_url, _table_name):
        captured["data"] = data.copy()
        return len(data)

    monkeypatch.setattr(app_module, "insert_uploaded_rows", fake_insert)
    long_data = pd.DataFrame(
        [
            ["Existing Study", "001", 1, "Product A", "Question A", 72],
            ["Existing Study", "002", 1, "Product A", "Question A", 75],
        ],
        columns=LONG_COLUMNS,
    )

    async def upload() -> httpx.Response:
        transport = httpx.ASGITransport(app=app_module.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            access = await client.post(
                "/api/access/confirm",
                json={"email": "long@example.com", "business_unit": "Research"},
            )
            token = access.json()["session_token"]
            return await client.post(
                "/api/uploads",
                files={"file": ("long.csv", long_data.to_csv(index=False).encode(), "text/csv")},
                headers={"Authorization": f"Bearer {token}"},
            )

    response = asyncio.run(upload())
    assert response.status_code == 200, response.text
    assert response.json()["format"] == "long"
    assert response.json()["inserted_rows"] == 2
    assert response.json()["study_names"] == ["Existing Study"]
    assert captured["data"].equals(long_data)


def test_upload_requires_postgres_connection(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(usage_store, "USAGE_DB_PATH", tmp_path / "usage.sqlite3")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    long_data = pd.DataFrame(
        [["Study A", "001", 1, "A", "Question", 70]],
        columns=LONG_COLUMNS,
    )

    async def upload() -> httpx.Response:
        transport = httpx.ASGITransport(app=app_module.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            access = await client.post(
                "/api/access/confirm",
                json={"email": "offline@example.com", "business_unit": "Research"},
            )
            token = access.json()["session_token"]
            return await client.post(
                "/api/uploads",
                files={"file": ("long.csv", long_data.to_csv(index=False).encode(), "text/csv")},
                headers={"Authorization": f"Bearer {token}"},
            )

    response = asyncio.run(upload())
    assert response.status_code == 503
    assert "DATABASE_URL is not configured" in response.json()["detail"]


def test_analyze_loads_selected_study_from_database(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(app_module, "ARTIFACT_DIR", tmp_path / "artifacts")
    long_data = transform_database_data(wide_sample(), "Study A")
    monkeypatch.setattr(app_module, "fetch_study_rows", lambda *_args: long_data)

    async def analyze() -> httpx.Response:
        transport = httpx.ASGITransport(app=app_module.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            access = await client.post(
                "/api/access/confirm",
                json={"email": "analysis@example.com", "business_unit": "Research"},
            )
            token = access.json()["session_token"]
            return await client.post(
                "/api/analyze",
                data={"study_name": "Study A"},
                headers={"Authorization": f"Bearer {token}"},
            )

    response = asyncio.run(analyze())
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["validation"]["study_name"] == "Study A"
    assert result["validation"]["database"]["status"] == "loaded"
    assert result["report"]["sheet_name"] == "Rep(All Data)"

    run_dir = tmp_path / "artifacts" / result["run_id"]
    assert (run_dir / "business_report.xlsx").is_file()
    assert (run_dir / "database_ingestion.csv").is_file()
    log = json.loads((run_dir / "validation_log.json").read_text(encoding="utf-8"))
    assert log["study_name"] == "Study A"