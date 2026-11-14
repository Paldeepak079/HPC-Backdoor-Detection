from __future__ import annotations

import numpy as np
import pandas as pd

from experiments import run_experiments


class IdentityPreprocessor:
    def __init__(self, *args, **kwargs) -> None:
        pass

    def fit_transform(self, frame: pd.DataFrame) -> np.ndarray:
        return frame.to_numpy(dtype=float)

    def transform(self, frame: pd.DataFrame) -> np.ndarray:
        return frame.to_numpy(dtype=float)


class IdentityDetector:
    def fit(self, X: np.ndarray) -> "IdentityDetector":
        return self

    def score(self, X: np.ndarray) -> np.ndarray:
        return X[:, 0]


def test_repeated_oof_raw_scores_are_per_sample_means(monkeypatch) -> None:
    frame = pd.DataFrame({
        "cache-references": np.arange(10, dtype=float),
        "cycles": np.arange(10, dtype=float) + 10,
        "LLC-loads": np.arange(10, dtype=float) + 20,
    })
    monkeypatch.setattr(run_experiments, "load_csv", lambda _: frame)
    monkeypatch.setattr(run_experiments, "Preprocessor", IdentityPreprocessor)
    monkeypatch.setattr(
        run_experiments,
        "make_detectors",
        lambda seed=42, detector_config=None: {"identity": IdentityDetector()},
    )

    result = run_experiments.run_experiments(cv_folds=2, cv_repeats=3)

    assert len(result["oof_scores"]["identity"]) == len(frame)
    assert np.allclose(result["raw_oof_scores"]["identity"], frame["cache-references"])


def test_default_detector_configuration_uses_the_two_selected_detectors() -> None:
    assert set(run_experiments.make_detectors()) == {"mahalanobis", "pca"}


def test_benign_oof_flag_rate_is_within_alpha_tolerance() -> None:
    result = run_experiments.run_experiments(
        data_path="HPC traces/trace.csv",
        detector_config={
            "mahalanobis": {"enabled": True},
            "pca": {"enabled": True, "variance_threshold": 0.95},
        },
    )
    fused_oof = np.asarray(result["fused_oof"])
    flag_rate = np.mean(fused_oof > result["tau"])

    assert 0.03 <= flag_rate <= 0.08
