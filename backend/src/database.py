from __future__ import annotations

import re
from typing import Any

import pandas as pd

from calculation.report_pipeline import load_database_columns


IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
LONG_COLUMNS = [
    "1_Study",
    "2_Respondent Serial Number",
    "3_Day",
    "4_Leg",
    "5_Dqs",
    "6_Value",
]


class DatabaseUnavailable(RuntimeError):
    pass


class DatabaseSchemaMismatch(RuntimeError):
    pass


def _validated_table_name(table_name: str) -> tuple[str, str]:
    parts = table_name.split(".")
    if len(parts) != 2 or any(IDENTIFIER_PATTERN.fullmatch(part) is None for part in parts):
        raise ValueError("DATABASE_TABLE must be a schema-qualified PostgreSQL identifier (schema.table).")
    return parts[0], parts[1]


def _validate_questionnaire_table(cursor: Any, schema: str, table: str) -> None:
    cursor.execute(
        """SELECT column_name
           FROM information_schema.columns
           WHERE table_schema = %s AND table_name = %s
           ORDER BY ordinal_position""",
        (schema, table),
    )
    actual_columns = [row[0] for row in cursor.fetchall()]
    business_columns = [column for column in actual_columns if column in LONG_COLUMNS]
    if business_columns != LONG_COLUMNS:
        raise DatabaseSchemaMismatch(
            f"PostgreSQL table {schema}.{table} must contain business columns in this order: {LONG_COLUMNS}; "
            f"found: {business_columns}."
        )


def insert_uploaded_rows(data: pd.DataFrame, database_url: str | None, table_name: str) -> int:
    if not database_url:
        raise DatabaseUnavailable("DATABASE_URL is not configured; PostgreSQL upload was not performed.")
    if list(data.columns) != LONG_COLUMNS:
        raise ValueError(f"Upload data must have columns {LONG_COLUMNS}.")
    if data.empty:
        raise ValueError("The uploaded file contains no questionnaire rows.")
    schema, table = _validated_table_name(table_name)

    import psycopg
    from psycopg import sql

    columns = sql.SQL(", ").join(sql.Identifier(column) for column in LONG_COLUMNS)
    placeholders = sql.SQL(", ").join(sql.Placeholder() for _ in LONG_COLUMNS)
    statement = sql.SQL("INSERT INTO {}.{} ({}) VALUES ({})").format(
        sql.Identifier(schema),
        sql.Identifier(table),
        columns,
        placeholders,
    )
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            _validate_questionnaire_table(cursor, schema, table)
            cursor.executemany(statement, data.itertuples(index=False, name=None))
    return len(data)


def get_postgres_study_names(database_url: str | None, table_name: str) -> list[str]:
    if not database_url:
        raise DatabaseUnavailable("DATABASE_URL is not configured.")
    schema, table = _validated_table_name(table_name)

    import psycopg
    from psycopg import sql

    query = sql.SQL(
        'SELECT DISTINCT "1_Study" FROM {}.{} '
        'WHERE "1_Study" IS NOT NULL AND btrim("1_Study") <> \'\' ORDER BY "1_Study"'
    ).format(sql.Identifier(schema), sql.Identifier(table))
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            _validate_questionnaire_table(cursor, schema, table)
            cursor.execute(query)
            return [str(row[0]).strip() for row in cursor.fetchall()]


def get_study_rows(database_url: str | None, table_name: str, study_name: str) -> pd.DataFrame:
    if not database_url:
        raise DatabaseUnavailable("DATABASE_URL is not configured.")
    schema, table = _validated_table_name(table_name)

    import psycopg
    from psycopg import sql

    columns = sql.SQL(", ").join(sql.Identifier(column) for column in LONG_COLUMNS)
    query = sql.SQL(
        'SELECT {} FROM {}.{} WHERE "1_Study" = %s '
        'ORDER BY "2_Respondent Serial Number", "3_Day", "4_Leg", "5_Dqs"'
    ).format(columns, sql.Identifier(schema), sql.Identifier(table))
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            _validate_questionnaire_table(cursor, schema, table)
            cursor.execute(query, (study_name,))
            rows = cursor.fetchall()
    return pd.DataFrame.from_records(rows, columns=LONG_COLUMNS)


def insert_questionnaire_rows(
    data: pd.DataFrame,
    database_url: str | None,
    table_name: str,
) -> int:
    if not database_url:
        raise DatabaseUnavailable("DATABASE_URL is not configured; upload was not saved.")
    if list(data.columns) != LONG_COLUMNS:
        raise ValueError(f"Upload rows must have columns {LONG_COLUMNS}, received {list(data.columns)}.")
    if data.empty:
        raise ValueError("The uploaded file contains no questionnaire rows.")
    schema, table = _validated_table_name(table_name)

    import psycopg
    from psycopg import sql

    columns = sql.SQL(", ").join(sql.Identifier(column) for column in LONG_COLUMNS)
    placeholders = sql.SQL(", ").join(sql.Placeholder() for _ in LONG_COLUMNS)
    statement = sql.SQL("INSERT INTO {}.{} ({}) VALUES ({})").format(
        sql.Identifier(schema),
        sql.Identifier(table),
        columns,
        placeholders,
    )
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            _validate_questionnaire_table(cursor, schema, table)
            cursor.executemany(statement, data.itertuples(index=False, name=None))
    return len(data)


def fetch_study_names(database_url: str | None, table_name: str) -> list[str]:
    if not database_url:
        raise DatabaseUnavailable("DATABASE_URL is not configured.")
    schema, table = _validated_table_name(table_name)

    import psycopg
    from psycopg import sql

    query = sql.SQL(
        'SELECT DISTINCT "1_Study" FROM {}.{} '
        'WHERE "1_Study" IS NOT NULL AND btrim("1_Study") <> \'\' ORDER BY "1_Study"'
    ).format(sql.Identifier(schema), sql.Identifier(table))
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            _validate_questionnaire_table(cursor, schema, table)
            cursor.execute(query)
            return [str(row[0]).strip() for row in cursor.fetchall()]


def fetch_study_rows(database_url: str | None, table_name: str, study_name: str) -> pd.DataFrame:
    if not database_url:
        raise DatabaseUnavailable("DATABASE_URL is not configured.")
    schema, table = _validated_table_name(table_name)

    import psycopg
    from psycopg import sql

    columns = sql.SQL(", ").join(sql.Identifier(column) for column in LONG_COLUMNS)
    query = sql.SQL(
        'SELECT {} FROM {}.{} WHERE "1_Study" = %s '
        'ORDER BY "2_Respondent Serial Number", "3_Day", "4_Leg", "5_Dqs"'
    ).format(columns, sql.Identifier(schema), sql.Identifier(table))
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            _validate_questionnaire_table(cursor, schema, table)
            cursor.execute(query, (study_name,))
            rows = cursor.fetchall()
    return pd.DataFrame.from_records(rows, columns=LONG_COLUMNS)


def compare_database_columns(actual: list[str], expected: list[str] | None = None) -> dict[str, Any]:
    expected_columns = expected or load_database_columns()
    return {
        "matches": actual == expected_columns,
        "expected": expected_columns,
        "actual": actual,
    }


def persist_if_schema_matches(
    data: pd.DataFrame,
    database_url: str | None,
    table_name: str,
) -> dict[str, Any]:
    expected = load_database_columns()
    if list(data.columns) != expected:
        return {
            "status": "warning",
            "message": f"Export column mismatch; insert skipped. Expected {expected}, received {list(data.columns)}.",
        }
    if not database_url:
        return {
            "status": "warning",
            "message": (
                "DATABASE_URL is not configured; PostgreSQL schema validation and insert were skipped. "
                f"The repository definition of the default table {table_name} includes management "
                "columns and does not match the six-column target CSV. Configure a target table "
                "with the exact 3_1 column order before loading."
            ),
        }

    parts = table_name.split(".")
    if len(parts) != 2 or any(IDENTIFIER_PATTERN.fullmatch(part) is None for part in parts):
        return {
            "status": "warning",
            "message": "DATABASE_TABLE must be a schema-qualified PostgreSQL identifier (schema.table).",
        }
    schema, table = parts

    try:
        import psycopg
        from psycopg import sql

        with psycopg.connect(database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """SELECT column_name
                       FROM information_schema.columns
                       WHERE table_schema = %s AND table_name = %s
                       ORDER BY ordinal_position""",
                    (schema, table),
                )
                actual = [row[0] for row in cursor.fetchall()]
                comparison = compare_database_columns(actual, expected)
                if not comparison["matches"]:
                    return {
                        "status": "warning",
                        "message": (
                            f"PostgreSQL table {schema}.{table} columns do not match the target CSV; "
                            "insert skipped. No schema changes were made."
                        ),
                        **comparison,
                    }
                if data.empty:
                    return {
                        "status": "skipped",
                        "message": "PostgreSQL schema matches, but there are no rows to insert.",
                        **comparison,
                    }
                columns = sql.SQL(", ").join(sql.Identifier(column) for column in expected)
                placeholders = sql.SQL(", ").join(sql.Placeholder() for _ in expected)
                statement = sql.SQL("INSERT INTO {}.{} ({}) VALUES ({})").format(
                    sql.Identifier(schema),
                    sql.Identifier(table),
                    columns,
                    placeholders,
                )
                cursor.executemany(statement, data.itertuples(index=False, name=None))
                inserted = len(data)
        return {
            "status": "loaded",
            "message": f"Inserted {inserted} rows into {schema}.{table}.",
            "inserted_rows": inserted,
            **comparison,
        }
    except Exception as error:
        return {
            "status": "warning",
            "message": f"PostgreSQL insert failed: {type(error).__name__}: {error}",
        }