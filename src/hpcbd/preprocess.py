"""Preprocessing pipeline: drop constants → log1p → robust scale + ratio features."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd


class Preprocessor:
    """Fit-transform pipeline for HPC trace features.

    Steps
    -----
    1. Drop constant columns.
    2. Add ratio features (LLC-loads/cache-refs, LLC-loads/cycles,
       cache-refs/cycles) if ``add_ratios=True``.
    3. log1p transform (shift to ensure positivity first).
    4. Robust scaling: (x - median) / IQR.
    """

    def __init__(
        self,
        add_ratios: bool = True,
        transform: str = "log1p",
        scaler: str = "robust",
    ) -> None:
        self.add_ratios = add_ratios
        # Do not call this attribute ``transform``: that would shadow the
        # public transform() method on the fitted instance.
        self.transform_name = transform
        self.scaler = scaler

        # Fitted state
        self._constant_cols: list[str] = []
        self._feature_cols: list[str] = []
        self._shifts: dict[str, float] = {}
        self._medians: dict[str, float] = {}
        self._iqrs: dict[str, float] = {}
        self._fitted = False

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _add_ratio_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add ratio columns if source columns are present."""
        df = df.copy()
        cr = "cache-references"
        cy = "cycles"
        llc = "LLC-loads"

        if llc in df.columns and cr in df.columns:
            denom = df[cr].replace(0, np.nan)
            df["llc_per_cache_ref"] = df[llc] / denom

        if llc in df.columns and cy in df.columns:
            denom = df[cy].replace(0, np.nan)
            df["llc_per_cycle"] = df[llc] / denom

        if cr in df.columns and cy in df.columns:
            denom = df[cy].replace(0, np.nan)
            df["cache_ref_per_cycle"] = df[cr] / denom

        # Fill NaN introduced by zero denominators
        for col in ["llc_per_cache_ref", "llc_per_cycle", "cache_ref_per_cycle"]:
            if col in df.columns:
                df[col] = df[col].fillna(0.0)

        return df

    def _drop_constants(self, df: pd.DataFrame) -> pd.DataFrame:
        return df.drop(columns=self._constant_cols, errors="ignore")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fit(self, X: pd.DataFrame) -> "Preprocessor":
        """Fit preprocessing parameters on X."""
        df = X.copy()

        if self.add_ratios:
            df = self._add_ratio_features(df)

        # Identify constant columns
        self._constant_cols = [c for c in df.columns if df[c].nunique() <= 1]
        df = self._drop_constants(df)

        self._feature_cols = list(df.columns)

        # Compute shifts for log1p (ensure non-negative)
        self._shifts = {}
        for col in self._feature_cols:
            min_val = df[col].min()
            self._shifts[col] = max(0.0, -float(min_val)) if min_val < 0 else 0.0

        # Apply log1p
        df_t = df.copy()
        for col in self._feature_cols:
            df_t[col] = np.log1p(df_t[col] + self._shifts[col])

        # Compute robust scaling parameters
        self._medians = {}
        self._iqrs = {}
        for col in self._feature_cols:
            vals = df_t[col].dropna().to_numpy(dtype=float)
            self._medians[col] = float(np.median(vals))
            q75, q25 = np.percentile(vals, [75, 25])
            iqr = float(q75 - q25)
            self._iqrs[col] = iqr if iqr > 1e-10 else 1.0  # guard zero IQR

        self._fitted = True
        return self

    def transform(self, X: pd.DataFrame) -> np.ndarray:
        """Transform X using fitted parameters.

        Parameters
        ----------
        X : pd.DataFrame
        
        Returns
        -------
        np.ndarray of shape (n_samples, n_features)
        """
        if not self._fitted:
            raise RuntimeError("Preprocessor is not fitted. Call fit() first.")

        df = X.copy()
        if self.add_ratios:
            df = self._add_ratio_features(df)
        df = self._drop_constants(df)

        missing = [col for col in self._feature_cols if col not in df.columns]
        if missing:
            raise ValueError(f"Missing fitted feature columns after preprocessing: {missing}")
        df = df.reindex(columns=self._feature_cols)

        # log1p
        for col in self._feature_cols:
            df[col] = np.log1p(df[col] + self._shifts.get(col, 0.0))

        # Robust scale
        for col in self._feature_cols:
            df[col] = (df[col] - self._medians[col]) / self._iqrs[col]

        values = df.to_numpy(dtype=float)
        if not np.isfinite(values).all():
            raise ValueError("Preprocessing produced non-finite values; check input values and ratios.")
        return values

    def fit_transform(self, X: pd.DataFrame) -> np.ndarray:
        """Fit then transform X."""
        return self.fit(X).transform(X)

    @property
    def feature_names(self) -> list[str]:
        return list(self._feature_cols)

    def save(self, path: str | os.PathLike) -> None:
        """Persist preprocessor to disk using joblib."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)

    @classmethod
    def load(cls, path: str | os.PathLike) -> "Preprocessor":
        """Load preprocessor from disk."""
        return joblib.load(path)
