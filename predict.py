"""Prediction script: score new CSV using saved artifact.

Usage:
    python predict.py --input test.csv --artifact artifact/ --out predictions.csv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import pandas as pd
import numpy as np

from hpcbd.artifact import load_artifact


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
    df = pd.read_csv(args.input)
    print(f"  Shape: {df.shape}")

    # Preprocess
    X = prep.transform(df)
    print(f"  Preprocessed shape: {X.shape}")

    # Score
    fused, per_det = det.score(X)

    # Build output
    out_df = df.copy()
    out_df["score"] = fused
    out_df["label"] = (fused > tau).astype(int)
    for name, sc in per_det.items():
        out_df[f"score_{name}"] = sc

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(out_path, index=False)

    n_anom = int(out_df["label"].sum())
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
