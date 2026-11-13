from __future__ import annotations

import csv
import re
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
RAW_SCHEMA_FILE = BASE_DIR / "2_1_Analysis Input schema.csv"
ID_COLUMN = "2_Respondent Serial Number"
PRODUCT_COLUMN = "4_Leg"
DAY_COLUMN_PATTERN = re.compile(r"^Day\d+_.+")


def expected_columns() -> list[str]:
    with RAW_SCHEMA_FILE.open("r", encoding="utf-8-sig", newline="") as template:
        return next(csv.reader(template))


def validate_raw_dataframe(data: pd.DataFrame) -> pd.DataFrame:
    expected = expected_columns()
    actual = list(data.columns)
    if actual != expected:
        raise ValueError(
            "Raw input columns do not match the locked template. "
            f"Expected {expected}; received {actual}."
        )

    invalid_day_columns = [
        column for column in expected[2:] if DAY_COLUMN_PATTERN.fullmatch(column) is None
    ]
    if invalid_day_columns:
        raise ValueError(
            "DQ columns must use the Day{number}_{DQ_name} convention: "
            f"{invalid_day_columns}"
        )

    for column in (ID_COLUMN, PRODUCT_COLUMN):
        values = data[column]
        if values.isna().any() or values.astype(str).str.strip().eq("").any():
            raise ValueError(f"Raw input column '{column}' contains blank values.")

    for column in expected[2:]:
        numeric = pd.to_numeric(data[column], errors="coerce")
        invalid_values = data[column].notna() & numeric.isna()
        if invalid_values.any():
            raise ValueError(f"DQ column '{column}' contains non-numeric values.")

    return data


def read_raw_csv(path: Path) -> pd.DataFrame:
    data = pd.read_csv(path, dtype={ID_COLUMN: "string", PRODUCT_COLUMN: "string"})
    return validate_raw_dataframe(data)