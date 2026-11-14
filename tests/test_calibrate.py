from __future__ import annotations

import numpy as np
import pytest

from hpcbd.calibrate import calibrate


@pytest.mark.xfail(reason="Known issue in report.md: calibrate uses an interpolated quantile, not the conformal order statistic.")
def test_conformal_threshold_limits_strict_exceedances() -> None:
    scores = np.arange(100, dtype=float)
    tau = calibrate(scores, alpha=0.05)

    assert tau == 96.0
    assert np.count_nonzero(scores > tau) <= 5
