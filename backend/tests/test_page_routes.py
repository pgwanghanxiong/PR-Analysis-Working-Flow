import asyncio

import httpx

from backend.src.main import app


def test_login_and_workspace_are_separate_urls() -> None:
    async def get_pages() -> tuple[httpx.Response, httpx.Response, httpx.Response]:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            root = await client.get("/", follow_redirects=False)
            login = await client.get("/login")
            workspace = await client.get("/workspace")
            return root, login, workspace

    root, login, workspace = asyncio.run(get_pages())
    assert root.status_code == 302
    assert root.headers["location"] == "/login"
    assert login.status_code == 200
    assert 'id="access-form"' in login.text
    assert "/assets/login.js" in login.text
    assert 'id="analysis-form"' not in login.text
    assert workspace.status_code == 200
    assert 'id="analysis-form"' in workspace.text
    assert 'class="standard-files"' in workspace.text
    assert "/assets/app.js" in workspace.text
    assert 'id="access-form"' not in workspace.text
    upload_section = workspace.text.index('class="workflow-section upload-section"')
    analysis_section = workspace.text.index('class="workflow-section analysis-section"')
    assert upload_section < analysis_section
    assert 'id="existing-study"' in workspace.text
    assert 'id="study-name"' in workspace.text