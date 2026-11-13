import asyncio

import httpx
import psycopg

from backend.src.main import app
from backend.src.database import LONG_COLUMNS


class FakeCursor:
    def __init__(self):
        self.calls = 0
        self.rows = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def execute(self, _query, _params=None):
        self.calls += 1
        if self.calls == 1:
            self.rows = [(column,) for column in ["id", *LONG_COLUMNS, "created_at"]]
        else:
            self.rows = [("Study A",), ("Study B",)]

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self):
        self.fake_cursor = FakeCursor()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def cursor(self):
        return self.fake_cursor


def test_studies_api_returns_names_from_postgres(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://test.invalid/database")
    monkeypatch.setattr(
        psycopg,
        "connect",
        lambda _database_url: FakeConnection(),
    )

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


def test_studies_api_requires_postgres_connection(monkeypatch) -> None:
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
    assert response.status_code == 503
    assert "DATABASE_URL is not configured" in response.json()["detail"]