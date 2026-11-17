from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path


TEMPLATE_FILE = Path(__file__).resolve().parents[2] / "calculation" / "4_1_Questionnaire Template.csv"
QUESTIONNAIRE_BUILD_COLUMNS = [
    "ID",
    "BU",
    "Category",
    "Variable Code",
    "English Question",
    "Chinese Question",
    "Options",
]
REQUIRED_COLUMNS = QUESTIONNAIRE_BUILD_COLUMNS[:5]
OPTIONAL_COLUMNS = {"Chinese Question", "Options"}


def load_questionnaire_build_columns() -> list[str]:
    with TEMPLATE_FILE.open("r", encoding="utf-8-sig", newline="") as template:
        return next(csv.reader(template, strict=True))


def parse_questionnaire_build_csv(content: bytes) -> list[tuple[object, ...]]:
    try:
        text = content.decode("utf-8-sig")
        rows = csv.reader(StringIO(text, newline=""), strict=True)
        headers = next(rows, None)
    except (UnicodeDecodeError, csv.Error) as error:
        raise ValueError(f"Invalid CSV encoding or syntax: {error}") from error

    expected_headers = load_questionnaire_build_columns()
    if headers != expected_headers:
        raise ValueError(
            "CSV columns must exactly match 4_1_Questionnaire Template.csv in name and order. "
            f"Expected {expected_headers}; received {headers}."
        )

    parsed_rows: list[tuple[object, ...]] = []
    seen_ids: set[int] = set()
    seen_codes: set[str] = set()
    for row_number, values in enumerate(rows, start=2):
        if not values:
            continue
        if len(values) != len(expected_headers):
            raise ValueError(
                f"CSV row {row_number} has {len(values)} fields; expected {len(expected_headers)}."
            )

        record = dict(zip(expected_headers, values))
        for column in REQUIRED_COLUMNS:
            if not record[column].strip():
                raise ValueError(f"CSV row {row_number} has a blank required field '{column}'.")

        raw_id = record["ID"].strip()
        try:
            identifier = int(raw_id)
        except ValueError as error:
            raise ValueError(f"CSV row {row_number} field 'ID' must be an integer.") from error
        if identifier <= 0:
            raise ValueError(f"CSV row {row_number} field 'ID' must be greater than zero.")
        if identifier in seen_ids:
            raise ValueError(f"CSV row {row_number} duplicates ID '{identifier}'.")
        seen_ids.add(identifier)

        variable_code = record["Variable Code"].strip()
        if variable_code in seen_codes:
            raise ValueError(f"CSV row {row_number} duplicates Variable Code '{variable_code}'.")
        seen_codes.add(variable_code)

        parsed_rows.append(
            (
                identifier,
                record["BU"],
                record["Category"],
                variable_code,
                record["English Question"],
                record["Chinese Question"] if record["Chinese Question"].strip() else None,
                record["Options"] if record["Options"].strip() else None,
            )
        )

    if not parsed_rows:
        raise ValueError("CSV contains no questionnaire definition rows.")
    return parsed_rows