from __future__ import annotations

from typing import Any

import pandas as pd


IDENTITY_COLUMNS = [
    "1_Study",
    "2_Respondent Serial Number",
    "3_Day",
    "4_Leg",
]


def build_wide_view(data: pd.DataFrame) -> dict[str, Any]:
    questions = sorted(data["5_Dqs"].unique().tolist(), key=lambda value: (str(value).casefold(), str(value)))
    records: dict[tuple[str, str, int, str], dict[str, list[str]]] = {}
    duplicate_cells = 0
    for study, respondent, day, leg, question, value in data[
        [*IDENTITY_COLUMNS, "5_Dqs", "6_Value"]
    ].itertuples(index=False, name=None):
        key = (str(study), str(respondent), int(day), str(leg))
        cells = records.setdefault(key, {})
        values = cells.setdefault(str(question), [])
        if len(values) == 1:
            duplicate_cells += 1
        values.append(str(value))

    rows = [
        [*key, *(cells.get(str(question), []) for question in questions)]
        for key, cells in records.items()
    ]
    return {
        "columns": [*IDENTITY_COLUMNS, *(str(question) for question in questions)],
        "rows": rows,
        "duplicate_cells": duplicate_cells,
    }