"""Isolation Forest anomaly detector wrapper."""

from __future__ import annotations

import numpy as np
from sklearn.ensemble import IsolationForest


class IForestDetector:
    """Anomaly detector based on Isolation Forest.

    Score convention: higher score → more anomalous
    (negated decision_function so that outliers have high scores).
    """

    def __init__(
        self,
        n_estimators: int = 200,
        max_samples: int | str = 256,
        random_state: int = 42,
        contamination: float = "auto",
    ) -> None:
        self.n_estimators = n_estimators
        self.max_samples = max_samples
        self.random_state = random_state
        self.contamination = contamination
        self._model: IsolationForest | None = None

    def fit(self, X: np.ndarray) -> "IForestDetector":
        self._model = IsolationForest(
            n_estimators=self.n_estimators,
            max_samples=self.max_samples,
            random_state=self.random_state,
            contamination=self.contamination,
        )
        self._model.fit(X)
        return self

    def score(self, X: np.ndarray) -> np.ndarray:
        """Return anomaly scores (higher = more anomalous).

        Parameters
        ----------
        X : array of shape (n_samples, n_features)

        Returns
        -------
        scores : array of shape (n_samples,)
        """
        if self._model is None:
            raise RuntimeError("Detector not fitted. Call fit() first.")
        # decision_function: negative means outlier → negate so higher=more anomalous
        return -self._model.decision_function(X)
