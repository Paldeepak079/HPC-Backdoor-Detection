"""Optional River streaming detector."""

from __future__ import annotations

from typing import Any

import numpy as np
from river import anomaly


class RiverHalfSpaceTreesDetector:
    """River Half-Space Trees with explicit prequential scoring.

    ``score`` is read-only after ``fit``.  Use ``score_stream`` for online
    operation; it scores each row before learning that row.
    """

    def __init__(
        self,
        n_trees: int = 25,
        height: int = 8,
        window_size: int = 250,
        seed: int = 42,
    ) -> None:
        self.n_trees = n_trees
        self.height = height
        self.window_size = window_size
        self.seed = seed
        self._model: Any | None = None

    def _new_model(self) -> Any:
        return anomaly.HalfSpaceTrees(
            n_trees=self.n_trees,
            height=self.height,
            window_size=self.window_size,
            seed=self.seed,
        )

    def fit(self, X: np.ndarray) -> "RiverHalfSpaceTreesDetector":
        self._model = self._new_model()
        for row in np.asarray(X, dtype=float):
            self._model.learn_one({i: float(value) for i, value in enumerate(row)})
        return self

    def score(self, X: np.ndarray) -> np.ndarray:
        if self._model is None:
            raise RuntimeError("Detector not fitted. Call fit() first.")
        return np.asarray(
            [
                self._model.score_one({i: float(value) for i, value in enumerate(row)})
                for row in np.asarray(X, dtype=float)
            ],
            dtype=float,
        )

    def score_stream(self, X: np.ndarray) -> np.ndarray:
        """Return prequential scores and update the model after each row."""
        if self._model is None:
            self._model = self._new_model()
        scores = []
        for row in np.asarray(X, dtype=float):
            features = {i: float(value) for i, value in enumerate(row)}
            scores.append(float(self._model.score_one(features)))
            self._model.learn_one(features)
        return np.asarray(scores, dtype=float)
