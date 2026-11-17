import asyncio

import httpx

from backend.src.main import app


def test_login_and_workspace_are_separate_urls() -> None:
    async def get_pages() -> tuple[
        httpx.Response,
        httpx.Response,
        httpx.Response,
        httpx.Response,
        httpx.Response,
        httpx.Response,
        httpx.Response,
        httpx.Response,
        httpx.Response,
        httpx.Response,
    ]:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            root = await client.get("/", follow_redirects=False)
            login = await client.get("/login")
            menu = await client.get("/questionnaire")
            questionnaire_create = await client.get("/questionnaire-create")
            upload = await client.get("/questionnaire-data-upload")
            standard_upload = await client.get("/questionnaire-standard-upload")
            data_view = await client.get("/questionnaire-data-view")
            analysis = await client.get("/questionnaire-data-analysis")
            workspace_alias = await client.get("/workspace", follow_redirects=False)
            return root, login, menu, questionnaire_create, upload, standard_upload, data_view, analysis, workspace_alias

    root, login, menu, questionnaire_create, upload, standard_upload, data_view, analysis, workspace_alias = asyncio.run(get_pages())
    assert root.status_code == 302
    assert root.headers["location"] == "/login"
    assert login.status_code == 200
    assert 'id="access-form"' in login.text
    assert "/assets/login.js" in login.text
    assert 'id="analysis-form"' not in login.text

    assert menu.status_code == 200
    assert "Questionnaire</h1>" in menu.text
    assert 'href="/questionnaire-data-upload"' in menu.text
    assert 'href="/questionnaire-data-view"' in menu.text
    assert 'href="/questionnaire-data-analysis"' in menu.text
    assert menu.text.index("1. Questionnaire Build") < menu.text.index(
        'href="/questionnaire-standard-upload"'
    ) < menu.text.index('href="/questionnaire-create"') < menu.text.index(
        "2. Questionnaire Data"
    ) < menu.text.index('href="/questionnaire-data-upload"') < menu.text.index(
        'href="/questionnaire-data-view"'
    ) < menu.text.index('href="/questionnaire-data-analysis"')

    assert upload.status_code == 200
    assert 'id="upload-form"' in upload.text
    assert 'id="upload-button"' in upload.text
    assert 'class="standard-files"' in upload.text
    assert 'id="analysis-form"' not in upload.text
    assert "/assets/upload.js" in upload.text

    assert standard_upload.status_code == 200
    assert 'id="questionnaire-standard-upload-form"' in standard_upload.text
    assert 'id="questionnaire-standard-file"' in standard_upload.text
    assert "/assets/questionnaire-standard-upload.js" in standard_upload.text

    assert data_view.status_code == 200
    assert 'id="view-study"' in data_view.text
    assert 'id="data-view-table"' in data_view.text
    assert 'id="upload-form"' not in data_view.text
    assert 'id="analysis-form"' not in data_view.text
    assert "/assets/data-view.js" in data_view.text

    assert analysis.status_code == 200
    assert 'id="analysis-form"' in analysis.text
    assert 'id="results"' in analysis.text
    assert 'id="upload-form"' not in analysis.text
    assert 'class="standard-files"' not in analysis.text
    assert "/assets/app.js" in analysis.text

    assert workspace_alias.status_code == 302
    assert workspace_alias.headers["location"] == "/questionnaire-data-analysis"
    assert 'href="/questionnaire-create"' in menu.text
    assert questionnaire_create.status_code == 200
    assert 'id="questionnaire-build-table"' in questionnaire_create.text
    assert 'id="add-visit"' in questionnaire_create.text
    assert 'id="visit-dialog"' in questionnaire_create.text
    assert 'id="visit-name"' in questionnaire_create.text
    assert "/assets/questionnaire-create.js" in questionnaire_create.text
    assert 'type="checkbox"' not in questionnaire_create.text
    assert 'id="questionnaire-create-button"' in questionnaire_create.text
    assert 'id="download-questionnaire-excel"' in questionnaire_create.text
    assert "window.print" not in questionnaire_create.text
    assert ".pdf" not in questionnaire_create.text.lower()