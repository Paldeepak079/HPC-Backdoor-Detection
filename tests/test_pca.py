from __future__ import annotations

import numpy as np

from hpcbd.detectors.pca import PCADetector


def test_score_is_invariant_to_scoring_batch() -> None:
    rng = np.random.default_rng(42)
    detector = PCADetector().fit(rng.normal(size=(80, 6)))
    batch = rng.normal(size=(12, 6))

    assert detector.score(batch[:1])[0] == detector.score(batch)[0]
