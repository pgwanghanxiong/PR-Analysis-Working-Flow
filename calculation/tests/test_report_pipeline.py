import pandas as pd
import pytest

from calculation.input_schema import expected_columns
from calculation.report_pipeline import (
    create_report_payload,
    load_analysis_dispatcher,
    load_database_columns,
    transform_database_data,
    write_business_report,
)


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


def test_business_report_expands_columns_for_seven_products(tmp_path) -> None:
    columns = expected_columns()
    metric = columns[2]
    raw = pd.DataFrame(
        [[f"ID{index}", f"P{index}", 50 + index] for index in range(1, 8)],
        columns=[columns[0], columns[1], metric],
    )
    significance = pd.DataFrame(
        [
            {"dq": metric, "T1": f"P{index}", "T2": "P7", "P_value": 0.01}
            for index in range(1, 7)
        ]
    )
    report = create_report_payload(raw, significance)
    output_path = tmp_path / "seven_products.xlsx"

    write_business_report(report, output_path)

    from openpyxl import load_workbook

    worksheet = load_workbook(output_path, read_only=True, data_only=True)["Rep(All Data)"]
    assert worksheet["A3"].value == "DQ Question"
    assert worksheet["B3"].value == "Time Point"
    assert worksheet["I1"].value == "P7"
    assert worksheet["I2"].value == "G"
    assert worksheet["I3"].value == 1
    assert worksheet["A4"].value == metric.split("_", 1)[1]
    assert worksheet["B4"].value == "Day1"
    assert worksheet["C4"].value == "51 G"
    assert worksheet["I4"].value == "57 ABCDEF"
    assert all(
        cell.value is None
        for row in worksheet.iter_rows(min_col=10)
        for cell in row
    )


def test_three_product_report_uses_no_extra_columns(tmp_path) -> None:
    columns = expected_columns()
    metric = columns[2]
    raw = pd.DataFrame(
        [["ID1", "P1", 50], ["ID2", "P2", 60], ["ID3", "P3", 70]],
        columns=[columns[0], columns[1], metric],
    )
    report = create_report_payload(raw, pd.DataFrame(columns=["dq", "T1", "T2", "P_value"]))
    output_path = tmp_path / "three_products.xlsx"

    write_business_report(report, output_path)

    from openpyxl import load_workbook

    worksheet = load_workbook(output_path, read_only=True, data_only=True)["Rep(All Data)"]
    assert [worksheet.cell(3, column).value for column in range(1, 6)] == [
        "DQ Question",
        "Time Point",
        1,
        1,
        1,
    ]
    assert all(
        cell.value is None
        for row in worksheet.iter_rows(min_col=6)
        for cell in row
    )


def test_analysis_dispatcher_accepts_more_than_three_products() -> None:
    columns = expected_columns()
    metric = columns[2]
    rows = [
        [f"{product}{respondent}", f"P{product}", 50 + product * 5 + variation]
        for product in range(1, 8)
        for respondent, variation in enumerate((0, 1, 3, 7), start=1)
    ]
    raw = pd.DataFrame(rows, columns=[columns[0], columns[1], metric])
    dispatcher = load_analysis_dispatcher()

    experiment_type = dispatcher.detect_experiment_type(raw)
    significance = dispatcher.run_significance_by_type(raw, experiment_type)
    report = create_report_payload(raw, significance)

    assert experiment_type.value == "independent"
    assert len(significance) == 21
    assert [product["abbreviation"] for product in report["products"]] == list("ABCDEFG")