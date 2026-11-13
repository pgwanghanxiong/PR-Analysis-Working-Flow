from __future__ import annotations

import re
from typing import Any

import pandas as pd

from calculation.report_pipeline import load_database_columns


IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


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