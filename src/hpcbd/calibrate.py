"""Threshold calibration via conformal quantile."""

from __future__ import annotations

import numpy as np


class CalibrationError(Exception):
    """Raised when calibration cannot be performed."""


def calibrate(oof_scores: np.ndarray, alpha: float = 0.05) -> float:
    """Compute the conformal calibration threshold tau.

    Uses the (1 - alpha) quantile of the OOF score distribution as the
    detection threshold, with a finite-sample correction factor
    ceil((n+1)(1-alpha)) / n to maintain coverage guarantee.

    Parameters
    ----------
    oof_scores : array of shape (n,)
        Out-of-fold anomaly scores on benign (training) data.
    alpha : float, optional
        Significance level in (0, 1). Lower alpha → stricter threshold
        (fewer false positives, possibly more false negatives).

    Returns
    -------
    tau : float
        Threshold: samples with score > tau are flagged as anomalous.

    Raises
    ------
    CalibrationError
        If ``oof_scores`` is empty or ``alpha`` is out of range.
    """
    if len(oof_scores) == 0:
        raise CalibrationError("oof_scores must be non-empty.")
    if not (0.0 < alpha < 1.0):
        raise CalibrationError(f"alpha must be in (0, 1), got {alpha}.")

    n = len(oof_scores)
    # Conformal quantile level with finite-sample correction
    q_level = min(np.ceil((n + 1) * (1.0 - alpha)) / n, 1.0)
    tau = float(np.quantile(oof_scores, q_level))
    return tau
