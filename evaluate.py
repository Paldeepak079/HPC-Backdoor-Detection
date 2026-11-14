"""Evaluate saved predictions against a labelled CSV.

The supplied competition data is benign-only, so classification metrics are
only reported when the evaluation CSV contains both binary classes.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent / "src"))

from hpcbd.artifact import load_artifact
from hpcbd.metrics import compute_metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate HPC anomaly predictions")
    parser.add_argument("--input", required=True, help="CSV with features and label column")
    parser.add_argument("--artifact", required=True, help="Saved artifact directory")
    parser.add_argument("--out", default=None, help="Optional JSON output path")
    args = parser.parse_args()

    detector, preprocessor, tau, _, _, _ = load_artifact(args.artifact)
    df = pd.read_csv(args.input)
    if "label" not in df.columns:
        raise SystemExit("Input CSV must contain a binary 'label' column.")

    y_true = df["label"].to_numpy(dtype=int)
    if set(y_true) - {0, 1}:
        raise SystemExit("The 'label' column must contain only 0 and 1.")

    if "score" in df.columns:
        scores = df["score"].to_numpy(dtype=float)
    else:
        features = df.drop(columns=["label"])
        scores, _ = detector.score(preprocessor.transform(features))

    result = {
        "n_samples": int(len(df)),
        "n_positive": int(y_true.sum()),
        "threshold": float(tau),
        "classification_metrics_available": bool(len(set(y_true)) == 2),
    }
    if result["classification_metrics_available"]:
        result.update(compute_metrics(y_true, scores, tau))
    else:
        result["message"] = (
            "Accuracy, TPR, FPR, F1 and AUROC require both benign and "
            "anomalous labels; no classification metrics were fabricated."
        )

    print(json.dumps(result, indent=2))
    if args.out:
        output = Path(args.out)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
