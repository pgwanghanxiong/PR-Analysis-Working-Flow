import asyncio
import csv
from io import BytesIO, StringIO

import httpx
from openpyxl import load_workbook

from backend.src.main import app
from calculation.input_schema import expected_columns
from calculation.report_pipeline import load_database_columns


def test_standard_file_downloads() -> None:
    async def download_all() -> dict[str, httpx.Response]:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return {
                "raw": await client.get("/api/templates/raw-input"),
                "report": await client.get("/api/templates/pr-report"),
                "database": await client.get("/api/templates/database"),
                "unknown": await client.get("/api/templates/unknown"),
            }

    responses = asyncio.run(download_all())
    assert responses["raw"].status_code == 200
    assert "2_1_Analysis_Input_Template.csv" in responses["raw"].headers["content-disposition"]
    raw_rows = list(csv.reader(StringIO(responses["raw"].text)))
    assert raw_rows == [expected_columns()]

    assert responses["database"].status_code == 200
    assert "3_1_Database_Ingestion_Template.csv" in responses["database"].headers["content-disposition"]
    database_rows = list(csv.reader(StringIO(responses["database"].text)))
    assert database_rows == [load_database_columns()]

    assert responses["report"].status_code == 200
    workbook = load_workbook(BytesIO(responses["report"].content), read_only=True)
    assert workbook.sheetnames == ["Rep(All Data)"]
    assert responses["unknown"].status_code == 404