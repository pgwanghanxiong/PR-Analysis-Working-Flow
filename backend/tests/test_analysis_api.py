import asyncio
import json
from pathlib import Path

import httpx
import pandas as pd

from backend.src import main as app_module
from backend.src import usage_store
from calculation.input_schema import expected_columns


ROOT = Path(__file__).resolve().parents[2]


def test_csv_upload_generates_report_exports_and_schema_warning(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(app_module, "ARTIFACT_DIR", tmp_path)
    monkeypatch.setattr(usage_store, "USAGE_DB_PATH", tmp_path / "usage.sqlite3")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    input_path = tmp_path / "sample.csv"
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
                for metric_index in range(len(expected_columns()) - 2)
            ]
        )
    pd.DataFrame(sample_rows, columns=expected_columns()).to_csv(input_path, index=False)

    async def upload() -> httpx.Response:
        transport = httpx.ASGITransport(app=app_module.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            access_response = await client.post(
                "/api/access/confirm",
                json={"email": "analyst@example.com", "business_unit": "Research"},
            )
            assert access_response.status_code == 200
            access = access_response.json()
            return await client.post(
                "/api/analyze",
                data={"study_name": "Reference Study"},
                files={"file": (input_path.name, input_path.read_bytes(), "text/csv")},
                headers={"Authorization": f"Bearer {access['session_token']}"},
            )

    response = asyncio.run(upload())

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["report"]["sheet_name"] == "Rep(All Data)"
    assert result["report"]["rows"][0]["day"].startswith("Day")
    assert result["validation"]["input_schema"] == "passed"
    assert result["validation"]["database"]["status"] == "warning"

    run_dir = tmp_path / result["run_id"]
    assert (run_dir / "business_report.xlsx").is_file()
    assert (run_dir / "database_ingestion.csv").is_file()
    log = json.loads((run_dir / "validation_log.json").read_text(encoding="utf-8"))
    assert log["database_export_columns"] == list(pd.read_csv(run_dir / "database_ingestion.csv").columns)