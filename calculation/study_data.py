from __future__ import annotations

import pandas as pd

from calculation.input_schema import (
    ID_COLUMN,
    PRODUCT_COLUMN,
    expected_columns,
    validate_analysis_dataframe,
)


def long_rows_to_analysis_wide(data: pd.DataFrame) -> pd.DataFrame:
    if data.empty:
        raise ValueError("No questionnaire rows were found for this Study Name.")

    long_data = data.copy()
    long_data["_metric"] = (
        "Day"
        + pd.to_numeric(long_data["3_Day"], errors="raise").astype(int).astype(str)
        + "_"
        + long_data["5_Dqs"].astype(str)
    )
    available_metrics = set(long_data["_metric"].drop_duplicates().tolist())
    template_metrics = [metric for metric in expected_columns()[2:] if metric in available_metrics]
    additional_metrics = sorted(
        available_metrics - set(template_metrics),
        key=lambda metric: (int(metric.split("_", 1)[0][3:]), metric.split("_", 1)[1].casefold()),
    )
    metric_columns = [*template_metrics, *additional_metrics]

    wide = long_data.pivot_table(
        index=[ID_COLUMN, PRODUCT_COLUMN],
        columns="_metric",
        values="6_Value",
        aggfunc="mean",
    ).reset_index()
    wide.columns.name = None
    wide = wide.reindex(columns=[ID_COLUMN, PRODUCT_COLUMN, *metric_columns])
    return validate_analysis_dataframe(wide)