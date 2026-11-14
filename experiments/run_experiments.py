"""Experiment runner: 5×10 repeated k-fold CV on all detectors."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
from sklearn.model_selection import RepeatedKFold

# Allow importing from src/
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from hpcbd.io import load_csv
from hpcbd.preprocess import Preprocessor
from hpcbd.detectors import (
    MahalanobisDetector, PCADetector, IForestDetector,
    KNNDetector, GMMDetector, OCSVMDetector, PyODECODDetector,
)
from hpcbd.ensemble import normalise_scores, fuse_scores
from hpcbd.calibrate import calibrate


def make_detectors(seed: int = 42) -> dict:
    return {
        "mahalanobis": MahalanobisDetector(),
        "pca": PCADetector(variance_threshold=0.95),
        "iforest": IForestDetector(n_estimators=200, max_samples=256, random_state=seed),
        "knn": KNNDetector(k=10),
        "gmm": GMMDetector(max_components=6, random_state=seed),
        "ocsvm": OCSVMDetector(nu=0.05, kernel="rbf"),
        "pyod_ecod": PyODECODDetector(),
    }


def run_experiments(
    data_path: str = "HPC traces/trace.csv",
    cv_folds: int = 5,
    cv_repeats: int = 10,
    seed: int = 42,
    alpha: float = 0.05,
    fusion_rule: str = "mean",
) -> dict:
    """Run repeated k-fold CV for all detectors.

    Returns
    -------
    dict with per-detector OOF scores, stability metrics, and calibration.
    """
    print(f"[experiments] Loading data from: {data_path}")
    df = load_csv(data_path)
    n_samples = len(df)
    print(f"[experiments] {n_samples} samples loaded.")

    rkf = RepeatedKFold(n_splits=cv_folds, n_repeats=cv_repeats, random_state=seed)

    # Store OOF scores per detector. Every fold fits preprocessing and models
    # on the fold's training partition only.
    oof_scores: dict[str, np.ndarray] = {
        name: np.zeros(n_samples) for name in make_detectors().keys()
    }
    raw_oof_scores: dict[str, np.ndarray] = {
        name: np.zeros(n_samples) for name in make_detectors().keys()
    }
    # Count how many folds each sample appeared in val set
    fold_counts = np.zeros(n_samples, dtype=int)
    fold_results = []

    total_folds = cv_folds * cv_repeats
    print(f"[experiments] Running {total_folds} folds ({cv_repeats}×{cv_folds}-fold CV)...")

    for fold_idx, (train_idx, val_idx) in enumerate(rkf.split(np.arange(n_samples))):
        t0 = time.time()

        # Preprocess on train, transform val
        prep = Preprocessor(add_ratios=True)
        df_train = df.iloc[train_idx]
        df_val = df.iloc[val_idx]

        X_train = prep.fit_transform(df_train)
        X_val = prep.transform(df_val)

        detectors = make_detectors(seed=seed)
        fold_det_scores = {}
        fold_rank_references = {}

        for name, det in detectors.items():
            try:
                det.fit(X_train)
                val_sc = det.score(X_val)
                train_sc = det.score(X_train)
                # Normalise val scores using train reference
                norm_val = normalise_scores(val_sc, train_sc)
                fold_det_scores[name] = norm_val
                fold_rank_references[name] = normalise_scores(train_sc, train_sc)
                # Accumulate OOF
                oof_scores[name][val_idx] += norm_val
                raw_oof_scores[name][val_idx] += val_sc
            except Exception as e:
                print(f"  [warn] Fold {fold_idx+1}, detector {name}: {e}")
                fold_det_scores[name] = np.zeros(len(val_idx))

        fold_counts[val_idx] += 1
        # Fuse for this fold
        fused_val = fuse_scores(
            fold_det_scores,
            rule=fusion_rule,
            rank_references=fold_rank_references,
        )

        elapsed = time.time() - t0
        fold_results.append({
            "fold": fold_idx + 1,
            "n_train": len(train_idx),
            "n_val": len(val_idx),
            "fused_mean": float(fused_val.mean()),
            "fused_std": float(fused_val.std()),
            "fused_max": float(fused_val.max()),
            "elapsed_s": round(elapsed, 3),
        })

        if (fold_idx + 1) % 10 == 0:
            print(f"  Fold {fold_idx+1}/{total_folds} done.")

    # Average OOF scores
    safe_counts = np.maximum(fold_counts, 1)  # average every repeated validation score
    for name in oof_scores:
        oof_scores[name] = oof_scores[name] / safe_counts
        raw_oof_scores[name] = raw_oof_scores[name] / safe_counts

    # Calibrate in the same score domain used by the final ensemble: raw
    # detector scores are mapped through the aggregated raw OOF references.
    # The fold-local normalised scores remain useful for stability reporting.
    calibration_scores = {
        name: normalise_scores(scores, scores)
        for name, scores in raw_oof_scores.items()
    }
    fused_oof = fuse_scores(
        calibration_scores,
        rule=fusion_rule,
        rank_references=calibration_scores,
    )

    # Calibrate
    tau = calibrate(fused_oof, alpha=alpha)

    # Per-detector stability
    det_stats = {}
    for name, sc in oof_scores.items():
        det_stats[name] = {
            "oof_mean": float(sc.mean()),
            "oof_std": float(sc.std()),
            "oof_min": float(sc.min()),
            "oof_max": float(sc.max()),
            "oof_q50": float(np.median(sc)),
            "oof_q95": float(np.percentile(sc, 95)),
        }

    results = {
        "meta": {
            "n_samples": int(n_samples),
            "cv_folds": cv_folds,
            "cv_repeats": cv_repeats,
            "seed": seed,
            "alpha": alpha,
            "fusion_rule": fusion_rule,
        },
        "tau": float(tau),
        "fused_oof_stats": {
            "mean": float(fused_oof.mean()),
            "std": float(fused_oof.std()),
            "q50": float(np.median(fused_oof)),
            "q95": float(np.percentile(fused_oof, 95)),
            "max": float(fused_oof.max()),
        },
        "per_detector": det_stats,
        "fold_summary": fold_results,
        # Store raw OOF as lists for JSON
        "oof_scores": {name: sc.tolist() for name, sc in oof_scores.items()},
        "raw_oof_scores": {name: sc.tolist() for name, sc in raw_oof_scores.items()},
        "fused_oof": fused_oof.tolist(),
    }

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run CV experiments")
    parser.add_argument("--data", default="HPC traces/trace.csv")
    parser.add_argument("--out", default="reports/experiment_results.json")
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--repeats", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument("--fusion-rule", default="mean", choices=["mean", "max", "rank_mean"])
    args = parser.parse_args()

    results = run_experiments(
        data_path=args.data,
        cv_folds=args.folds,
        cv_repeats=args.repeats,
        seed=args.seed,
        alpha=args.alpha,
        fusion_rule=args.fusion_rule,
    )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\n[experiments] Results saved to {out_path}")
    print(f"  tau = {results['tau']:.6f}")
    print(f"  fused OOF mean = {results['fused_oof_stats']['mean']:.4f}")
    print("  Per-detector OOF stats:")
    for name, stats in results["per_detector"].items():
        print(f"    {name}: mean={stats['oof_mean']:.4f} std={stats['oof_std']:.4f}")
