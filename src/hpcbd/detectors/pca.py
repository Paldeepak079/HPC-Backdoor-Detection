"""PCA reconstruction error + Hotelling T² detector."""

from __future__ import annotations

import numpy as np
from sklearn.decomposition import PCA


class PCADetector:
    """Anomaly detector combining PCA reconstruction error and Hotelling T².

    Score convention: higher score → more anomalous.
    """

    def __init__(self, variance_threshold: float = 0.95) -> None:
        self.variance_threshold = variance_threshold
        self._pca: PCA | None = None
        self._n_components: int = 0

    def fit(self, X: np.ndarray) -> "PCADetector":
        """Fit PCA retaining enough components to explain ``variance_threshold`` variance.

        Parameters
        ----------
        X : array of shape (n_samples, n_features)
        """
        # First fit to find n_components
        pca_full = PCA().fit(X)
        cumvar = np.cumsum(pca_full.explained_variance_ratio_)
        n_comp = int(np.searchsorted(cumvar, self.variance_threshold) + 1)
        n_comp = min(n_comp, X.shape[1], X.shape[0] - 1)
        n_comp = max(n_comp, 1)

        self._n_components = n_comp
        self._pca = PCA(n_components=n_comp)
        self._pca.fit(X)
        return self

    def score(self, X: np.ndarray) -> np.ndarray:
        """Compute combined anomaly score.

        Score = reconstruction_error + Hotelling T² (in PC space).

        Parameters
        ----------
        X : array of shape (n_samples, n_features)

        Returns
        -------
        scores : array of shape (n_samples,)
        """
        if self._pca is None:
            raise RuntimeError("Detector not fitted. Call fit() first.")

        # Project and reconstruct
        X_proj = self._pca.transform(X)         # (n, k)
        X_recon = self._pca.inverse_transform(X_proj)  # (n, p)

        # Reconstruction error (MSE per sample)
        recon_err = np.mean((X - X_recon) ** 2, axis=1)

        # Hotelling T² in the PC subspace
        # Variance of each PC from training
        pc_var = self._pca.explained_variance_  # (k,)
        pc_var = np.maximum(pc_var, 1e-10)
        t2 = np.sum(X_proj ** 2 / pc_var, axis=1)

        # Normalize both to comparable scale then sum
        # Simple combination: z-score both and sum
        def _normalize(arr):
            std = arr.std()
            if std < 1e-10:
                return arr - arr.mean()
            return (arr - arr.mean()) / std

        score = _normalize(recon_err) + _normalize(t2)
        return score
