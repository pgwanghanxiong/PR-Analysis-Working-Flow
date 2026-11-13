import asyncio

import httpx
import psycopg

from backend.src import usage_store
from backend.src.main import app


def test_studies_api_returns_names_from_configured_table(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(usage_store, "USAGE_DB_PATH", tmp_path / "usage.sqlite3")
    monkeypatch.setenv("DATABASE_URL", "postgresql://test.invalid/database")

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def execute(self, _query):
            return None

        def fetchall(self):
            return [("Study A",), ("Study B",)]

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def cursor(self):
            return FakeCursor()

    monkeypatch.setattr(psycopg, "connect", lambda _database_url: FakeConnection())

    async def get_studies() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            access = await client.post(
                "/api/access/confirm",
                json={"email": "analyst@example.com", "business_unit": "Research"},
            )
            token = access.json()["session_token"]
            return await client.get(
                "/api/studies",
                headers={"Authorization": f"Bearer {token}"},
            )

    response = asyncio.run(get_studies())
    assert response.status_code == 200
    assert response.json()["status"] == "available"
    assert response.json()["study_names"] == ["Study A", "Study B"]


def test_studies_api_keeps_manual_entry_when_database_is_not_configured(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(usage_store, "USAGE_DB_PATH", tmp_path / "usage.sqlite3")
    monkeypatch.delenv("DATABASE_URL", raising=False)

    async def get_studies() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            access = await client.post(
                "/api/access/confirm",
                json={"email": "analyst@example.com", "business_unit": "Research"},
            )
            token = access.json()["session_token"]
            return await client.get(
                "/api/studies",
                headers={"Authorization": f"Bearer {token}"},
            )

    response = asyncio.run(get_studies())
    assert response.status_code == 200
    assert response.json()["status"] == "unavailable"
    assert response.json()["study_names"] == []
    assert "Enter a Study Name manually" in response.json()["message"]