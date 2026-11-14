"""Explainability: identify top deviating features for a given sample."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .preprocess import Preprocessor
from .detectors.mahalanobis import MahalanobisDetector


def explain_row(
    row: pd.Series | np.ndarray | dict,
    preprocessor: Preprocessor,
    mahal_detector: MahalanobisDetector,
    k: int = 3,
) -> list[dict[str, Any]]:
    """Identify the top-k features most responsible for a sample's anomaly score.

    Uses per-feature z-scores in the Mahalanobis sense (standardised deviation
    from the training centre, accounting for covariance).

    Parameters
    ----------
    row : pd.Series, dict, or 1-D array
        A single sample in original (pre-transformed) feature space.
    preprocessor : Preprocessor
        Fitted preprocessor — used to transform the row.
    mahal_detector : MahalanobisDetector
        Fitted Mahalanobis detector — provides mean and precision.
    k : int
        Number of top features to return.

    Returns
    -------
    list of dict
        Each dict has keys: ``feature``, ``z_score``, ``direction``
        (``'high'`` or ``'low'``), and ``raw_value``.
    """
    # Convert input to DataFrame row
    if isinstance(row, dict):
        df_row = pd.DataFrame([row])
    elif isinstance(row, pd.Series):
        df_row = row.to_frame().T
    else:
        # Assume 1-D array; use preprocessor feature names for original cols
        # (best effort — may not match if ratios were added)
        arr = np.asarray(row).ravel()
        # Try to map to original schema columns
        schema_cols = [c for c in preprocessor.feature_names
                       if c not in ("llc_per_cache_ref", "llc_per_cycle", "cache_ref_per_cycle")]
        if len(arr) == len(schema_cols):
            df_row = pd.DataFrame([dict(zip(schema_cols, arr))])
        else:
            df_row = pd.DataFrame([dict(enumerate(arr))])

    # Transform
    X_t = preprocessor.transform(df_row)  # (1, p)
    feature_names = preprocessor.feature_names

    if mahal_detector._mean is None:
        raise RuntimeError("MahalanobisDetector is not fitted.")

    # Per-feature deviation from training mean (in transformed space)
    # Using diagonal of precision for marginal z-scores
    mean = mahal_detector._mean
    precision = mahal_detector._precision

    diff = (X_t[0] - mean)  # (p,)
    # Feature-wise Mahalanobis contribution: |diff_i| * sqrt(prec_ii)
    prec_diag = np.diag(precision)
    z_scores = np.abs(diff) * np.sqrt(np.maximum(prec_diag, 0.0))

    # Sort descending
    top_indices = np.argsort(z_scores)[::-1][:k]

    results = []
    for idx in top_indices:
        feat = feature_names[idx] if idx < len(feature_names) else str(idx)
        z = float(z_scores[idx])
        direction = "high" if diff[idx] > 0 else "low"
        # Try to get raw value
        try:
            raw_val = float(df_row.iloc[0, idx]) if idx < df_row.shape[1] else None
        except Exception:
            raw_val = None
        results.append({
            "feature": feat,
            "z_score": round(z, 4),
            "direction": direction,
            "raw_value": raw_val,
        })

    return results
