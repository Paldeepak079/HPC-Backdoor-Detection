"""Create a methodology PDF from recorded audit and experiment results."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _active_detector_names(config: dict) -> list[str]:
    display_names = {"mahalanobis": "Mahalanobis", "pca": "PCA"}
    return [
        display_names.get(name, name.replace("_", " ").title())
        for name, settings in config.get("detectors", {}).items()
        if settings.get("enabled", False)
    ]


def make_report(
    audit_path: Path,
    experiment_path: Path,
    output: Path,
    config_path: Path = Path("artifact/config.json"),
) -> None:
    audit = _read_json(audit_path)
    experiment = _read_json(experiment_path)
    config = _read_json(config_path)
    active_detectors = _active_detector_names(config)
    detector_text = " + ".join(active_detectors) if active_detectors else "no configured detectors"
    output.parent.mkdir(parents=True, exist_ok=True)

    with PdfPages(output) as pdf:
        fig = plt.figure(figsize=(8.27, 11.69))
        fig.text(0.08, 0.93, "HPC Backdoor Detection", fontsize=22, weight="bold")
        fig.text(0.08, 0.895, "Clean-only anomaly detection methodology report", fontsize=13)
        fig.text(
            0.08, 0.82,
            "Objective\n"
            "Detect traces that deviate from 800 benign hardware performance counter traces.\n\n"
            "Data governance\n"
            f"Input shape: {audit['shape'][0]} rows × {audit['shape'][1]} columns.\n"
            "All fitted preprocessing, detector parameters and thresholds use benign data only.\n"
            "No anomaly labels were supplied; classification performance is therefore not claimed.\n\n"
            "Preprocessing\n"
            "Constant columns are removed. Ratio features are derived from the three HPC counters,\n"
            "then non-negative log1p transforms and robust median/IQR scaling are fitted on each\n"
            "training fold. The fitted preprocessor is persisted with the model.\n\n"
            "Detection models\n"
            f"The active batch detectors are {detector_text}. Per-detector scores are converted\n"
            "through an empirical CDF and averaged. Other detectors remain available only when\n"
            "explicitly enabled in config.json. River Half-Space Trees is kept as an opt-in\n"
            "prequential detector for ordered streaming data, not silently mixed into batch scoring.\n\n"
            "Calibration and validation\n"
            f"Repeated {experiment['meta']['cv_repeats']}x{experiment['meta']['cv_folds']}-fold CV fits\n"
            "preprocessing and detectors inside each fold. The final threshold is the finite-sample\n"
            f"conformal upper quantile at the configured alpha (τ={experiment['tau']:.5f}). This estimates a benign false-alarm\n"
            "budget; it does not estimate TPR, F1 or AUROC.",
            fontsize=10, va="top", linespacing=1.35,
        )
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

        names = list(experiment["per_detector"])
        means = [experiment["per_detector"][n]["oof_mean"] for n in names]
        stds = [experiment["per_detector"][n]["oof_std"] for n in names]
        fig, ax = plt.subplots(figsize=(10, 5.5))
        ax.bar(names, means, yerr=stds, capsize=4, color="#2563eb")
        ax.set_title("Leakage-safe OOF score stability (mean ± standard deviation)")
        ax.set_ylabel("Normalised anomaly score")
        ax.tick_params(axis="x", rotation=35)
        ax.grid(axis="y", alpha=0.25)
        fig.tight_layout()
        pdf.savefig(fig)
        plt.close(fig)

        fig, ax = plt.subplots(figsize=(8.27, 11.69))
        fig.text(0.08, 0.93, "Reproducibility and limitations", fontsize=20, weight="bold")
        fig.text(
            0.08, 0.87,
            "Reproduction\n"
            "1. Install the pinned minimum dependencies from requirements.txt.\n"
            "2. Run: python train.py --data \"HPC traces/trace.csv\" --out artifact/\n"
            "3. Score unseen data: python predict.py --input unseen.csv --artifact artifact/ --out predictions.csv\n"
            "4. Evaluate labelled data only: python evaluate.py --input labelled.csv --artifact artifact/\n\n"
            "Saved deliverables\n"
            "The artifact directory contains the fitted preprocessor, detector ensemble, configuration,\n"
            "threshold and SHA-256 manifest. predictions.csv contains raw input columns, the fused\n"
            "anomaly score, binary label and every detector score.\n\n"
            "Interpretation\n"
            "Label 0 means the fused score is at or below the benign-calibrated threshold. Label 1\n"
            "means it exceeds that threshold and should be investigated as suspicious. This is an\n"
            "unsupervised screening result, not proof of a backdoor.\n\n"
            "Limitations\n"
            "Because only benign traces are available, AUROC, TPR, FPR, F1 and accuracy on attacks\n"
            "cannot be computed without an independent labelled test set. Any such values would be\n"
            "fabricated. OOD behaviour and threshold transfer should be revalidated when labelled\n"
            "attack traces become available.",
            fontsize=11, va="top", linespacing=1.45,
        )
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", default="reports/data_audit.json")
    parser.add_argument("--experiments", default="reports/experiment_results.json")
    parser.add_argument("--config", default="artifact/config.json")
    parser.add_argument("--out", default="reports/methodology_report.pdf")
    args = parser.parse_args()
    make_report(Path(args.audit), Path(args.experiments), Path(args.out), Path(args.config))
