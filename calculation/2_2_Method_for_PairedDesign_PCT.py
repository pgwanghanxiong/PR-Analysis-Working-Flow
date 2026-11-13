from __future__ import annotations

import argparse
from itertools import combinations
from math import sqrt
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

try:
    from calculation.input_schema import read_raw_csv, validate_raw_dataframe
except ModuleNotFoundError:
    from input_schema import read_raw_csv, validate_raw_dataframe

OUTPUT_FILE = Path("2_Result_PCT_Python.xlsx")
OUTPUT_SHEET = "2_Result_PCT_Python"


def _paired_vectors(
    df: pd.DataFrame,
    id_col: str,
    product_col: str,
    value_col: str,
    trt1: str,
    trt2: str,
) -> pd.Series:
    pair_df = df[df[product_col].isin([trt1, trt2])][[id_col, product_col, value_col]].copy()
    wide = pair_df.pivot_table(index=id_col, columns=product_col, values=value_col, aggfunc="mean")
    if trt1 not in wide.columns or trt2 not in wide.columns:
        return pd.Series(dtype=float)
    paired = wide[[trt1, trt2]].dropna()
    return paired[trt1] - paired[trt2]


def _wilcoxon_metrics(diff: pd.Series) -> tuple[float, float, float, float, float]:
    median_diff = float(diff.median()) if len(diff) > 0 else np.nan

    non_zero = diff[diff != 0].dropna()
    if len(non_zero) == 0:
        return median_diff, np.nan, np.nan, np.nan, np.nan

    abs_diff = np.abs(non_zero.to_numpy())
    ranks = stats.rankdata(abs_diff, method="average")
    signs = np.sign(non_zero.to_numpy())

    pos_rank_sum = float(ranks[signs > 0].sum())
    neg_rank_sum = float(ranks[signs < 0].sum())

    try:
        res = stats.wilcoxon(
            non_zero.to_numpy(),
            zero_method="wilcox",
            correction=False,
            alternative="two-sided",
            method="approx",
        )
        p_value = float(res.pvalue)
    except Exception:
        p_value = np.nan

    n = len(non_zero)
    mean_w = n * (n + 1) / 4.0
    _, tie_counts = np.unique(abs_diff, return_counts=True)
    tie_term = float(np.sum(tie_counts**3 - tie_counts))
    var_w = n * (n + 1) * (2 * n + 1) / 24.0 - tie_term / 48.0
    z_value = float((pos_rank_sum - mean_w) / sqrt(var_w)) if var_w > 0 else np.nan

    return median_diff, pos_rank_sum, neg_rank_sum, z_value, p_value


def run_significance_analysis(raw: pd.DataFrame) -> pd.DataFrame:
    validate_raw_dataframe(raw)
    id_col = raw.columns[0]
    product_col = raw.columns[1]
    dq_cols = list(raw.columns[2:])

    data = raw[[id_col, product_col] + dq_cols].copy()
    data[product_col] = data[product_col].astype(str).str.strip()
    products = sorted(data[product_col].dropna().unique().tolist())
    pairs = list(combinations(products, 2))

    records: list[dict[str, float | str]] = []

    for dq in dq_cols:
        sub = data[[id_col, product_col, dq]].copy()
        sub[dq] = pd.to_numeric(sub[dq], errors="coerce")
        sub = sub.dropna(subset=[id_col, product_col, dq])

        for trt1, trt2 in pairs:
            diff = _paired_vectors(sub, id_col, product_col, dq, trt1, trt2)
            n = int(len(diff))

            if n >= 2:
                mean_diff = float(diff.mean())
                sd_diff = float(diff.std(ddof=1))
                sem = float(sd_diff / sqrt(n))
                _, p_value = stats.ttest_1samp(diff.to_numpy(), popmean=0.0, nan_policy="omit")
                p_value = float(p_value)
            else:
                mean_diff = np.nan
                sd_diff = np.nan
                sem = np.nan
                p_value = np.nan

            (
                wil_median_diff,
                wil_pos_sum,
                wil_neg_sum,
                wil_z,
                wil_p,
            ) = _wilcoxon_metrics(diff)

            records.append(
                {
                    "dq": dq,
                    "T1": trt1,
                    "T2": trt2,
                    "P_value": p_value,
                    "mean_difference": mean_diff,
                    "standard_error": sem,
                    "Paired_Sample_N": n,
                    "T_Mean_Difference": mean_diff,
                    "T_Difference_SD": sd_diff,
                    "T_SEM": sem,
                    "Wilcoxon_Median_Difference": wil_median_diff,
                    "Wilcoxon_Positive_Rank_Sum": wil_pos_sum,
                    "Wilcoxon_Negative_Rank_Sum": wil_neg_sum,
                    "Wilcoxon_Z_statistic": wil_z,
                    "Wilcoxon_p_value": wil_p,
                }
            )

    result = pd.DataFrame.from_records(records)
    result = result[["dq", "T1", "T2", "P_value"]]
    return result


def main(input_file: Path) -> None:
    raw = read_raw_csv(input_file)
    result = run_significance_analysis(raw)

    with pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl") as writer:
        result.to_excel(writer, sheet_name=OUTPUT_SHEET, index=False)

    print(f"Saved result to: {OUTPUT_FILE.resolve()}")
    print(f"Rows: {len(result)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run paired-design analysis on a raw CSV.")
    parser.add_argument("input_csv", type=Path, help="Path to the raw questionnaire CSV.")
    main(parser.parse_args().input_csv)
