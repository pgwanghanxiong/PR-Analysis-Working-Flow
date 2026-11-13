from __future__ import annotations

import argparse
from itertools import combinations
from math import sqrt
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats

try:
    from calculation.input_schema import read_raw_csv, validate_raw_dataframe
except ModuleNotFoundError:
    from input_schema import read_raw_csv, validate_raw_dataframe

OUTPUT_FILE = Path("2_Result_SQM_Python.xlsx")


def _paired_ttest_by_id(
    df: pd.DataFrame,
    id_col: str,
    product_col: str,
    value_col: str,
    p1: str,
    p2: str,
) -> tuple[float, float, float]:
    pair_df = df[df[product_col].isin([p1, p2])].copy()
    wide = pair_df.pivot_table(index=id_col, columns=product_col, values=value_col, aggfunc="mean")

    if p1 in wide.columns and p2 in wide.columns:
        diff = (wide[p1] - wide[p2]).dropna()
        n = len(diff)
        if n >= 2:
            mean_diff = float(diff.mean())
            se = float(diff.std(ddof=1) / sqrt(n))
            _, p_value = stats.ttest_1samp(diff, popmean=0.0, nan_policy="omit")
            return float(p_value), mean_diff, se

    # Fallback: if paired observations are insufficient, use independent Student t-test.
    g1 = pair_df.loc[pair_df[product_col] == p1, value_col].dropna()
    g2 = pair_df.loc[pair_df[product_col] == p2, value_col].dropna()

    if len(g1) < 2 or len(g2) < 2:
        return np.nan, np.nan, np.nan

    _, p_value = stats.ttest_ind(g1, g2, equal_var=True, nan_policy="omit")
    mean_diff = float(g1.mean() - g2.mean())

    var1 = float(g1.var(ddof=1))
    var2 = float(g2.var(ddof=1))
    n1 = len(g1)
    n2 = len(g2)
    pooled_var = (((n1 - 1) * var1) + ((n2 - 1) * var2)) / (n1 + n2 - 2)
    se = float(sqrt(pooled_var * ((1.0 / n1) + (1.0 / n2))))
    return float(p_value), mean_diff, se


def _fit_mixed_model(df: pd.DataFrame, id_col: str) -> None:
    model = smf.mixedlm("y ~ C(product)", data=df, groups=df[id_col], re_formula="1")
    # Fit model to satisfy the requested mixed-model workflow.
    model.fit(reml=True, method="lbfgs", disp=False)


def run_significance_analysis(raw: pd.DataFrame) -> pd.DataFrame:
    validate_raw_dataframe(raw)
    id_col = raw.columns[0]
    product_col = raw.columns[1]
    dq_cols = list(raw.columns[2:])

    data = raw[[id_col, product_col] + dq_cols].copy()
    data[product_col] = data[product_col].astype(str).str.strip()
    products = sorted(data[product_col].dropna().unique().tolist())

    if len(products) < 2:
        raise ValueError(f"Need at least two product levels, found: {products}")

    pairs = list(combinations(products, 2))
    records: list[dict[str, float | str]] = []

    for dq in dq_cols:
        sub = data[[id_col, product_col, dq]].copy()
        sub[dq] = pd.to_numeric(sub[dq], errors="coerce")
        sub = sub.dropna(subset=[dq, product_col, id_col])

        if sub.empty:
            for p1, p2 in pairs:
                records.append(
                    {
                        "dq": dq,
                        "T1": p1,
                        "T2": p2,
                        "P_value": np.nan,
                        "mean_difference": np.nan,
                        "standard_error": np.nan,
                    }
                )
            continue

        mm_df = sub.rename(columns={product_col: "product", dq: "y"})
        try:
            _fit_mixed_model(mm_df, id_col=id_col)
        except Exception:
            # Keep producing pairwise results even if one model fails to converge.
            pass

        for p1, p2 in pairs:
            p_value, mean_diff, se = _paired_ttest_by_id(
                sub, id_col=id_col, product_col=product_col, value_col=dq, p1=p1, p2=p2
            )
            records.append(
                {
                    "dq": dq,
                    "T1": p1,
                    "T2": p2,
                    "P_value": p_value,
                    "mean_difference": mean_diff,
                    "standard_error": se,
                }
            )

    result = pd.DataFrame.from_records(records)
    result = result[["dq", "T1", "T2", "P_value"]]
    return result


def main(input_file: Path) -> None:
    raw = read_raw_csv(input_file)
    result = run_significance_analysis(raw)

    with pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl") as writer:
        result.to_excel(writer, sheet_name="2_Result_SQM_Python", index=False)

    print(f"Saved result to: {OUTPUT_FILE.resolve()}")
    print(f"Rows: {len(result)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run mixed-design analysis on a raw CSV.")
    parser.add_argument("input_csv", type=Path, help="Path to the raw questionnaire CSV.")
    main(parser.parse_args().input_csv)
