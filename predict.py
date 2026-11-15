"""Prediction script: score new CSV using saved artifact.

Usage:
    python predict.py --input test.csv --artifact artifact/ --out predictions.csv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import numpy as np
import pandas as pd

from hpcbd.artifact import load_artifact
from hpcbd.io import DEFAULT_SCHEMA, EmptyInputError, NonFiniteValueError, SchemaMismatchError


def _available_output_name(base: str, existing: pd.Index) -> str:
    """Choose a prediction column name without replacing an input column."""
    if base not in existing:
        return base
    return f"prediction_{base}"


def _load_prediction_csv(path: str | Path, required_columns: list[str]) -> pd.DataFrame:
    """Load inference data while preserving non-feature columns verbatim."""
    input_path = Path(path)
    if not input_path.exists():
        raise FileNotFoundError(f"CSV file not found: {input_path}")

    try:
        df = pd.read_csv(input_path)
    except pd.errors.EmptyDataError as error:
        raise EmptyInputError("CSV contains no header or data rows.") from error

    if df.empty:
        raise EmptyInputError("CSV contains no data rows.")

    missing = sorted(set(required_columns) - set(df.columns))
    if missing:
        raise SchemaMismatchError(f"missing columns: {missing}")

    for column in required_columns:
        values = pd.to_numeric(df[column], errors="coerce")
        if values.isna().any() or not np.isfinite(values.to_numpy(dtype=float)).all():
            raise NonFiniteValueError(f"Column '{column}' contains non-finite or non-numeric values.")
        df[column] = values

    return df.reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Score new HPC traces for backdoor anomalies")
    parser.add_argument("--input", required=True, help="Input CSV file to score")
    parser.add_argument("--artifact", required=True, help="Artifact directory")
    parser.add_argument("--out", default="predictions.csv", help="Output predictions CSV")
    args = parser.parse_args()

    print(f"[predict] Loading artifact from: {args.artifact}")
    det, prep, tau, alpha, schema, cfg = load_artifact(args.artifact)
    print(f"  tau = {tau:.6f}, alpha = {alpha}")

    print(f"[predict] Loading input from: {args.input}")
    required_columns = list(schema) if schema else list(DEFAULT_SCHEMA)
    try:
        df = _load_prediction_csv(args.input, required_columns)
    except (FileNotFoundError, EmptyInputError, SchemaMismatchError, NonFiniteValueError) as error:
        print(f"[predict] ERROR: invalid input CSV: {error}", file=sys.stderr)
        raise SystemExit(2) from error
    print(f"  Shape: {df.shape}")

    # Preprocess
    X = prep.transform(df.loc[:, required_columns])
    print(f"  Preprocessed shape: {X.shape}")

    # Score
    fused, per_det = det.score(X)

    # Build output
    out_df = df.copy()
    score_column = _available_output_name("score", out_df.columns)
    label_column = _available_output_name("label", out_df.columns)
    out_df[score_column] = fused
    out_df[label_column] = (fused > tau).astype(int)
    for name, sc in per_det.items():
        out_df[_available_output_name(f"score_{name}", out_df.columns)] = sc

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(out_path, index=False)

    n_anom = int(out_df[label_column].sum())
    print(f"[predict] {n_anom}/{len(out_df)} samples flagged as anomalous (tau={tau:.4f})")
    print(f"[predict] Predictions saved to {out_path}")

    # Score summary
    print(f"\nScore statistics:")
    print(f"  mean = {fused.mean():.4f}")
    print(f"  std  = {fused.std():.4f}")
    print(f"  min  = {fused.min():.4f}")
    print(f"  max  = {fused.max():.4f}")
    print(f"  q50  = {np.median(fused):.4f}")
    print(f"  q95  = {np.percentile(fused, 95):.4f}")


if __name__ == "__main__":
    main()
