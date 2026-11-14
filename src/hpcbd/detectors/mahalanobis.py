"""Shrinkage Mahalanobis distance detector (Ledoit-Wolf covariance estimation)."""

from __future__ import annotations

import numpy as np
from sklearn.covariance import LedoitWolf


class MahalanobisDetector:
    """Anomaly detector based on Mahalanobis distance with Ledoit-Wolf shrinkage.

    Score convention: higher score → more anomalous.
    """

    def __init__(self, shrinkage: str = "ledoit_wolf") -> None:
        self.shrinkage = shrinkage
        self._lw: LedoitWolf | None = None
        self._mean: np.ndarray | None = None
        self._precision: np.ndarray | None = None

    def fit(self, X: np.ndarray) -> "MahalanobisDetector":
        """Fit Ledoit-Wolf covariance estimator on X.

        Parameters
        ----------
        X : array of shape (n_samples, n_features)
        """
        self._lw = LedoitWolf(assume_centered=False)
        self._lw.fit(X)
        self._mean = self._lw.location_
        self._precision = self._lw.precision_
        return self

    def score(self, X: np.ndarray) -> np.ndarray:
        """Compute Mahalanobis distance for each sample.

        Parameters
        ----------
        X : array of shape (n_samples, n_features)

        Returns
        -------
        scores : array of shape (n_samples,)
            Mahalanobis distance — higher is more anomalous.
        """
        if self._lw is None:
            raise RuntimeError("Detector not fitted. Call fit() first.")
        diff = X - self._mean  # (n, p)
        # Mahalanobis^2 = diff @ precision @ diff.T (diagonal)
        maha_sq = np.einsum("ij,jk,ik->i", diff, self._precision, diff)
        return np.sqrt(np.maximum(maha_sq, 0.0))
