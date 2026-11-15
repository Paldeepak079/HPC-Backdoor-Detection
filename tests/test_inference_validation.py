from __future__ import annotations

import sys

import pandas as pd
import pytest

import predict
import stream_predict


class _FakePreprocessor:
    def transform(self, frame: pd.DataFrame):
        assert list(frame.columns) == ["cache-references", "cycles", "LLC-loads"]
        return frame.to_numpy(dtype=float)


class _FakeDetector:
    def score(self, values):
        size = len(values)
        return (
            pd.Series([0.5] * size).to_numpy(),
            {"mahalanobis": pd.Series([0.25] * size).to_numpy()},
        )


@pytest.mark.parametrize(
    ("row_count", "columns"),
    [
        (1, ["cache-references", "cycles", "LLC-loads"]),
        (800, ["cache-references", "cycles", "LLC-loads"]),
        (3, ["cycles", "LLC-loads", "cache-references"]),
        (2, ["cache-references", "cycles", "LLC-loads", "label"]),
        (2, ["cache-references", "cycles", "LLC-loads", "trace_name"]),
    ],
)
def test_predict_preserves_extra_columns_and_feature_order(
    monkeypatch, tmp_path, row_count, columns
) -> None:
    values = {
        "cache-references": list(range(1, row_count + 1)),
        "cycles": list(range(101, row_count + 101)),
        "LLC-loads": list(range(201, row_count + 201)),
        "label": [0, 1] * (row_count // 2) + [0] * (row_count % 2),
        "trace_name": [f"trace-{index}" for index in range(row_count)],
    }
    frame = pd.DataFrame({column: values[column] for column in columns})
    input_path = tmp_path / "input.csv"
    output_path = tmp_path / "output.csv"
    frame.to_csv(input_path, index=False)
    monkeypatch.setattr(
        predict,
        "load_artifact",
        lambda _: (_FakeDetector(), _FakePreprocessor(), 1.0, 0.05, [
            "cache-references", "cycles", "LLC-loads"
        ], {}),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["predict.py", "--input", str(input_path), "--artifact", "unused", "--out", str(output_path)],
    )

    predict.main()

    result = pd.read_csv(output_path)
    assert list(result.columns[: len(columns)]) == columns
    pd.testing.assert_frame_equal(result[columns], frame, check_dtype=False)
    assert len(result) == row_count
    assert "score" in result
    if "label" in frame:
        assert result["label"].tolist() == frame["label"].tolist()
        assert "prediction_label" in result
    else:
        assert "label" in result
    if "trace_name" in frame:
        assert result["trace_name"].tolist() == frame["trace_name"].tolist()


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
