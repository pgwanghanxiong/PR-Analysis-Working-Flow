import asyncio
from io import BytesIO

import httpx
from openpyxl import load_workbook

from backend.src import main as app_module, usage_store
from backend.src import database as database_module
from backend.src.questionnaire_build import TEMPLATE_FILE


def test_standard_upload_endpoint_validates_then_inserts(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(usage_store, "USAGE_DB_PATH", tmp_path / "usage.sqlite3")
    inserted = []

    def fake_insert(rows, database_url):
        inserted.extend(rows)
        return len(rows)

    monkeypatch.setattr(database_module, "insert_questionnaire_build_rows", fake_insert)
    content = TEMPLATE_FILE.read_bytes()

    async def upload() -> tuple[httpx.Response, httpx.Response]:
        transport = httpx.ASGITransport(app=app_module.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            access = await client.post(
                "/api/access/confirm",
                json={"email": "standard-upload@example.com", "business_unit": "Research"},
            )
            token = access.json()["session_token"]
            headers = {"Authorization": f"Bearer {token}"}
            unauthorized = await client.post(
                "/api/questionnaire-build/upload",
                files={"file": (TEMPLATE_FILE.name, content, "text/csv")},
            )
            authorized = await client.post(
                "/api/questionnaire-build/upload",
                files={"file": (TEMPLATE_FILE.name, content, "text/csv")},
                headers=headers,
            )
            return unauthorized, authorized

    unauthorized, authorized = asyncio.run(upload())
    assert unauthorized.status_code == 401
    assert authorized.status_code == 200, authorized.text
    assert authorized.json()["table"] == "consumer_questionnaire.questionnaire_build"
    assert authorized.json()["inserted_rows"] == 97
    assert len(inserted) == 97


def test_questionnaire_build_read_endpoint_returns_immutable_rows(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(usage_store, "USAGE_DB_PATH", tmp_path / "usage.sqlite3")
    columns = ["ID", "BU", "Category", "Variable Code", "English Question", "Chinese Question", "Options"]
    row = (1, "PCC", "Screen", "WTP", "Willing to participate", "愿意参加吗？", "Yes\nNo")
    monkeypatch.setattr(app_module, "fetch_questionnaire_build_rows", lambda _database_url: [row])

    async def read_table() -> tuple[httpx.Response, httpx.Response]:
        transport = httpx.ASGITransport(app=app_module.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            unauthorized = await client.get("/api/questionnaire-build")
            access = await client.post(
                "/api/access/confirm",
                json={"email": "questionnaire-view@example.com", "business_unit": "Research"},
            )
            authorized = await client.get(
                "/api/questionnaire-build",
                headers={"Authorization": f"Bearer {access.json()['session_token']}"},
            )
            return unauthorized, authorized

    unauthorized, authorized = asyncio.run(read_table())
    assert unauthorized.status_code == 401
    assert authorized.status_code == 200
    assert authorized.json() == {"columns": columns, "rows": [list(row)], "count": 1}


def test_visit_selection_exports_downloadable_excel_without_database_writes(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(usage_store, "USAGE_DB_PATH", tmp_path / "usage.sqlite3")
    monkeypatch.delenv("DATABASE_URL", raising=False)

    async def export() -> httpx.Response:
        transport = httpx.ASGITransport(app=app_module.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            access = await client.post(
                "/api/access/confirm",
                json={"email": "questionnaire-export@example.com", "business_unit": "Research"},
            )
            token = access.json()["session_token"]
            return await client.post(
                "/api/questionnaire-build/export",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "visits": [
                        {
                            "name": "Screening",
                            "questions": [
                                {
                                    "question_code": "WTP",
                                    "question": "Willing to participate?\n您愿意参加吗？",
                                    "answer": "Yes\nNo",
                                }
                            ],
                        },
                        {
                            "name": "D1",
                            "questions": [
                                {
                                    "question_code": "Gndr",
                                    "question": "Gender",
                                    "answer": "Male\nFemale",
                                }
                            ],
                        },
                    ]
                },
            )

    response = asyncio.run(export())
    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    workbook = load_workbook(BytesIO(response.content), read_only=True, data_only=True)
    worksheet = workbook["Questionnaire"]
    rows = list(worksheet.iter_rows(values_only=True))
    assert rows == [
        ("Day", "Question Code", "Question", "Answer"),
        ("Screening", "WTP", "Willing to participate?\n您愿意参加吗？", "Yes\nNo"),
        ("D1", "Gndr", "Gender", "Male\nFemale"),
    ]