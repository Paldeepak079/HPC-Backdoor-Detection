"""Evaluation metrics for anomaly detection."""

from __future__ import annotations

from typing import Any

import numpy as np


def compute_metrics(
    y_true: np.ndarray,
    scores: np.ndarray,
    threshold: float,
) -> dict[str, Any]:
    """Compute classification metrics given ground-truth labels and anomaly scores.

    Parameters
    ----------
    y_true : array of shape (n,)
        Binary labels: 1 = anomaly, 0 = benign.
    scores : array of shape (n,)
        Anomaly scores (higher = more anomalous).
    threshold : float
        Decision threshold tau; samples with score > tau are predicted anomalous.

    Returns
    -------
    dict with keys:
        accuracy, tpr (true positive rate / recall), fpr (false positive rate),
        f1, auroc (AUC-ROC).
    """
    y_true = np.asarray(y_true, dtype=int)
    scores = np.asarray(scores, dtype=float)
    if len(np.unique(y_true)) != 2:
        raise ValueError(
            "Classification metrics require both benign (0) and anomalous (1) labels."
        )
    y_pred = (scores > threshold).astype(int)

    # Basic counts
    tp = int(np.sum((y_pred == 1) & (y_true == 1)))
    fp = int(np.sum((y_pred == 1) & (y_true == 0)))
    tn = int(np.sum((y_pred == 0) & (y_true == 0)))
    fn = int(np.sum((y_pred == 0) & (y_true == 1)))
    n = len(y_true)

    accuracy = (tp + tn) / n if n > 0 else 0.0
    tpr = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    f1 = (2 * precision * tpr) / (precision + tpr) if (precision + tpr) > 0 else 0.0

    # AUROC via trapezoidal rule
    auroc = _auroc(y_true, scores)

    return {
        "accuracy": float(accuracy),
        "tpr": float(tpr),
        "fpr": float(fpr),
        "precision": float(precision),
        "f1": float(f1),
        "auroc": float(auroc),
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
    }


def _auroc(y_true: np.ndarray, scores: np.ndarray) -> float:
    """Compute AUC-ROC via the trapezoidal rule.

    Both classes must be present; callers validate this before calling.
    """
    # Sort by descending score
    order = np.argsort(scores)[::-1]
    y_sorted = y_true[order]

    n_pos = y_true.sum()
    n_neg = len(y_true) - n_pos
    if n_pos == 0 or n_neg == 0:
        raise ValueError("AUROC requires both benign and anomalous labels.")

    tprs = [0.0]
    fprs = [0.0]
    tp = fp = 0
    for label in y_sorted:
        if label == 1:
            tp += 1
        else:
            fp += 1
        tprs.append(tp / n_pos)
        fprs.append(fp / n_neg)

    # Trapezoidal AUC
    return float(np.trapz(tprs, fprs))
