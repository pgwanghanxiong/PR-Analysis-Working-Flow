import pandas as pd
import psycopg
import pytest

from backend.src.database import (
    DatabaseSchemaMismatch,
    compare_database_columns,
    get_postgres_study_names,
    get_study_rows,
    insert_uploaded_rows,
    persist_if_schema_matches,
)
from calculation.report_pipeline import load_database_columns


class FakeCursor:
    def __init__(self, table_columns: list[str], rows: list[tuple] | None = None):
        self.table_columns = table_columns
        self.query_rows = rows or []
        self.result_rows = []
        self.execute_count = 0
        self.inserted_rows = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def execute(self, _query, _params=None):
        self.execute_count += 1
        self.result_rows = (
            [(column,) for column in self.table_columns]
            if self.execute_count == 1
            else self.query_rows
        )

    def executemany(self, _statement, rows):
        self.inserted_rows = list(rows)

    def fetchall(self):
        return self.result_rows


class FakeConnection:
    def __init__(self, cursor: FakeCursor):
        self.fake_cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def cursor(self):
        return self.fake_cursor


def test_target_database_columns_match_reference_csv() -> None:
    assert compare_database_columns(load_database_columns())["matches"]


def test_extra_database_column_blocks_ingestion() -> None:
    actual = load_database_columns() + ["created_at"]

    result = compare_database_columns(actual)

    assert not result["matches"]


def test_missing_database_url_warns_and_skips_insert() -> None:
    result = persist_if_schema_matches(
        pd.DataFrame(columns=load_database_columns()),
        database_url=None,
        table_name="consumer_questionnaire.questionnaire_data",
    )

    assert result["status"] == "warning"
    assert "does not match the six-column target CSV" in result["message"]


def test_upload_insert_accepts_managed_columns_and_inserts_business_rows(monkeypatch) -> None:
    table_columns = ["id", *load_database_columns(), "created_by", "updated_by", "created_at", "updated_at"]
    cursor = FakeCursor(table_columns)
    monkeypatch.setattr(psycopg, "connect", lambda _database_url: FakeConnection(cursor))
    data = pd.DataFrame(
        [["Study A", "001", 1, "Product A", "Question A", 72]],
        columns=load_database_columns(),
    )

    inserted = insert_uploaded_rows(data, "postgresql://test", "consumer_questionnaire.questionnaire_data")

    assert inserted == 1
    assert cursor.inserted_rows == [("Study A", "001", 1, "Product A", "Question A", 72)]


def test_upload_insert_rejects_mismatched_target_columns(monkeypatch) -> None:
    cursor = FakeCursor(["id", "1_Study", "2_Respondent Serial Number"])
    monkeypatch.setattr(psycopg, "connect", lambda _database_url: FakeConnection(cursor))
    data = pd.DataFrame(columns=load_database_columns())
    data.loc[0] = ["Study A", "001", 1, "Product A", "Question A", 72]

    with pytest.raises(DatabaseSchemaMismatch, match="must contain business columns"):
        insert_uploaded_rows(data, "postgresql://test", "consumer_questionnaire.questionnaire_data")


def test_study_queries_read_from_postgres(monkeypatch) -> None:
    names_cursor = FakeCursor(
        ["id", *load_database_columns(), "created_by", "updated_by", "created_at", "updated_at"],
        rows=[("Study A",), ("Study B",)],
    )
    monkeypatch.setattr(psycopg, "connect", lambda _database_url: FakeConnection(names_cursor))

    names = get_postgres_study_names("postgresql://test", "consumer_questionnaire.questionnaire_data")

    assert names == ["Study A", "Study B"]

    rows_cursor = FakeCursor(
        ["id", *load_database_columns(), "created_by", "updated_by", "created_at", "updated_at"],
        rows=[("Study A", "001", 1, "Product A", "Question A", 72)],
    )
    monkeypatch.setattr(psycopg, "connect", lambda _database_url: FakeConnection(rows_cursor))

    rows = get_study_rows("postgresql://test", "consumer_questionnaire.questionnaire_data", "Study A")

    assert rows.to_dict(orient="records") == [
        {
            "1_Study": "Study A",
            "2_Respondent Serial Number": "001",
            "3_Day": 1,
            "4_Leg": "Product A",
            "5_Dqs": "Question A",
            "6_Value": 72,
        }
    ]