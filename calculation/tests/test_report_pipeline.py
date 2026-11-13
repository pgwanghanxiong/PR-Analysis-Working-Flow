import pandas as pd
import pytest

from calculation.input_schema import expected_columns
from calculation.report_pipeline import create_report_payload, load_database_columns, transform_database_data


def make_raw() -> pd.DataFrame:
    columns = expected_columns()
    row_a = ["001", "P1", *([10] * (len(columns) - 2))]
    row_b = ["002", "P2", *([20] * (len(columns) - 2))]
    return pd.DataFrame([row_a, row_b], columns=columns)


def test_database_transform_matches_reference_schema_and_keeps_day_number() -> None:
    raw = make_raw()

    result = transform_database_data(raw, "Study 1")

    assert list(result.columns) == load_database_columns()
    assert result.iloc[0]["2_Respondent Serial Number"] == "001"
    assert result.iloc[0]["3_Day"] == 1
    assert result.iloc[0]["5_Dqs"]


def test_business_report_uses_day_labels_and_comparison_abbreviations() -> None:
    raw = make_raw()
    metric = expected_columns()[2]
    significance = pd.DataFrame(
        [{"dq": metric, "T1": "P1", "T2": "P2", "P_value": 0.01}]
    )

    result = create_report_payload(raw, significance)
    first_row = result["rows"][0]

    assert result["products"][0]["abbreviation"] == "A"
    assert first_row["day"] == "Day1"
    assert first_row["product_values"][0]["display"] == "10 B"
    assert first_row["product_values"][1]["display"] == "20 A"


def test_database_transform_requires_study_name() -> None:
    with pytest.raises(ValueError, match="Study name is required"):
        transform_database_data(make_raw(), " ")