"""k-NN distance anomaly detector."""

from __future__ import annotations

import numpy as np
from sklearn.neighbors import NearestNeighbors


class KNNDetector:
    """Anomaly detector based on mean k-nearest-neighbour distance.

    Score convention: higher score → more anomalous.
    """

    def __init__(self, k: int = 10, metric: str = "euclidean") -> None:
        self.k = k
        self.metric = metric
        self._nn: NearestNeighbors | None = None

    def fit(self, X: np.ndarray) -> "KNNDetector":
        """Fit kNN index on X.

        Parameters
        ----------
        X : array of shape (n_samples, n_features)
        """
        k_actual = min(self.k, X.shape[0] - 1)
        self._nn = NearestNeighbors(n_neighbors=k_actual + 1, metric=self.metric)
        self._nn.fit(X)
        self._k_actual = k_actual
        return self

    def score(self, X: np.ndarray) -> np.ndarray:
        """Compute mean distance to k nearest neighbours.

        Parameters
        ----------
        X : array of shape (n_samples, n_features)

        Returns
        -------
        scores : array of shape (n_samples,)
        """
        if self._nn is None:
            raise RuntimeError("Detector not fitted. Call fit() first.")
        # First neighbour is the point itself when scoring training data
        distances, _ = self._nn.kneighbors(X)
        # Exclude self (index 0) and average over k neighbours
        mean_dist = distances[:, 1:self._k_actual + 1].mean(axis=1)
        return mean_dist
