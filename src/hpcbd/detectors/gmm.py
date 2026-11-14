"""GMM log-likelihood anomaly detector with BIC model selection."""

from __future__ import annotations

import numpy as np
from sklearn.mixture import GaussianMixture


class GMMDetector:
    """Anomaly detector based on Gaussian Mixture Model log-likelihood.

    Uses BIC to select the optimal number of components.

    Score convention: higher score → more anomalous
    (negated log-likelihood so that unlikely points have high scores).
    """

    def __init__(
        self,
        max_components: int = 6,
        random_state: int = 42,
        covariance_type: str = "full",
    ) -> None:
        self.max_components = max_components
        self.random_state = random_state
        self.covariance_type = covariance_type
        self._model: GaussianMixture | None = None
        self._best_n: int = 1

    def fit(self, X: np.ndarray) -> "GMMDetector":
        """Fit GMM with BIC-selected number of components.

        Parameters
        ----------
        X : array of shape (n_samples, n_features)
        """
        max_n = min(self.max_components, X.shape[0] // 5, X.shape[0] - 1)
        max_n = max(max_n, 1)

        best_bic = np.inf
        best_model = None
        best_n = 1

        for n in range(1, max_n + 1):
            try:
                gm = GaussianMixture(
                    n_components=n,
                    covariance_type=self.covariance_type,
                    random_state=self.random_state,
                    n_init=3,
                    max_iter=200,
                )
                gm.fit(X)
                bic = gm.bic(X)
                if bic < best_bic:
                    best_bic = bic
                    best_model = gm
                    best_n = n
            except Exception:
                break

        self._model = best_model
        self._best_n = best_n
        return self

    def score(self, X: np.ndarray) -> np.ndarray:
        """Compute negative log-likelihood scores.

        Parameters
        ----------
        X : array of shape (n_samples, n_features)

        Returns
        -------
        scores : array of shape (n_samples,)
            Negative log-likelihood — higher means less likely under GMM.
        """
        if self._model is None:
            raise RuntimeError("Detector not fitted. Call fit() first.")
        log_prob = self._model.score_samples(X)  # log-likelihood per sample
        return -log_prob  # negate: higher = more anomalous
