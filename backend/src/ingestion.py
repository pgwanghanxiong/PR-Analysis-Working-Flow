from __future__ import annotations

from io import BytesIO

import numpy as np
import pandas as pd

from calculation.input_schema import (
    ID_COLUMN,
    PRODUCT_COLUMN,
    expected_columns,
    validate_raw_dataframe,
)
from calculation.database_format import transform_database_data


LONG_COLUMNS = [
    "1_Study",
    "2_Respondent Serial Number",
    "3_Day",
    "4_Leg",
    "5_Dqs",
    "6_Value",
]
LONG_OPTIONAL_COLUMNS = {"id", "created_by", "updated_by", "created_at", "updated_at"}


def normalize_uploaded_csv(content: bytes, study_name: str | None = None) -> tuple[pd.DataFrame, str]:
    data = pd.read_csv(
        BytesIO(content),
        dtype={ID_COLUMN: "string", "1_Study": "string"},
    )
    columns = list(data.columns)

    if columns == expected_columns():
        normalized_study = (study_name or "").strip()
        if not normalized_study:
            raise ValueError("Study Name is required when uploading Wide format data.")
        validate_raw_dataframe(data)
        return transform_database_data(data, normalized_study), "wide"

    required = set(LONG_COLUMNS)
    missing = [column for column in LONG_COLUMNS if column not in columns]
    unexpected = [
        column for column in columns if column not in required and column not in LONG_OPTIONAL_COLUMNS
    ]
    if missing or unexpected:
        raise ValueError(
            "CSV must match either the locked Wide input schema or the Long database format. "
            f"Missing Long columns: {missing}; unexpected columns: {unexpected}."
        )

    normalized = data[LONG_COLUMNS].copy()
    for column in LONG_COLUMNS:
        if normalized[column].isna().any():
            raise ValueError(f"Long format column '{column}' contains blank values.")
        if normalized[column].astype(str).str.strip().eq("").any():
            raise ValueError(f"Long format column '{column}' contains blank values.")

    days = pd.to_numeric(normalized["3_Day"], errors="coerce")
    if days.isna().any() or (days < 0).any() or (days % 1 != 0).any():
        raise ValueError("Long format column '3_Day' must contain non-negative whole numbers.")
    normalized["3_Day"] = days.astype("int64")

    values = pd.to_numeric(normalized["6_Value"], errors="coerce")
    if values.isna().any() or not np.isfinite(values.to_numpy(dtype=float)).all():
        raise ValueError("Long format column '6_Value' must contain finite numeric values.")
    normalized["6_Value"] = values
    normalized["1_Study"] = normalized["1_Study"].astype(str).str.strip()
    normalized["2_Respondent Serial Number"] = normalized["2_Respondent Serial Number"].astype(str)
    normalized["4_Leg"] = normalized["4_Leg"].astype(str).str.strip()
    normalized["5_Dqs"] = normalized["5_Dqs"].astype(str).str.strip()
    if normalized.empty:
        raise ValueError("CSV contains no questionnaire rows to upload.")
    return normalized, "long"