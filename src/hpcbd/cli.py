"""Command-line interface for hpcbd."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd


def cmd_audit(args: argparse.Namespace) -> None:
    """Run data audit and print/save report."""
    from hpcbd.io import load_csv
    from hpcbd.audit import audit, save_audit

    df = load_csv(args.data)
    report = audit(df)

    out_path = Path(args.out) if args.out else Path("reports/audit")
    save_audit(report, out_path)
    print(f"[audit] Report saved to {out_path}.json and {out_path}.md")
    print(f"  Shape: {report['shape']}")
    print(f"  Duplicate rows: {report['duplicate_rows']}")
    print(f"  Constant cols: {report['constant_cols']}")


def cmd_fit(args: argparse.Namespace) -> None:
    """Fit the ensemble and save artifact."""
    from hpcbd.io import load_csv
    from hpcbd.preprocess import Preprocessor
    from hpcbd.detectors import (
        MahalanobisDetector, PCADetector, IForestDetector,
        KNNDetector, GMMDetector, OCSVMDetector,
    )
    from hpcbd.ensemble import EnsembleDetector
    from hpcbd.calibrate import calibrate
    from hpcbd.artifact import save_artifact
    import yaml

    cfg = {}
    if args.config and Path(args.config).exists():
        with open(args.config) as f:
            cfg = yaml.safe_load(f) or {}

    seed = cfg.get("seed", 42)
    alpha = float(cfg.get("alpha", 0.05))

    df = load_csv(args.data)
    prep = Preprocessor(
        add_ratios=cfg.get("preprocess", {}).get("add_ratios", True),
    )
    X = prep.fit_transform(df)

    dcfg = cfg.get("detectors", {})
    detectors = {
        "mahalanobis": MahalanobisDetector(),
        "pca": PCADetector(variance_threshold=dcfg.get("pca", {}).get("variance_threshold", 0.95)),
        "iforest": IForestDetector(
            n_estimators=dcfg.get("iforest", {}).get("n_estimators", 200),
            max_samples=dcfg.get("iforest", {}).get("max_samples", 256),
            random_state=seed,
        ),
        "knn": KNNDetector(k=dcfg.get("knn", {}).get("k", 10)),
        "gmm": GMMDetector(
            max_components=dcfg.get("gmm", {}).get("max_components", 6),
            random_state=seed,
        ),
        "ocsvm": OCSVMDetector(
            nu=dcfg.get("ocsvm", {}).get("nu", 0.05),
            kernel=dcfg.get("ocsvm", {}).get("kernel", "rbf"),
        ),
    }

    fusion_rule = cfg.get("fusion", {}).get("rule", "mean")
    ensemble = EnsembleDetector(detectors, fusion_rule=fusion_rule)
    ensemble.fit(X)

    # Calibrate using training scores
    fused, _ = ensemble.score(X)
    tau = calibrate(fused, alpha=alpha)

    out_path = Path(args.out)
    from hpcbd.io import DEFAULT_SCHEMA
    save_artifact(
        detector=ensemble,
        preprocessor=prep,
        tau=tau,
        alpha=alpha,
        schema=DEFAULT_SCHEMA,
        config=cfg,
        path=out_path,
    )
    print(f"[fit] tau = {tau:.6f}")


def cmd_score(args: argparse.Namespace) -> None:
    """Score a CSV file using a saved artifact."""
    from hpcbd.artifact import load_artifact

    det, prep, tau, alpha, schema, cfg = load_artifact(args.artifact)
    df = pd.read_csv(args.input)
    X = prep.transform(df)
    fused, per_det = det.score(X)

    out_df = df.copy()
    out_df["score"] = fused
    for name, sc in per_det.items():
        out_df[f"score_{name}"] = sc

    out_path = Path(args.out) if args.out else Path("scores.csv")
    out_df.to_csv(out_path, index=False)
    print(f"[score] Scores written to {out_path}")


def cmd_predict(args: argparse.Namespace) -> None:
    """Score + threshold to produce binary predictions."""
    from hpcbd.artifact import load_artifact

    det, prep, tau, alpha, schema, cfg = load_artifact(args.artifact)
    df = pd.read_csv(args.input)
    X = prep.transform(df)
    fused, per_det = det.score(X)

    out_df = df.copy()
    out_df["score"] = fused
    out_df["label"] = (fused > tau).astype(int)
    for name, sc in per_det.items():
        out_df[f"score_{name}"] = sc

    out_path = Path(args.out) if args.out else Path("predictions.csv")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(out_path, index=False)
    n_anom = int(out_df["label"].sum())
    print(f"[predict] {n_anom}/{len(out_df)} samples flagged (tau={tau:.4f})")
    print(f"[predict] Predictions saved to {out_path}")


def cmd_evaluate(args: argparse.Namespace) -> None:
    """Evaluate predictions against ground-truth labels."""
    from hpcbd.metrics import compute_metrics
    from hpcbd.artifact import load_artifact

    det, prep, tau, alpha, schema, cfg = load_artifact(args.artifact)
    df = pd.read_csv(args.input)

    if "label" not in df.columns:
        print("[evaluate] ERROR: input CSV must have a 'label' column.")
        sys.exit(1)

    y_true = df["label"].to_numpy()
    score_col = "score" if "score" in df.columns else None

    if score_col is None:
        X = prep.transform(df.drop(columns=["label"]))
        fused, _ = det.score(X)
    else:
        fused = df[score_col].to_numpy()

    metrics = compute_metrics(y_true, fused, tau)
    print("[evaluate] Metrics:")
    for k, v in metrics.items():
        print(f"  {k}: {v}")


def cmd_explain(args: argparse.Namespace) -> None:
    """Explain a single row from input CSV."""
    from hpcbd.artifact import load_artifact
    from hpcbd.explain import explain_row

    det, prep, tau, alpha, schema, cfg = load_artifact(args.artifact)
    df = pd.read_csv(args.input)
    idx = int(args.row_index)
    row = df.iloc[idx]

    mahal = det.detectors.get("mahalanobis")
    if mahal is None:
        print("[explain] No Mahalanobis detector in ensemble.")
        sys.exit(1)

    result = explain_row(row, prep, mahal, k=int(args.k))
    print(f"[explain] Row {idx}:")
    for item in result:
        print(f"  {item['feature']}: z={item['z_score']:.4f} ({item['direction']})")


def cmd_export(args: argparse.Namespace) -> None:
    """Export run.json for the dashboard."""
    import subprocess
    result = subprocess.run(
        [
            sys.executable, "export_dashboard.py",
            "--predictions", args.predictions,
            "--artifact", args.artifact,
            "--out", args.out,
        ],
        capture_output=True,
        text=True,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        sys.exit(result.returncode)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hpcbd",
        description="HPC Backdoor Detection CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # audit
    p_audit = sub.add_parser("audit", help="Run data audit")
    p_audit.add_argument("--data", required=True)
    p_audit.add_argument("--out", default=None)

    # fit
    p_fit = sub.add_parser("fit", help="Fit ensemble detector")
    p_fit.add_argument("--data", required=True)
    p_fit.add_argument("--out", required=True)
    p_fit.add_argument("--config", default="configs/default.yaml")

    # score
    p_score = sub.add_parser("score", help="Score a CSV file")
    p_score.add_argument("--input", required=True)
    p_score.add_argument("--artifact", required=True)
    p_score.add_argument("--out", default=None)

    # predict
    p_predict = sub.add_parser("predict", help="Predict anomalies")
    p_predict.add_argument("--input", required=True)
    p_predict.add_argument("--artifact", required=True)
    p_predict.add_argument("--out", default=None)

    # evaluate
    p_eval = sub.add_parser("evaluate", help="Evaluate against labels")
    p_eval.add_argument("--input", required=True)
    p_eval.add_argument("--artifact", required=True)

    # explain
    p_explain = sub.add_parser("explain", help="Explain a single sample")
    p_explain.add_argument("--input", required=True)
    p_explain.add_argument("--artifact", required=True)
    p_explain.add_argument("--row-index", default=0)
    p_explain.add_argument("--k", default=3)

    # export
    p_export = sub.add_parser("export", help="Export dashboard run.json")
    p_export.add_argument("--predictions", required=True)
    p_export.add_argument("--artifact", required=True)
    p_export.add_argument("--out", default="dashboard/")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    dispatch = {
        "audit": cmd_audit,
        "fit": cmd_fit,
        "score": cmd_score,
        "predict": cmd_predict,
        "evaluate": cmd_evaluate,
        "explain": cmd_explain,
        "export": cmd_export,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
