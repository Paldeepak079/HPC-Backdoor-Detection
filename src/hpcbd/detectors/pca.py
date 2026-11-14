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
        self._recon_mean = 0.0
        self._recon_std = 1.0
        self._t2_mean = 0.0
        self._t2_std = 1.0

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
        train_proj = self._pca.transform(X)
        train_recon = self._pca.inverse_transform(train_proj)
        train_recon_err = np.mean((X - train_recon) ** 2, axis=1)
        pc_var = np.maximum(self._pca.explained_variance_, 1e-10)
        train_t2 = np.sum(train_proj ** 2 / pc_var, axis=1)
        self._recon_mean = float(train_recon_err.mean())
        self._recon_std = max(float(train_recon_err.std()), 1e-10)
        self._t2_mean = float(train_t2.mean())
        self._t2_std = max(float(train_t2.std()), 1e-10)
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

        # Normalize against the fitted training reference, not the scoring batch.
        score = ((recon_err - self._recon_mean) / self._recon_std
                 + (t2 - self._t2_mean) / self._t2_std)
        return score
