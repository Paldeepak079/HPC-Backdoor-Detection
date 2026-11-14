from __future__ import annotations

import numpy as np
import pytest
from sklearn.metrics import roc_auc_score

from hpcbd.metrics import _auroc


@pytest.mark.xfail(reason="M8 in report.md: _auroc does not handle tied scores correctly.")
def test_auroc_matches_sklearn_when_scores_tie() -> None:
    y_true = np.array([0, 1, 0, 1])
    scores = np.array([0.5, 0.5, 0.2, 0.2])

    assert _auroc(y_true, scores) == roc_auc_score(y_true, scores)
