import pandas as pd

from backend.src.database import compare_database_columns, persist_if_schema_matches
from calculation.report_pipeline import load_database_columns


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