"""Data auditing utilities."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats


def audit(df: pd.DataFrame) -> dict[str, Any]:
    """Compute comprehensive audit statistics for a DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        Input data (all numeric columns expected).

    Returns
    -------
    dict
        Audit report with shape, dtypes, missing value counts, per-column
        statistics, correlation matrix, and autocorrelation lags.
    """
    report: dict[str, Any] = {}

    # Basic shape
    report["shape"] = list(df.shape)
    report["dtypes"] = {col: str(dtype) for col, dtype in df.dtypes.items()}

    # Missing / infinite
    report["nan_counts"] = df.isna().sum().to_dict()
    report["inf_counts"] = {
        col: int(np.isinf(df[col].fillna(0)).sum()) for col in df.columns
    }

    # Constant columns
    report["constant_cols"] = [
        col for col in df.columns if df[col].nunique() <= 1
    ]

    # Duplicate rows
    report["duplicate_rows"] = int(df.duplicated().sum())

    # Per-column statistics
    per_col: dict[str, Any] = {}
    for col in df.columns:
        s = df[col].dropna()
        arr = s.to_numpy(dtype=float)
        q25, q50, q75 = np.percentile(arr, [25, 50, 75]) if len(arr) else (np.nan,) * 3
        per_col[col] = {
            "mean": float(arr.mean()) if len(arr) else None,
            "std": float(arr.std(ddof=1)) if len(arr) > 1 else None,
            "skew": float(stats.skew(arr)) if len(arr) > 2 else None,
            "kurtosis": float(stats.kurtosis(arr)) if len(arr) > 3 else None,
            "min": float(arr.min()) if len(arr) else None,
            "max": float(arr.max()) if len(arr) else None,
            "q25": float(q25),
            "q50": float(q50),
            "q75": float(q75),
        }
    report["per_column_stats"] = per_col

    # Correlation matrix
    corr = df.corr(numeric_only=True)
    report["correlation_matrix"] = corr.to_dict()

    # Autocorrelation (lag 1-10 for each column)
    autocorr: dict[str, Any] = {}
    for col in df.columns:
        s = df[col].dropna()
        autocorr[col] = {
            str(lag): float(s.autocorr(lag=lag))
            for lag in range(1, min(11, len(s)))
        }
    report["autocorrelation"] = autocorr

    return report


def _make_finite(obj: Any) -> Any:
    """Recursively replace non-finite floats with None for JSON serialization."""
    if isinstance(obj, dict):
        return {k: _make_finite(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_make_finite(v) for v in obj]
    if isinstance(obj, float):
        if np.isnan(obj) or np.isinf(obj):
            return None
    return obj


def save_audit(audit_dict: dict[str, Any], path: str | Path) -> None:
    """Save the audit report as both JSON and Markdown.

    Parameters
    ----------
    audit_dict : dict
        Output of :func:`audit`.
    path : path-like
        Base path (without extension). Files ``<path>.json`` and
        ``<path>.md`` will be created.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Save JSON
    clean = _make_finite(audit_dict)
    json_path = path.with_suffix(".json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(clean, f, indent=2)

    # Save Markdown
    md_path = path.with_suffix(".md")
    lines = ["# Data Audit Report\n"]
    shape = audit_dict.get("shape", [])
    lines.append(f"**Shape:** {shape[0]} rows × {shape[1]} columns\n")
    lines.append(f"**Duplicate rows:** {audit_dict.get('duplicate_rows', 0)}\n")

    # Constant cols
    const = audit_dict.get("constant_cols", [])
    lines.append(f"**Constant columns:** {const if const else 'none'}\n")

    # Per-column stats
    lines.append("\n## Per-Column Statistics\n")
    pcs = audit_dict.get("per_column_stats", {})
    if pcs:
        header_cols = ["Column", "Mean", "Std", "Skew", "Kurt", "Min", "Max", "Q50"]
        lines.append("| " + " | ".join(header_cols) + " |")
        lines.append("|" + "|".join(["---"] * len(header_cols)) + "|")
        for col, s in pcs.items():
            def fmt(v):
                return f"{v:.4g}" if v is not None else "N/A"
            lines.append(
                f"| {col} | {fmt(s['mean'])} | {fmt(s['std'])} | "
                f"{fmt(s['skew'])} | {fmt(s['kurtosis'])} | "
                f"{fmt(s['min'])} | {fmt(s['max'])} | {fmt(s['q50'])} |"
            )

    # Correlation matrix
    lines.append("\n## Correlation Matrix\n")
    corr = audit_dict.get("correlation_matrix", {})
    if corr:
        cols = list(corr.keys())
        lines.append("| | " + " | ".join(cols) + " |")
        lines.append("|" + "|".join(["---"] * (len(cols) + 1)) + "|")
        for row_col in cols:
            vals = [f"{corr[row_col].get(c, float('nan')):.4f}" for c in cols]
            lines.append(f"| {row_col} | " + " | ".join(vals) + " |")

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
