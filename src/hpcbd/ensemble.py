"""Score normalisation and ensemble fusion."""

from __future__ import annotations

from typing import Any

import numpy as np
from scipy.interpolate import interp1d


def normalise_scores(
    scores: np.ndarray,
    oof_scores: np.ndarray,
) -> np.ndarray:
    """Transform raw scores to [0, ∞) via empirical CDF → -log(1-F).

    Uses the OOF (out-of-fold) scores to build the empirical CDF, then
    maps new ``scores`` through that CDF and applies the -log(1-F)
    transform so the final values are in [0, ∞) with higher = more anomalous.

    Parameters
    ----------
    scores : array of shape (n,)
        New scores to normalise.
    oof_scores : array of shape (m,)
        Reference distribution (out-of-fold training scores).

    Returns
    -------
    normalised : array of shape (n,)
    """
    oof_sorted = np.sort(oof_scores)
    n = len(oof_sorted)
    # Empirical CDF values at sorted positions
    ecdf_vals = (np.arange(1, n + 1)) / n  # (0, 1]

    # Build interpolator; extrapolate beyond range with boundary values
    if n >= 2:
        interp = interp1d(
            oof_sorted,
            ecdf_vals,
            kind="linear",
            bounds_error=False,
            fill_value=(ecdf_vals[0], ecdf_vals[-1]),
        )
        F = interp(scores)
    else:
        F = np.full_like(scores, 0.5, dtype=float)

    # Clip to [epsilon, 1-epsilon] to avoid log(0)
    eps = 1e-6
    F = np.clip(F, eps, 1.0 - eps)
    return -np.log(1.0 - F)


def fuse_scores(
    normalised_scores_dict: dict[str, np.ndarray],
    rule: str = "mean",
    rank_references: dict[str, np.ndarray] | None = None,
) -> np.ndarray:
    """Fuse per-detector normalised scores into a single ensemble score.

    Parameters
    ----------
    normalised_scores_dict : dict str → array(n,)
        Mapping of detector name to normalised score array.
    rule : {'mean', 'max', 'rank_mean'}
        Fusion rule.

    Returns
    -------
    fused : array of shape (n,)
    """
    if not normalised_scores_dict:
        raise ValueError("normalised_scores_dict is empty.")

    matrix = np.stack(list(normalised_scores_dict.values()), axis=1)  # (n, d)

    if rule == "mean":
        return matrix.mean(axis=1)
    elif rule == "max":
        return matrix.max(axis=1)
    elif rule == "rank_mean":
        if rank_references is None:
            raise ValueError("rank_mean requires OOF rank_references.")
        ranks = []
        for name, values in normalised_scores_dict.items():
            reference = np.sort(np.asarray(rank_references[name], dtype=float))
            if not len(reference):
                raise ValueError(f"rank_mean reference for {name!r} is empty.")
            ranks.append(np.searchsorted(reference, values, side="right") / len(reference))
        return np.stack(ranks, axis=1).mean(axis=1)
    else:
        raise ValueError(f"Unknown fusion rule: {rule!r}. Choose 'mean', 'max', or 'rank_mean'.")


class EnsembleDetector:
    """Wrapper that fits multiple detectors and fuses their scores.

    Parameters
    ----------
    detectors : dict str → detector instance
        Detector objects with fit(X) and score(X) methods.
    fusion_rule : str
        Passed to :func:`fuse_scores`.
    """

    def __init__(
        self,
        detectors: dict[str, Any],
        fusion_rule: str = "mean",
    ) -> None:
        self.detectors = detectors
        self.fusion_rule = fusion_rule
        self._oof_scores: dict[str, np.ndarray] = {}
        self._rank_references: dict[str, np.ndarray] = {}
        self._fitted = False

    def fit(self, X: np.ndarray, oof_scores: dict[str, np.ndarray] | None = None) -> "EnsembleDetector":
        """Fit all constituent detectors.

        Parameters
        ----------
        X : array of shape (n_samples, n_features)
        oof_scores : dict | None
            Pre-computed OOF scores for normalisation. If None, training scores
            are used as the reference distribution.
        """
        for name, det in self.detectors.items():
            det.fit(X)

        # Store reference distributions for normalisation
        for name, det in self.detectors.items():
            ref = oof_scores.get(name) if oof_scores else None
            if ref is None:
                ref = det.score(X)
            self._oof_scores[name] = ref
            self._rank_references[name] = normalise_scores(ref, ref)

        self._fitted = True
        return self

    def score(self, X: np.ndarray) -> tuple[np.ndarray, dict[str, np.ndarray]]:
        """Score samples and return fused score + per-detector normalised scores.

        Returns
        -------
        fused : array of shape (n,)
        per_detector : dict str → array(n,)
        """
        if not self._fitted:
            raise RuntimeError("EnsembleDetector not fitted. Call fit() first.")

        raw: dict[str, np.ndarray] = {}
        normalised: dict[str, np.ndarray] = {}

        for name, det in self.detectors.items():
            raw[name] = det.score(X)
            normalised[name] = normalise_scores(raw[name], self._oof_scores[name])

        fused = fuse_scores(
            normalised,
            rule=self.fusion_rule,
            rank_references=self._rank_references,
        )
        return fused, normalised
