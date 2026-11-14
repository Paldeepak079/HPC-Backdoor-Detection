from __future__ import annotations

import numpy as np
import joblib

from hpcbd.detectors.pca import PCADetector


def test_score_is_invariant_to_scoring_batch_and_persistence(tmp_path) -> None:
    rng = np.random.default_rng(42)
    detector = PCADetector().fit(rng.normal(size=(80, 6)))
    batch = rng.normal(size=(12, 6))
    path = tmp_path / "pca.joblib"
    joblib.dump(detector, path)
    restored = joblib.load(path)

    assert detector.score(batch[:1])[0] == detector.score(batch)[0]
    assert restored.score(batch[:1])[0] == restored.score(batch)[0]
