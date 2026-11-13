from __future__ import annotations

import argparse
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

try:
    from calculation.input_schema import read_raw_csv, validate_raw_dataframe
except ModuleNotFoundError:
    from input_schema import read_raw_csv, validate_raw_dataframe

OUTPUT_FILE = Path("2_Result_SPBT_Python.xlsx")
ALPHA = 0.05


def _to_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").dropna()


def _student_pvalue(group1: pd.Series, group2: pd.Series) -> float:
    _, p = stats.ttest_ind(group1, group2, equal_var=True, nan_policy="omit")
    return float(p)


def _welch_pvalue(group1: pd.Series, group2: pd.Series) -> float:
    _, p = stats.ttest_ind(group1, group2, equal_var=False, nan_policy="omit")
    return float(p)


def _is_normal_shapiro(group: pd.Series) -> bool:
    if len(group) < 3:
        return False
    _, p = stats.shapiro(group)
    return bool(p >= ALPHA)


def _has_equal_variance(group1: pd.Series, group2: pd.Series) -> bool:
    if len(group1) < 2 or len(group2) < 2:
        return False
    _, p = stats.levene(group1, group2, center="median")
    return bool(p >= ALPHA)


def _adaptive_pvalue(group1: pd.Series, group2: pd.Series) -> float:
    normal_1 = _is_normal_shapiro(group1)
    normal_2 = _is_normal_shapiro(group2)
    equal_var = _has_equal_variance(group1, group2)

    if normal_1 and normal_2 and equal_var:
        return _student_pvalue(group1, group2)
    return _welch_pvalue(group1, group2)


def run_significance_analysis(raw_df: pd.DataFrame) -> pd.DataFrame:
    validate_raw_dataframe(raw_df)
    id_col = raw_df.columns[0]
    product_col = raw_df.columns[1]
    dq_cols = list(raw_df.columns[2:])

    data = raw_df[[id_col, product_col] + dq_cols].copy()
    data[product_col] = data[product_col].astype(str).str.strip()

    products = sorted(data[product_col].dropna().unique().tolist())
    if len(products) < 2:
        raise ValueError(
            f"Expected at least 2 products in column '{product_col}', found: {products}"
        )

    pairs = list(combinations(products, 2))
    records: list[dict[str, float | str]] = []

    for dq in dq_cols:
        for p1, p2 in pairs:
            g1 = data.loc[data[product_col] == p1, dq]
            g2 = data.loc[data[product_col] == p2, dq]
            series_1 = _to_numeric(g1)
            series_2 = _to_numeric(g2)

            if len(series_1) < 2 or len(series_2) < 2:
                student_p = np.nan
                welch_p = np.nan
                adaptive_p = np.nan
            else:
                student_p = _student_pvalue(series_1, series_2)
                welch_p = _welch_pvalue(series_1, series_2)
                adaptive_p = _adaptive_pvalue(series_1, series_2)

            records.append(
                {
                    "dq": dq,
                    "T1": p1,
                    "T2": p2,
                    "Student_t_p": student_p,
                    "Welch_t_p": welch_p,
                    "Adaptive_t_p": adaptive_p,
                }
            )

    result = pd.DataFrame.from_records(records)
    result = result[["dq", "T1", "T2", "Welch_t_p"]].rename(columns={"Welch_t_p": "P_value"})
    return result


def main(input_file: Path) -> None:
    df = read_raw_csv(input_file)
    result = run_significance_analysis(df)

    with pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl") as writer:
        result.to_excel(writer, sheet_name="2_Result_SPBT_Python", index=False)

    print(f"Saved result to: {OUTPUT_FILE.resolve()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run independent-design analysis on a raw CSV.")
    parser.add_argument("input_csv", type=Path, help="Path to the raw questionnaire CSV.")
    main(parser.parse_args().input_csv)
