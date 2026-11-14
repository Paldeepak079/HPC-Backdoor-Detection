"""Main training script for HPC Backdoor Detection.

Usage:
    python train.py --data "HPC traces/trace.csv" --out artifact/
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

# Allow importing from src/
sys.path.insert(0, str(Path(__file__).parent / "src"))

import yaml

from hpcbd.io import load_csv, DEFAULT_SCHEMA
from hpcbd.audit import audit, save_audit
from hpcbd.preprocess import Preprocessor
from hpcbd.detectors import (
    MahalanobisDetector, PCADetector, IForestDetector,
    KNNDetector, GMMDetector, OCSVMDetector, PyODECODDetector,
)
from hpcbd.ensemble import EnsembleDetector
from hpcbd.artifact import save_artifact


def load_config(cfg_path: str) -> dict:
    p = Path(cfg_path)
    if p.exists():
        with open(p) as f:
            return yaml.safe_load(f) or {}
    print(f"[train] Config not found at {cfg_path}, using defaults.")
    return {}


def main() -> None:
    parser = argparse.ArgumentParser(description="Train HPC Backdoor Detection ensemble")
    parser.add_argument("--data", required=True, help="Path to trace CSV")
    parser.add_argument("--out", default="artifact/", help="Output directory for artifact")
    parser.add_argument("--config", default="configs/default.yaml")
    parser.add_argument("--run-experiments", action="store_true", default=True,
                        help="Run leakage-safe CV calibration before final fit (default)")
    args = parser.parse_args()

    t_start = time.time()

    # --- Load config ---
    cfg = load_config(args.config)
    seed = int(cfg.get("seed", 42))
    alpha = float(cfg.get("alpha", 0.05))
    cv_folds = int(cfg.get("cv_folds", 5))
    cv_repeats = int(cfg.get("cv_repeats", 10))

    print("=" * 60)
    print("HPC Backdoor Detection — Training Pipeline")
    print("=" * 60)
    print(f"  Data   : {args.data}")
    print(f"  Output : {args.out}")
    print(f"  Config : {args.config}")
    print(f"  seed={seed}, alpha={alpha}")

    # --- Step 1: Load data ---
    print("\n[1/6] Loading data...")
    df = load_csv(args.data)
    print(f"  Shape: {df.shape}")
    print(f"  Columns: {list(df.columns)}")

    # --- Step 2: Audit ---
    print("\n[2/6] Auditing data...")
    audit_report = audit(df)
    Path("reports").mkdir(exist_ok=True)
    save_audit(audit_report, "reports/data_audit")
    print(f"  Audit saved to reports/data_audit.{{json,md}}")
    print(f"  NaN counts: {audit_report['nan_counts']}")
    print(f"  Constant cols: {audit_report['constant_cols']}")
    pcs = audit_report["per_column_stats"]
    for col, stats in pcs.items():
        print(f"  {col}: mean={stats['mean']:.2f}, std={stats['std']:.2f}, "
              f"skew={stats['skew']:.2f}")

    # --- Step 3: Preprocess ---
    print("\n[3/6] Preprocessing...")
    prep_cfg = cfg.get("preprocess", {})
    preprocessor = Preprocessor(
        add_ratios=prep_cfg.get("add_ratios", True),
        transform=prep_cfg.get("transform", "log1p"),
        scaler=prep_cfg.get("scaler", "robust"),
    )
    X = preprocessor.fit_transform(df)
    print(f"  Feature matrix: {X.shape}")
    print(f"  Feature names: {preprocessor.feature_names}")

    # --- Step 4: Run experiments (CV) ---
    print(f"\n[4/6] Running {cv_repeats}×{cv_folds}-fold CV experiments...")
    from experiments.run_experiments import run_experiments
    exp_results = run_experiments(
        data_path=args.data,
        cv_folds=cv_folds,
        cv_repeats=cv_repeats,
        seed=seed,
        alpha=alpha,
        fusion_rule=cfg.get("fusion", {}).get("rule", "mean"),
        detector_config=cfg.get("detectors", {}),
    )
    print(f"  CV tau = {exp_results['tau']:.6f}")
    for name, s in exp_results["per_detector"].items():
        print(f"  {name}: OOF mean={s['oof_mean']:.4f} ± {s['oof_std']:.4f}")

    # --- Step 5: Final fit on full data ---
    print("\n[5/6] Fitting final ensemble on full dataset...")
    dcfg = cfg.get("detectors", {})
    detectors = {}
    if dcfg.get("mahalanobis", {}).get("enabled", True):
        detectors["mahalanobis"] = MahalanobisDetector()
    if dcfg.get("pca", {}).get("enabled", True):
        detectors["pca"] = PCADetector(
            variance_threshold=dcfg.get("pca", {}).get("variance_threshold", 0.95)
        )
    # DISABLED: P1-1 keeps non-selected detector code available behind config flags.
    if dcfg.get("iforest", {}).get("enabled", False):
        detectors["iforest"] = IForestDetector(
            n_estimators=dcfg.get("iforest", {}).get("n_estimators", 200),
            max_samples=dcfg.get("iforest", {}).get("max_samples", 256),
            random_state=seed,
        )
    if dcfg.get("knn", {}).get("enabled", False):
        detectors["knn"] = KNNDetector(k=dcfg.get("knn", {}).get("k", 10))
    if dcfg.get("gmm", {}).get("enabled", False):
        detectors["gmm"] = GMMDetector(
            max_components=dcfg.get("gmm", {}).get("max_components", 6),
            random_state=seed,
        )
    if dcfg.get("ocsvm", {}).get("enabled", False):
        detectors["ocsvm"] = OCSVMDetector(
            nu=dcfg.get("ocsvm", {}).get("nu", 0.05),
            kernel=dcfg.get("ocsvm", {}).get("kernel", "rbf"),
        )
    if dcfg.get("pyod_ecod", {}).get("enabled", False):
        detectors["pyod_ecod"] = PyODECODDetector()

    fusion_rule = cfg.get("fusion", {}).get("rule", "mean")
    ensemble = EnsembleDetector(detectors, fusion_rule=fusion_rule)
    # Fit on all benign traces, but use fold-held-out scores for the score
    # reference distribution and threshold to avoid in-sample calibration.
    ensemble.fit(X, oof_scores={
        name: np.asarray(scores)
        for name, scores in exp_results["raw_oof_scores"].items()
        if name in detectors
    })

    # Score training data to get reference distribution
    fused_train, per_det_train = ensemble.score(X)
    print(f"  Training score stats: mean={fused_train.mean():.4f}, "
          f"std={fused_train.std():.4f}, max={fused_train.max():.4f}")

    for name, sc in per_det_train.items():
        print(f"    {name}: mean={sc.mean():.4f} ± {sc.std():.4f}")

    # --- Step 6: Calibrate ---
    print(f"\n[6/6] Calibrating threshold (alpha={alpha})...")
    tau = float(exp_results["tau"])
    n_flagged = int((fused_train > tau).sum())
    print(f"  tau = {tau:.6f}")
    print(f"  Samples flagged on training set: {n_flagged}/{len(fused_train)} "
          f"({100*n_flagged/len(fused_train):.1f}%)")
    flag_rate = n_flagged / len(fused_train)
    if not 0.03 <= flag_rate <= 0.08:
        raise RuntimeError(
            f"Benign flag rate {flag_rate:.1%} is outside the 3–8% acceptance range; "
            "artifacts and reports were not regenerated."
        )

    Path("reports").mkdir(exist_ok=True)
    with open("reports/experiment_results.json", "w", encoding="utf-8") as f:
        json.dump(exp_results, f, indent=2)
    with open("reports/evaluation_benign_only.json", "w", encoding="utf-8") as f:
        json.dump({
            "n_samples": int(len(df)),
            "n_positive": 0,
            "threshold": tau,
            "classification_metrics_available": False,
            "message": (
                "Accuracy, TPR, FPR, F1 and AUROC require both benign and anomalous "
                "labels; no classification metrics were fabricated."
            ),
        }, f, indent=2)

    # Save artifact
    out_path = Path(args.out)
    save_artifact(
        detector=ensemble,
        preprocessor=preprocessor,
        tau=tau,
        alpha=alpha,
        schema=DEFAULT_SCHEMA,
        config=cfg,
        path=out_path,
    )

    # Save scores on training data as predictions.csv
    import pandas as pd
    pred_df = df.copy()
    pred_df["score"] = fused_train
    pred_df["label"] = (fused_train > tau).astype(int)
    for name, sc in per_det_train.items():
        pred_df[f"score_{name}"] = sc
    pred_path = Path("predictions.csv")
    pred_df.to_csv(pred_path, index=False)
    print(f"\n  Training predictions saved to {pred_path}")

    elapsed = time.time() - t_start
    print(f"\n{'='*60}")
    print(f"Training complete in {elapsed:.1f}s")
    print(f"  Artifact: {out_path}/")
    print(f"  tau = {tau:.6f} (alpha={alpha})")
    print(f"  Flagged (train): {n_flagged}/{len(fused_train)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
