from __future__ import annotations

import pandas as pd
import pytest

from hpcbd.io import NonFiniteValueError, SchemaMismatchError, load_csv


def test_load_csv_rejects_missing_required_column(tmp_path) -> None:
    path = tmp_path / "missing.csv"
    pd.DataFrame({"cache-references": [1], "cycles": [2]}).to_csv(path, index=False)

    with pytest.raises(SchemaMismatchError, match="missing columns"):
        load_csv(path)


def test_load_csv_rejects_nan(tmp_path) -> None:
    path = tmp_path / "nan.csv"
    pd.DataFrame({"cache-references": [1], "cycles": [float("nan")], "LLC-loads": [3]}).to_csv(path, index=False)

    with pytest.raises(NonFiniteValueError, match="cycles.*NaN"):
        load_csv(path)
