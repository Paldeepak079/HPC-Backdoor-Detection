from __future__ import annotations

import sys

import pandas as pd
import pytest

import predict
import stream_predict


def test_predict_exits_nonzero_for_malformed_csv(monkeypatch, tmp_path, capsys) -> None:
    malformed = tmp_path / "missing.csv"
    pd.DataFrame({"cache-references": [1], "cycles": [2]}).to_csv(malformed, index=False)
    monkeypatch.setattr(predict, "load_artifact", lambda _: (None, None, 1.0, 0.05, ["cache-references", "cycles", "LLC-loads"], {}))
    monkeypatch.setattr(sys, "argv", ["predict.py", "--input", str(malformed), "--artifact", "unused"])

    with pytest.raises(SystemExit) as exit_info:
        predict.main()

    assert exit_info.value.code == 2
    assert "invalid input CSV" in capsys.readouterr().err


def test_stream_predict_exits_nonzero_for_malformed_csv(monkeypatch, tmp_path, capsys) -> None:
    malformed = tmp_path / "nan.csv"
    pd.DataFrame({"cache-references": [1], "cycles": [float("nan")], "LLC-loads": [3]}).to_csv(malformed, index=False)
    monkeypatch.setattr(
        sys,
        "argv",
        ["stream_predict.py", "--reference", str(malformed), "--input", str(malformed)],
    )

    with pytest.raises(SystemExit) as exit_info:
        stream_predict.main()

    assert exit_info.value.code == 2
    assert "invalid input CSV" in capsys.readouterr().err
