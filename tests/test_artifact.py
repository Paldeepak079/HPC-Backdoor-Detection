from __future__ import annotations

import numpy as np
import pandas as pd

from hpcbd.artifact import load_artifact, save_artifact
from hpcbd.preprocess import Preprocessor


class DummyDetector:
    def score(self, X: np.ndarray) -> tuple[np.ndarray, dict[str, np.ndarray]]:
        return np.zeros(len(X)), {}


def test_artifact_round_trip_verifies_hashes(tmp_path) -> None:
    frame = pd.DataFrame({
        "cache-references": [1.0, 2.0, 3.0],
        "cycles": [4.0, 5.0, 6.0],
        "LLC-loads": [7.0, 8.0, 9.0],
    })
    preprocessor = Preprocessor().fit(frame)
    save_artifact(
        detector=DummyDetector(),
        preprocessor=preprocessor,
        tau=1.0,
        alpha=0.05,
        schema=list(frame.columns),
        config={"seed": 42},
        path=tmp_path,
    )

    detector, loaded_preprocessor, tau, alpha, schema, config = load_artifact(tmp_path)

    assert isinstance(detector, DummyDetector)
    assert loaded_preprocessor.feature_names == preprocessor.feature_names
    assert (tau, alpha, schema, config) == (1.0, 0.05, list(frame.columns), {"seed": 42})
