from __future__ import annotations

import argparse
from enum import Enum
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType

import pandas as pd

try:
    from calculation.input_schema import read_raw_csv, validate_raw_dataframe
except ModuleNotFoundError:
    from input_schema import read_raw_csv, validate_raw_dataframe


BASE_DIR = Path(__file__).resolve().parent
DESCRIPTION_OUTPUT_FILE = BASE_DIR / "1_description_statistic.xlsx"
SIGNIFICANCE_OUTPUT_FILE = BASE_DIR / "2_significance_test_result.xlsx"


class ExperimentType(str, Enum):
    INDEPENDENT = "independent"
    PAIRED = "paired"
    MIXED = "mixed"


ALGORITHM_FILE_BY_TYPE = {
    ExperimentType.INDEPENDENT: BASE_DIR / "2_2_Method_for_IndependentDesign.py",
    ExperimentType.PAIRED: BASE_DIR / "2_2_Method_for_PairedDesign_PCT.py",
    ExperimentType.MIXED: BASE_DIR / "2_2_Method_for_MixedDesign_SQM.py",
}


def detect_experiment_type(data: pd.DataFrame) -> ExperimentType:
    """Determine experiment type by counting unique products per subject ID."""
    validate_raw_dataframe(data)
    if data.shape[1] < 3:
        raise ValueError("Input data must have at least 3 columns: ID, product, DQ...")

    id_col = data.columns[0]
    product_col = data.columns[1]

    tmp = data[[id_col, product_col]].copy()
    tmp = tmp.dropna(subset=[id_col, product_col])
    tmp[product_col] = tmp[product_col].astype(str).str.strip()

    if tmp.empty:
        raise ValueError("Input data has no valid ID/product rows.")

    product_count_by_id = tmp.groupby(id_col)[product_col].nunique(dropna=True)
    max_products_per_subject = int(product_count_by_id.max())

    if max_products_per_subject <= 1:
        return ExperimentType.INDEPENDENT
    if max_products_per_subject == 2:
        return ExperimentType.PAIRED
    return ExperimentType.MIXED


def create_description_statistics(data: pd.DataFrame) -> pd.DataFrame:
    """Create unified description statistics output: question x product mean."""
    validate_raw_dataframe(data)
    id_col = data.columns[0]
    product_col = data.columns[1]
    dq_cols = list(data.columns[2:])

    long_df = data[[product_col] + dq_cols].melt(
        id_vars=[product_col],
        value_vars=dq_cols,
        var_name="question",
        value_name="value",
    )

    long_df["value"] = pd.to_numeric(long_df["value"], errors="coerce")

    summary = (
        long_df.pivot_table(
            index="question",
            columns=product_col,
            values="value",
            aggfunc="mean",
            dropna=False,
        )
        .reset_index()
        .rename_axis(None, axis=1)
    )
    return summary


def _load_algorithm_module(module_path: Path) -> ModuleType:
    module_name = f"algo_{module_path.stem}"
    spec = spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from: {module_path}")

    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_significance_by_type(data: pd.DataFrame, exp_type: ExperimentType) -> pd.DataFrame:
    """Dispatch to the matched algorithm module with a unified function contract."""
    validate_raw_dataframe(data)
    module_path = ALGORITHM_FILE_BY_TYPE[exp_type]
    module = _load_algorithm_module(module_path)

    run_func = getattr(module, "run_significance_analysis", None)
    if run_func is None:
        raise AttributeError(
            f"Module '{module_path.name}' must define run_significance_analysis(raw_df)."
        )

    result = run_func(data)
    if not isinstance(result, pd.DataFrame):
        raise TypeError(
            f"Module '{module_path.name}' must return a pandas DataFrame, got: {type(result)}"
        )

    expected_cols = ["dq", "T1", "T2", "P_value"]
    missing_cols = [col for col in expected_cols if col not in result.columns]
    if missing_cols:
        raise ValueError(
            f"Module '{module_path.name}' result missing columns: {missing_cols}. "
            f"Expected: {expected_cols}"
        )

    return result[expected_cols].copy()


def main(input_file: Path) -> None:
    """Orchestrate experiment detection, significance test, and description stats output."""
    raw = read_raw_csv(input_file)

    exp_type = detect_experiment_type(raw)
    significance_result = run_significance_by_type(raw, exp_type)
    description_result = create_description_statistics(raw)

    description_result.to_excel(DESCRIPTION_OUTPUT_FILE, index=False)
    significance_result.to_excel(SIGNIFICANCE_OUTPUT_FILE, index=False)

    print(f"Detected experiment type: {exp_type.value}")
    print(f"Saved description stats to: {DESCRIPTION_OUTPUT_FILE.resolve()}")
    print(f"Saved significance result to: {SIGNIFICANCE_OUTPUT_FILE.resolve()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze a CSV that follows the locked input schema.")
    parser.add_argument("input_csv", type=Path, help="Path to the raw questionnaire CSV.")
    main(parser.parse_args().input_csv)
