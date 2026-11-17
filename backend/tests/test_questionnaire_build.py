from pathlib import Path
from unittest.mock import MagicMock

import psycopg
import pytest

from backend.src.database import (
    DatabaseSchemaMismatch,
    QUESTIONNAIRE_BUILD_COLUMN_TYPES,
    fetch_questionnaire_build_rows,
    insert_questionnaire_build_rows,
)
from backend.src.questionnaire_build import (
    QUESTIONNAIRE_BUILD_COLUMNS,
    TEMPLATE_FILE,
    parse_questionnaire_build_csv,
)


def test_reference_questionnaire_template_matches_expected_schema() -> None:
    rows = parse_questionnaire_build_csv(TEMPLATE_FILE.read_bytes())

    assert len(rows) == 97
    assert all(len(row) == len(QUESTIONNAIRE_BUILD_COLUMNS) for row in rows)
    assert all(isinstance(row[0], int) for row in rows)


def test_parser_preserves_optional_empty_fields_as_null() -> None:
    content = (
        "ID,BU,Category,Variable Code,English Question,Chinese Question,Options\n"
        "1,BU1,Category A,Q1,Question one,,\n"
    ).encode("utf-8")

    rows = parse_questionnaire_build_csv(content)

    assert rows == [(1, "BU1", "Category A", "Q1", "Question one", None, None)]


def test_parser_rejects_reordered_headers() -> None:
    content = (
        "BU,ID,Category,Variable Code,English Question,Chinese Question,Options\n"
        "BU1,1,Category A,Q1,Question one,,\n"
    ).encode("utf-8")

    with pytest.raises(ValueError, match="exactly match"):
        parse_questionnaire_build_csv(content)


def test_parser_rejects_wrong_field_count_and_non_integer_id() -> None:
    wrong_width = (
        "ID,BU,Category,Variable Code,English Question,Chinese Question,Options\n"
        "1,BU1,Category A,Q1,Question one,\n"
    ).encode("utf-8")
    with pytest.raises(ValueError, match="fields; expected"):
        parse_questionnaire_build_csv(wrong_width)

    wrong_id = (
        "ID,BU,Category,Variable Code,English Question,Chinese Question,Options\n"
        "one,BU1,Category A,Q1,Question one,,\n"
    ).encode("utf-8")
    with pytest.raises(ValueError, match="ID.*integer"):
        parse_questionnaire_build_csv(wrong_id)


def test_parser_rejects_duplicate_primary_and_variable_codes() -> None:
    duplicate_id = (
        "ID,BU,Category,Variable Code,English Question,Chinese Question,Options\n"
        "1,BU1,Category A,Q1,Question one,,\n"
        "1,BU1,Category A,Q2,Question two,,\n"
    ).encode("utf-8")
    with pytest.raises(ValueError, match="duplicates ID"):
        parse_questionnaire_build_csv(duplicate_id)

    duplicate_code = (
        "ID,BU,Category,Variable Code,English Question,Chinese Question,Options\n"
        "1,BU1,Category A,Q1,Question one,,\n"
        "2,BU1,Category A,Q1,Question two,,\n"
    ).encode("utf-8")
    with pytest.raises(ValueError, match="duplicates Variable Code"):
        parse_questionnaire_build_csv(duplicate_code)


def test_database_insert_checks_schema_before_inserting(monkeypatch) -> None:
    expected_schema = [
        ("ID", "integer", "NO"),
        ("BU", "text", "NO"),
        ("Category", "text", "NO"),
        ("Variable Code", "text", "NO"),
        ("English Question", "text", "NO"),
        ("Chinese Question", "text", "YES"),
        ("Options", "text", "YES"),
    ]

    class FakeCursor:
        def __init__(self, schema_rows):
            self.schema_rows = schema_rows
            self.call_count = 0
            self.result_rows = []
            self.inserted_rows = []

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def execute(self, _query, _params=None):
            self.call_count += 1
            self.result_rows = self.schema_rows if self.call_count == 1 else [
                ("PRIMARY KEY", "ID"),
                ("UNIQUE", "Variable Code"),
            ]

        def fetchall(self):
            return self.result_rows

        def executemany(self, _statement, rows):
            self.inserted_rows = list(rows)

    class FakeConnection:
        def __init__(self, cursor):
            self.fake_cursor = cursor

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def cursor(self):
            return self.fake_cursor

    questionnaire_rows = parse_questionnaire_build_csv(TEMPLATE_FILE.read_bytes())
    valid_cursor = FakeCursor(expected_schema)
    monkeypatch.setattr(psycopg, "connect", lambda _url: FakeConnection(valid_cursor))

    inserted = insert_questionnaire_build_rows(questionnaire_rows, "postgresql://test")

    assert inserted == 97
    assert len(valid_cursor.inserted_rows) == 97

    invalid_cursor = FakeCursor(expected_schema[:-1])
    monkeypatch.setattr(psycopg, "connect", lambda _url: FakeConnection(invalid_cursor))
    with pytest.raises(DatabaseSchemaMismatch, match="do not match"):
        insert_questionnaire_build_rows(questionnaire_rows, "postgresql://test")


def test_database_read_orders_by_quoted_id(monkeypatch) -> None:
    cursor = MagicMock()
    rows = [(1, "BU1", "Screen", "Q1", "Question", None, None)]
    cursor.fetchall.side_effect = [QUESTIONNAIRE_BUILD_COLUMN_TYPES, rows]
    connection = MagicMock()
    connection.__enter__.return_value.cursor.return_value.__enter__.return_value = cursor
    monkeypatch.setattr(psycopg, "connect", lambda _url: connection)

    assert fetch_questionnaire_build_rows("postgresql://test") == rows
    assert cursor.execute.call_args.args[0].strip().endswith('ORDER BY "ID"')