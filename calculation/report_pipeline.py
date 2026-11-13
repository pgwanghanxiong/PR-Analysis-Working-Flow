from __future__ import annotations

import csv
import importlib.util
import json
import re
from pathlib import Path
from types import ModuleType
from typing import Any

import numpy as np
import pandas as pd

from calculation.input_schema import (
    BASE_DIR,
    ID_COLUMN,
    PRODUCT_COLUMN,
    validate_raw_dataframe,
)


DATABASE_TEMPLATE = BASE_DIR / "3_1_Target Database schema.csv"
REPORT_TEMPLATE = BASE_DIR / "3_2_Target Result Format.xlsx"
DATABASE_COLUMNS = [
    "1_Study",
    "2_Respondent Serial Number",
    "3_Day",
    "4_Leg",
    "5_Dqs",
    "6_Value",
]
DAY_PATTERN = re.compile(r"^Day(\d+)_(.+)$")
ALPHA = 0.05


def load_database_columns() -> list[str]:
    with DATABASE_TEMPLATE.open("r", encoding="utf-8-sig", newline="") as template:
        return next(csv.reader(template))


def load_analysis_dispatcher() -> ModuleType:
    module_path = BASE_DIR / "2_2_main.py"
    spec = importlib.util.spec_from_file_location("questionnaire_analysis_dispatcher", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load analysis dispatcher: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _abbreviations(products: list[str]) -> dict[str, str]:
    if len(products) > 3:
        raise ValueError(
            f"The supplied PR template supports at most 3 products; received {len(products)}."
        )
    return {product: chr(ord("A") + index) for index, product in enumerate(products)}


def _format_mean(value: float) -> str:
    if not np.isfinite(value):
        return ""
    return f"{value:.2f}".rstrip("0").rstrip(".")


def create_report_payload(
    raw: pd.DataFrame,
    significance: pd.DataFrame,
) -> dict[str, Any]:
    validate_raw_dataframe(raw)
    products = sorted(raw[PRODUCT_COLUMN].astype(str).str.strip().unique().tolist())
    abbreviations = _abbreviations(products)
    sample_sizes = {
        product: int(raw.loc[raw[PRODUCT_COLUMN].astype(str).str.strip() == product, ID_COLUMN].nunique())
        for product in products
    }
    p_values = {
        (str(row.dq), str(row.T1), str(row.T2)): row.P_value
        for row in significance.itertuples(index=False)
    }
    rows: list[dict[str, Any]] = []

    for metric_column in raw.columns[2:]:
        match = DAY_PATTERN.fullmatch(metric_column)
        if match is None:
            raise ValueError(f"Metric column does not follow Day{{number}}_{{DQ_name}}: {metric_column}")
        day_number, question = int(match.group(1)), match.group(2)
        means: dict[str, float | None] = {}
        marks: dict[str, list[str]] = {product: [] for product in products}

        for product in products:
            values = pd.to_numeric(
                raw.loc[raw[PRODUCT_COLUMN].astype(str).str.strip() == product, metric_column],
                errors="coerce",
            ).dropna()
            means[product] = float(values.mean()) if not values.empty else None

        for left_index, left in enumerate(products):
            for right in products[left_index + 1 :]:
                pair_p = p_values.get((metric_column, left, right))
                if pair_p is None:
                    pair_p = p_values.get((metric_column, right, left))
                if pair_p is not None and pd.notna(pair_p) and float(pair_p) < ALPHA:
                    marks[left].append(abbreviations[right])
                    marks[right].append(abbreviations[left])

        product_values = []
        for product in products:
            mean = means[product]
            display = _format_mean(mean) if mean is not None else ""
            if display and marks[product]:
                display = f"{display} {''.join(sorted(marks[product]))}"
            product_values.append(
                {
                    "product": product,
                    "abbreviation": abbreviations[product],
                    "mean": mean,
                    "display": display,
                }
            )

        rows.append(
            {
                "day": f"Day{day_number}",
                "day_number": day_number,
                "question": question,
                "metric_column": metric_column,
                "chinese_description": "",
                "product_values": product_values,
            }
        )

    return {
        "sheet_name": "Rep(All Data)",
        "products": [
            {
                "name": product,
                "abbreviation": abbreviations[product],
                "sample_size": sample_sizes[product],
            }
            for product in products
        ],
        "rows": rows,
    }


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


def write_business_report(payload: dict[str, Any], output_path: Path) -> None:
    from openpyxl import load_workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    workbook = load_workbook(REPORT_TEMPLATE)
    worksheet = workbook["Rep(All Data)"]
    for row in worksheet.iter_rows():
        for cell in row:
            cell.value = None

    for index, product in enumerate(payload["products"], start=1):
        worksheet.cell(1, index, product["name"])
        worksheet.cell(2, index, product["abbreviation"])
        worksheet.cell(3, index, product["sample_size"])

    worksheet.cell(3, 4, "Time Point")
    worksheet.cell(3, 6, "DQ Question")
    worksheet.cell(3, 7, "Chinese Description")
    for row_index, report_row in enumerate(payload["rows"], start=4):
        for product_index, product_value in enumerate(report_row["product_values"], start=1):
            worksheet.cell(row_index, product_index, product_value["display"])
        worksheet.cell(row_index, 4, report_row["day"])
        worksheet.cell(row_index, 6, report_row["question"])
        worksheet.cell(row_index, 7, report_row["chinese_description"])

    header_fill = PatternFill("solid", fgColor="DDEFEA")
    for row_index in range(1, 4):
        for cell in worksheet[row_index]:
            if cell.column <= 7:
                cell.font = Font(bold=True, color="183B36")
                cell.fill = header_fill
                cell.alignment = Alignment(vertical="center")
    worksheet.freeze_panes = "A4"
    worksheet.column_dimensions["A"].width = 18
    worksheet.column_dimensions["B"].width = 18
    worksheet.column_dimensions["C"].width = 18
    worksheet.column_dimensions["D"].width = 14
    worksheet.column_dimensions["E"].width = 3
    worksheet.column_dimensions["F"].width = 48
    worksheet.column_dimensions["G"].width = 32
    output_path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(output_path)


def write_database_export(data: pd.DataFrame, output_path: Path) -> None:
    expected = load_database_columns()
    if list(data.columns) != expected:
        raise ValueError(f"Database export columns mismatch: expected {expected}, got {list(data.columns)}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data.to_csv(output_path, index=False, encoding="utf-8-sig")


def write_validation_log(log: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")