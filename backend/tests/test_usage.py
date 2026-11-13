import asyncio

import httpx

from backend.src.main import app
from backend.src import usage_store


def test_confirmed_visits_increment_baseline_and_person_count(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(usage_store, "USAGE_DB_PATH", tmp_path / "usage.sqlite3")

    async def confirm_twice() -> tuple[
        httpx.Response, httpx.Response, httpx.Response, httpx.Response, httpx.Response
    ]:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            baseline = await client.get("/api/usage/count")
            first = await client.post(
                "/api/access/confirm",
                json={"email": "Person@Example.com", "business_unit": "Research"},
            )
            second = await client.post(
                "/api/access/confirm",
                json={"email": "person@example.com", "business_unit": "Research"},
            )
            token = second.json()["session_token"]
            session = await client.get(
                "/api/access/session",
                headers={"Authorization": f"Bearer {token}"},
            )
            total = await client.get("/api/usage/count")
            return baseline, first, second, session, total

    baseline, first, second, session, total = asyncio.run(confirm_twice())
    assert baseline.json() == {"total_uses": 66}
    assert first.status_code == 200
    assert first.json()["total_uses"] == 67
    assert first.json()["user_uses"] == 1
    assert second.json()["total_uses"] == 68
    assert second.json()["user_uses"] == 2
    assert session.json()["total_uses"] == 68
    assert session.json()["user_uses"] == 2
    assert total.json() == {"total_uses": 68}


def test_analysis_requires_confirmed_access() -> None:
    async def request_analysis() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.post(
                "/api/analyze",
                data={"study_name": "Unauthorized"},
                files={"file": ("input.csv", b"invalid", "text/csv")},
            )

    response = asyncio.run(request_analysis())
    assert response.status_code == 401