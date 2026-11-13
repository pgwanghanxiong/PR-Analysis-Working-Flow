from __future__ import annotations

import json
import os
import re
import sys
import uuid
import csv
from io import BytesIO, StringIO
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from calculation.input_schema import (
    ID_COLUMN,
    PRODUCT_COLUMN,
    expected_columns,
    validate_raw_dataframe,
)
from calculation.report_pipeline import (
    create_report_payload,
    load_analysis_dispatcher,
    load_database_columns,
    REPORT_TEMPLATE,
    transform_database_data,
    write_business_report,
    write_database_export,
    write_validation_log,
)
from backend.src.database import IDENTIFIER_PATTERN, persist_if_schema_matches
from backend.src.usage_store import (
    create_access_session,
    get_access_session,
    get_total_usage,
    get_usage_summary,
)


FRONTEND_DIR = ROOT / "frontend"
ARTIFACT_DIR = Path(os.getenv("REPORT_OUTPUT_DIR", ROOT / "output")).resolve()
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
app = FastAPI(title="Questionnaire Analysis", version="1.0.0")
app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "src"), name="assets")


class AccessRequest(BaseModel):
    email: str
    business_unit: str


def _require_access(authorization: str | None) -> dict[str, str]:
    scheme, separator, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not separator or not token.strip():
        raise HTTPException(status_code=401, detail="Confirm your email and business unit to continue.")
    session = get_access_session(token.strip())
    if session is None:
        raise HTTPException(status_code=401, detail="Access session is invalid. Please confirm your details again.")
    return session


def _read_uploaded_csv(content: bytes) -> pd.DataFrame:
    try:
        data = pd.read_csv(
            BytesIO(content),
            dtype={ID_COLUMN: "string", PRODUCT_COLUMN: "string"},
        )
        return validate_raw_dataframe(data)
    except (UnicodeDecodeError, pd.errors.ParserError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse("/login", status_code=302)


@app.get("/login")
def login_page() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "login.html")


@app.get("/workspace")
def workspace_page() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/usage/count")
def usage_count() -> dict[str, int]:
    return {"total_uses": get_total_usage()}


@app.post("/api/access/confirm")
def confirm_access(request: AccessRequest) -> dict[str, Any]:
    email = request.email.strip().lower()
    business_unit = request.business_unit.strip()
    if len(email) > 254 or re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email) is None:
        raise HTTPException(status_code=422, detail="Enter a valid work email address.")
    if not business_unit or len(business_unit) > 80:
        raise HTTPException(status_code=422, detail="Enter a business unit (up to 80 characters).")
    return create_access_session(email, business_unit)


@app.get("/api/access/session")
def access_session(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    session = _require_access(authorization)
    return {**session, **get_usage_summary(session["email"])}


@app.get("/api/studies")
def list_studies(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _require_access(authorization)
    database_url = os.getenv("DATABASE_URL")
    table_name = os.getenv("DATABASE_TABLE", "consumer_questionnaire.questionnaire_data")
    if not database_url:
        return {
            "status": "unavailable",
            "study_names": [],
            "message": "Database is not configured. Enter a Study Name manually.",
        }

    parts = table_name.split(".")
    if len(parts) != 2 or any(IDENTIFIER_PATTERN.fullmatch(part) is None for part in parts):
        return {
            "status": "unavailable",
            "study_names": [],
            "message": "DATABASE_TABLE must be a schema-qualified PostgreSQL identifier. Enter a Study Name manually.",
        }

    try:
        import psycopg
        from psycopg import sql

        schema, table = parts
        study_column = sql.Identifier("1_Study")
        query = sql.SQL(
            "SELECT DISTINCT {column} FROM {schema}.{table} "
            "WHERE {column} IS NOT NULL AND btrim({column}) <> '' ORDER BY {column}"
        ).format(
            column=study_column,
            schema=sql.Identifier(schema),
            table=sql.Identifier(table),
        )
        with psycopg.connect(database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query)
                study_names = [str(row[0]).strip() for row in cursor.fetchall()]
        return {
            "status": "available",
            "study_names": study_names,
            "message": f"Loaded {len(study_names)} Study Names from the database."
            if study_names
            else "No Study Names found in the database. Enter one manually.",
        }
    except Exception:
        return {
            "status": "unavailable",
            "study_names": [],
            "message": "Could not load Study Names from the database. Enter a Study Name manually.",
        }


@app.get("/api/templates/{kind}")
def download_template(kind: str) -> Response:
    if kind == "pr-report":
        return FileResponse(REPORT_TEMPLATE, filename="3_2_Target_Result_Format.xlsx")

    templates = {
        "raw-input": (expected_columns(), "2_1_Analysis_Input_Template.csv"),
        "database": (load_database_columns(), "3_1_Database_Ingestion_Template.csv"),
    }
    template = templates.get(kind)
    if template is None:
        raise HTTPException(status_code=404, detail="Standard file not found.")

    columns, filename = template
    output = StringIO(newline="")
    csv.writer(output, lineterminator="\r\n").writerow(columns)
    return Response(
        content=output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/analyze")
def analyze(
    file: UploadFile = File(...),
    study_name: str = Form(...),
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    _require_access(authorization)
    if not file.filename or Path(file.filename).suffix.lower() != ".csv":
        raise HTTPException(status_code=415, detail="Upload a CSV file that follows the locked input template.")
    if not study_name.strip():
        raise HTTPException(status_code=422, detail="Study name is required.")

    content = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="CSV upload exceeds the 20 MB limit.")
    raw = _read_uploaded_csv(content)
    dispatcher = load_analysis_dispatcher()
    experiment_type = dispatcher.detect_experiment_type(raw)
    significance = dispatcher.run_significance_by_type(raw, experiment_type)
    report = create_report_payload(raw, significance)
    database_data = transform_database_data(raw, study_name)

    run_id = uuid.uuid4().hex
    run_dir = ARTIFACT_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    report_path = run_dir / "business_report.xlsx"
    database_path = run_dir / "database_ingestion.csv"
    preview_path = run_dir / "preview.json"
    log_path = run_dir / "validation_log.json"

    write_business_report(report, report_path)
    write_database_export(database_data, database_path)
    preview_path.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")

    database_result = persist_if_schema_matches(
        database_data,
        os.getenv("DATABASE_URL"),
        os.getenv("DATABASE_TABLE", "consumer_questionnaire.questionnaire_data"),
    )
    log = {
        "run_id": run_id,
        "input_schema": "passed",
        "input_columns": list(raw.columns),
        "input_rows": int(len(raw)),
        "experiment_type": experiment_type.value,
        "analysis_rows": int(len(significance)),
        "report_rows": len(report["rows"]),
        "database_export_columns": list(database_data.columns),
        "database_export_rows": int(len(database_data)),
        "database": database_result,
    }
    write_validation_log(log, log_path)

    return {
        "run_id": run_id,
        "report": report,
        "validation": log,
        "artifacts": {
            "business_report": f"/api/runs/{run_id}/artifacts/business_report",
            "database_ingestion": f"/api/runs/{run_id}/artifacts/database_ingestion",
            "validation_log": f"/api/runs/{run_id}/artifacts/validation_log",
        },
    }


@app.get("/api/runs/{run_id}")
def get_run(run_id: str) -> dict[str, Any]:
    if not run_id.isalnum():
        raise HTTPException(status_code=404, detail="Report run not found.")
    run_dir = ARTIFACT_DIR / run_id
    try:
        report = json.loads((run_dir / "preview.json").read_text(encoding="utf-8"))
        validation = json.loads((run_dir / "validation_log.json").read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="Report run not found.") from error
    return {"run_id": run_id, "report": report, "validation": validation}


@app.get("/api/runs/{run_id}/artifacts/{kind}")
def get_artifact(run_id: str, kind: str) -> FileResponse:
    if not run_id.isalnum():
        raise HTTPException(status_code=404, detail="Report run not found.")
    names = {
        "business_report": "business_report.xlsx",
        "database_ingestion": "database_ingestion.csv",
        "validation_log": "validation_log.json",
    }
    filename = names.get(kind)
    artifact = ARTIFACT_DIR / run_id / filename if filename else None
    if artifact is None or not artifact.is_file():
        raise HTTPException(status_code=404, detail="Report artifact not found.")
    return FileResponse(artifact, filename=filename)