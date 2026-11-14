"""I/O utilities: CSV loading and schema validation."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class SchemaMismatchError(Exception):
    """Raised when DataFrame columns do not match the expected schema."""


class NonFiniteValueError(Exception):
    """Raised when DataFrame contains NaN or infinite values after loading."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

DEFAULT_SCHEMA: list[str] = ["cache-references", "cycles", "LLC-loads"]


def load_csv(path: str | os.PathLike, *, schema: list[str] | None = None) -> pd.DataFrame:
    """Load a CSV file, validate schema and finite values, return DataFrame.

    Parameters
    ----------
    path : path-like
        Path to the CSV file.
    schema : list[str] | None
        Expected column names. Defaults to DEFAULT_SCHEMA.

    Returns
    -------
    pd.DataFrame
        Loaded and validated DataFrame.

    Raises
    ------
    FileNotFoundError
        If the file does not exist.
    SchemaMismatchError
        If columns don't match the schema.
    NonFiniteValueError
        If any non-finite values are found.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {path}")

    df = pd.read_csv(path)

    # Coerce all numeric columns
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Validate schema
    if schema is None:
        schema = DEFAULT_SCHEMA
    validate_schema(df, schema)

    # Check for non-finite values
    for col in df.columns:
        n_nan = df[col].isna().sum()
        n_inf = np.isinf(df[col].fillna(0)).sum()
        if n_nan > 0 or n_inf > 0:
            raise NonFiniteValueError(
                f"Column '{col}' has {n_nan} NaN and {n_inf} Inf values."
            )

    return df.reset_index(drop=True)


def validate_schema(df: pd.DataFrame, schema: Sequence[str]) -> None:
    """Validate that DataFrame has exactly the expected columns.

    Parameters
    ----------
    df : pd.DataFrame
    schema : sequence of str
        Expected column names (order-insensitive).

    Raises
    ------
    SchemaMismatchError
    """
    expected = set(schema)
    actual = set(df.columns)
    missing = expected - actual
    extra = actual - expected
    if missing or extra:
        msg_parts = []
        if missing:
            msg_parts.append(f"missing columns: {sorted(missing)}")
        if extra:
            msg_parts.append(f"unexpected columns: {sorted(extra)}")
        raise SchemaMismatchError("; ".join(msg_parts))
