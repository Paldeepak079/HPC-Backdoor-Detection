"""PyOD ECOD detector wrapper."""

from __future__ import annotations

import numpy as np

from pyod.models.ecod import ECOD


class PyODECODDetector:
    """Empirical-CDF outlier detector from PyOD.

    ECOD is useful here because it is a deterministic, distribution-free
    univariate detector that complements the multivariate sklearn models.
    """

    def __init__(self) -> None:
        self._model: ECOD | None = None

    def fit(self, X: np.ndarray) -> "PyODECODDetector":
        # PyOD uses contamination only for its internal labels; the
        # competition threshold is calibrated separately from held-out scores.
        self._model = ECOD(contamination=0.05)
        self._model.fit(X)
        return self

    def score(self, X: np.ndarray) -> np.ndarray:
        if self._model is None:
            raise RuntimeError("Detector not fitted. Call fit() first.")
        return np.asarray(self._model.decision_function(X), dtype=float)
