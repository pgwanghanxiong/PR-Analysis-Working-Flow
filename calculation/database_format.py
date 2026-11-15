from __future__ import annotations

import csv

import pandas as pd

from calculation.input_schema import BASE_DIR, ID_COLUMN, PRODUCT_COLUMN, validate_raw_dataframe


DATABASE_TEMPLATE = BASE_DIR / "3_1_Target Database schema.csv"


def load_database_columns() -> list[str]:
    with DATABASE_TEMPLATE.open("r", encoding="utf-8-sig", newline="") as template:
        return next(csv.reader(template))


def transform_database_data(raw: pd.DataFrame, study_name: str) -> pd.DataFrame:
    validate_raw_dataframe(raw)
    study = study_name.strip()
    if not study:
        raise ValueError("Study name is required to populate the database export.")

    metric_names = pd.Series(raw.columns[2:], dtype="string")
    metric_parts = metric_names.str.extract(r"^Day(\d+)_(.+)$")
    if metric_parts.isna().any(axis=None):
        invalid = metric_names[metric_parts.isna().any(axis=1)].tolist()
        raise ValueError(f"Metric columns do not follow Day{{number}}_{{DQ_name}}: {invalid}")

    long_data = raw.melt(
        id_vars=[ID_COLUMN, PRODUCT_COLUMN],
        value_vars=raw.columns[2:],
        var_name="metric_column",
        value_name="6_Value",
    )
    long_data["6_Value"] = pd.to_numeric(long_data["6_Value"], errors="coerce")
    long_data = long_data.dropna(subset=["6_Value"])
    long_data["1_Study"] = study
    long_data["3_Day"] = long_data["metric_column"].str.extract(r"^Day(\d+)_", expand=False).astype(int)
    long_data["4_Leg"] = long_data[PRODUCT_COLUMN].astype(str).str.strip()
    long_data["5_Dqs"] = long_data["metric_column"].str.replace(r"^Day\d+_", "", regex=True)
    long_data["2_Respondent Serial Number"] = long_data[ID_COLUMN].astype(str)
    return long_data[load_database_columns()].reset_index(drop=True)