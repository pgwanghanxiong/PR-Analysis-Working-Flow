import pandas as pd
import pytest

from backend.src.ingestion import LONG_COLUMNS, long_rows_to_analysis_wide, normalize_uploaded_csv
from calculation.input_schema import expected_columns
from calculation.report_pipeline import create_report_payload, load_analysis_dispatcher


def csv_bytes(data: pd.DataFrame) -> bytes:
    return data.to_csv(index=False).encode("utf-8")


def test_long_format_is_normalized_without_changing_study_name() -> None:
    data = pd.DataFrame(
        [["Study A", "001", "1", "Product A", "Question A", "72"]],
        columns=LONG_COLUMNS,
    )

    normalized, upload_format = normalize_uploaded_csv(csv_bytes(data))

    assert upload_format == "long"
    assert list(normalized.columns) == LONG_COLUMNS
    assert normalized.iloc[0].to_dict() == {
        "1_Study": "Study A",
        "2_Respondent Serial Number": "001",
        "3_Day": 1,
        "4_Leg": "Product A",
        "5_Dqs": "Question A",
        "6_Value": 72,
    }


def test_wide_format_extracts_day_and_question_and_adds_study_name() -> None:
    columns = expected_columns()
    rows = [
        [respondent_id, product, *([score] * (len(columns) - 2))]
        for respondent_id, product, score in (
            ("A001", "A", 60),
            ("A002", "A", 61),
            ("A003", "B", 80),
            ("A004", "B", 82),
        )
    ]
    data = pd.DataFrame(rows, columns=columns)

    normalized, upload_format = normalize_uploaded_csv(csv_bytes(data), "Wide Study")

    assert upload_format == "wide"
    assert list(normalized.columns) == LONG_COLUMNS
    assert normalized["1_Study"].eq("Wide Study").all()
    first_metric = columns[2]
    assert normalized.iloc[0]["3_Day"] == int(first_metric.split("_", 1)[0][3:])
    assert normalized.iloc[0]["5_Dqs"] == first_metric.split("_", 1)[1]


def test_wide_format_requires_study_name() -> None:
    columns = expected_columns()
    data = pd.DataFrame(
        [["A001", "A", *([70] * (len(columns) - 2))]],
        columns=columns,
    )

    with pytest.raises(ValueError, match="Study Name is required"):
        normalize_uploaded_csv(csv_bytes(data))


def test_stored_study_with_metric_subset_runs_existing_analysis_and_report() -> None:
    columns = expected_columns()
    metric_columns = [columns[2], columns[5]]
    rows = []
    for respondent_id, product, score, variation in (
        ("A001", "A", 60, 0),
        ("A002", "A", 60, 2),
        ("A003", "A", 60, 5),
        ("A004", "A", 60, 9),
        ("B001", "B", 80, 0),
        ("B002", "B", 80, 3),
        ("B003", "B", 80, 6),
        ("B004", "B", 80, 10),
    ):
        for metric_index, metric_column in enumerate(metric_columns):
            day, question = metric_column.split("_", 1)
            rows.append(
                {
                    "1_Study": "Study A",
                    "2_Respondent Serial Number": respondent_id,
                    "3_Day": int(day[3:]),
                    "4_Leg": product,
                    "5_Dqs": question,
                    "6_Value": score + variation + metric_index,
                }
            )

    wide = long_rows_to_analysis_wide(pd.DataFrame(rows, columns=LONG_COLUMNS))
    dispatcher = load_analysis_dispatcher()
    experiment_type = dispatcher.detect_experiment_type(wide)
    significance = dispatcher.run_significance_by_type(wide, experiment_type)
    report = create_report_payload(wide, significance)

    assert list(wide.columns) == [*columns[:2], *metric_columns]
    assert len(wide) == 8
    assert set(significance["dq"]) == set(metric_columns)
    assert len(report["rows"]) == len(metric_columns)
    assert report["rows"][0]["question"] == metric_columns[0].split("_", 1)[1]