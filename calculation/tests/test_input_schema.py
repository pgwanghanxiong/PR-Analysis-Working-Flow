from pathlib import Path

import pandas as pd
import pytest

from calculation.input_schema import RAW_SCHEMA_FILE, expected_columns, read_raw_csv, validate_raw_dataframe


ROOT = Path(__file__).resolve().parents[2]


def valid_frame() -> pd.DataFrame:
    columns = expected_columns()
    return pd.DataFrame(
        [["001", "P1", *([75] * (len(expected_columns()) - 2))]],
        columns=columns,
    )


def test_header_only_schema_has_locked_columns_and_loads() -> None:
    data = read_raw_csv(RAW_SCHEMA_FILE)

    assert list(data.columns) == expected_columns()
    assert data.empty
    assert data["2_Respondent Serial Number"].dtype.name == "string"


def test_rejects_reordered_columns() -> None:
    data = valid_frame().iloc[:, ::-1]

    with pytest.raises(ValueError, match="locked template"):
        validate_raw_dataframe(data)


def test_rejects_non_numeric_metric() -> None:
    data = valid_frame()
    metric_column = data.columns[2]
    data[metric_column] = data[metric_column].astype(object)
    data.iloc[0, 2] = "not-a-score"

    with pytest.raises(ValueError, match="non-numeric"):
        validate_raw_dataframe(data)