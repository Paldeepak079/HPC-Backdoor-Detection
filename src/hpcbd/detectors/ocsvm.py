"""One-Class SVM anomaly detector."""

from __future__ import annotations

import numpy as np
from sklearn.svm import OneClassSVM


class OCSVMDetector:
    """Anomaly detector based on One-Class SVM.

    Score convention: higher score → more anomalous
    (negated decision_function so outliers get high positive scores).
    """

    def __init__(
        self,
        nu: float = 0.05,
        kernel: str = "rbf",
        gamma: str = "scale",
    ) -> None:
        self.nu = nu
        self.kernel = kernel
        self.gamma = gamma
        self._model: OneClassSVM | None = None

    def fit(self, X: np.ndarray) -> "OCSVMDetector":
        """Fit One-Class SVM on X.

        Parameters
        ----------
        X : array of shape (n_samples, n_features)
        """
        self._model = OneClassSVM(
            nu=self.nu,
            kernel=self.kernel,
            gamma=self.gamma,
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
        # decision_function < 0 means outlier; negate so outliers → high positive
        return -self._model.decision_function(X)
