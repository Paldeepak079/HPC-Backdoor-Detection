"""Export dashboard run.json from predictions and artifact.

Usage:
    python export_dashboard.py --predictions predictions.csv --artifact artifact/ --out dashboard/
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import numpy as np
import pandas as pd

from hpcbd.artifact import load_artifact
from hpcbd.explain import explain_row
from hpcbd.calibrate import calibrate


def _make_serialisable(obj):
    """Recursively convert numpy types to Python native types."""
    if isinstance(obj, dict):
        return {k: _make_serialisable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_make_serialisable(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        value = float(obj)
        return None if not np.isfinite(value) else value
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, float) and (np.isnan(obj) or np.isinf(obj)):
        return None
    return obj


def main() -> None:
    parser = argparse.ArgumentParser(description="Export dashboard run.json")
    parser.add_argument("--predictions", required=True, help="Predictions CSV (from train.py or predict.py)")
    parser.add_argument("--artifact", required=True, help="Artifact directory")
    parser.add_argument("--out", default="dashboard/", help="Output directory for run.json")
    args = parser.parse_args()

    print(f"[export] Loading artifact from: {args.artifact}")
    det, prep, tau, alpha, schema, cfg = load_artifact(args.artifact)

    print(f"[export] Loading predictions from: {args.predictions}")
    pred_df = pd.read_csv(args.predictions)
    n = len(pred_df)
    print(f"  {n} rows loaded.")

    # Identify score columns
    missing_columns = {"score", "label"} - set(pred_df.columns)
    if missing_columns:
        raise ValueError(
            f"Predictions CSV is missing required columns: {sorted(missing_columns)}"
        )
    score_col = "score"
    label_col = "label"

    det_score_cols = [c for c in pred_df.columns if c.startswith("score_")]

    # Get Mahalanobis detector for explanations
    mahal = det.detectors.get("mahalanobis") if hasattr(det, "detectors") else None

    # Build rows
    rows = []
    feature_cols = [c for c in schema if c in pred_df.columns]

    scores_arr = pred_df[score_col].to_numpy(dtype=float)
    labels_arr = pred_df[label_col].to_numpy(dtype=int)

    for i in range(n):
        raw_row = pred_df.iloc[i]
        score_val = float(scores_arr[i])
        label_val = int(labels_arr[i])

        # Per-detector stage scores
        stage_scores = {}
        for col in det_score_cols:
            det_name = col[len("score_"):]
            stage_scores[det_name] = float(raw_row[col]) if col in pred_df.columns else None

        # Explanation (top 3 features)
        top_features = []
        if mahal is not None and mahal._mean is not None:
            try:
                # Build a row dict with only original feature columns
                row_dict = {c: raw_row[c] for c in feature_cols if c in raw_row.index}
                top_features = explain_row(row_dict, prep, mahal, k=3)
            except Exception:
                top_features = []

        rows.append({
            "row_id": i,
            "score": score_val,
            "label": label_val,
            "top_features": top_features,
            "stage_scores": stage_scores,
        })

    # Calibration statistics
    oof_norm = np.array([r["score"] for r in rows])  # training scores as reference
    n_flagged = int(sum(r["label"] for r in rows))
    pct_flagged = round(100.0 * n_flagged / n, 2) if n > 0 else 0.0

    calibration = {
        "tau": float(tau),
        "alpha": float(alpha),
        "n_flagged": n_flagged,
        "n_total": n,
        "pct_flagged": pct_flagged,
        "score_mean": float(oof_norm.mean()),
        "score_std": float(oof_norm.std()),
        "score_q50": float(np.median(oof_norm)),
        "score_q95": float(np.percentile(oof_norm, 95)),
        "score_max": float(oof_norm.max()),
    }

    run_json = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "schema": schema,
            "feature_names": prep.feature_names,
            "n_detectors": len(det.detectors) if hasattr(det, "detectors") else 1,
            "detector_names": list(det.detectors.keys()) if hasattr(det, "detectors") else [],
            "fusion_rule": getattr(det, "fusion_rule", "mean"),
            "config": cfg,
        },
        "threshold": float(tau),
        "alpha": float(alpha),
        "calibration": calibration,
        "rows": rows,
    }

    out_path = Path(args.out)
    out_path.mkdir(parents=True, exist_ok=True)
    run_json_path = out_path / "run.json"

    serialisable = _make_serialisable(run_json)
    with open(run_json_path, "w", encoding="utf-8") as f:
        json.dump(serialisable, f, indent=2)

    # Keep the static dashboard inputs synchronized with this exact export.
    # The React app consumes these files directly rather than fabricating data.
    shutil.copy2(args.predictions, out_path / "predictions.csv")
    shutil.copy2(Path(args.artifact) / "manifest.json", out_path / "manifest.json")
    experiment_results = Path(args.artifact).parent / "reports" / "experiment_results.json"
    if experiment_results.exists():
        shutil.copy2(experiment_results, out_path / "experiment_results.json")

    print(f"[export] run.json written to {run_json_path}")
    print(f"  Total rows: {n}")
    print(f"  Flagged: {n_flagged} ({pct_flagged}%)")
    print(f"  tau = {tau:.6f}")
    print(f"  Score mean = {calibration['score_mean']:.4f}, max = {calibration['score_max']:.4f}")

    # Print schema overview
    print("\n[export] run.json top-level schema:")
    for key in run_json:
        val = run_json[key]
        if isinstance(val, list):
            print(f"  {key}: [{len(val)} items]")
        elif isinstance(val, dict):
            print(f"  {key}: {{{', '.join(list(val.keys())[:5])}{',...' if len(val) > 5 else ''}}}")
        else:
            print(f"  {key}: {val}")


if __name__ == "__main__":
    main()
