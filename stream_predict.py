"""Prequential River inference for ordered HPC streams.

The reference file must contain only the 800 benign training traces. The
input stream is scored before each row is learned, so this mode is separate
from the batch artifact and should only be used when order is meaningful.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent / "src"))

from hpcbd.calibrate import calibrate
from hpcbd.detectors import RiverHalfSpaceTreesDetector
from hpcbd.io import DEFAULT_SCHEMA, load_csv
from hpcbd.preprocess import Preprocessor


def main() -> None:
    parser = argparse.ArgumentParser(description="Score an ordered HPC stream with River")
    parser.add_argument("--reference", required=True, help="Benign reference CSV")
    parser.add_argument("--input", required=True, help="Ordered stream CSV")
    parser.add_argument("--out", default="stream_predictions.csv")
    parser.add_argument("--alpha", type=float, default=0.05)
    args = parser.parse_args()

    reference = load_csv(args.reference, schema=DEFAULT_SCHEMA)
    stream = load_csv(args.input, schema=DEFAULT_SCHEMA)
    prep = Preprocessor()
    X_reference = prep.fit_transform(reference)
    X_stream = prep.transform(stream)

    calibration_model = RiverHalfSpaceTreesDetector()
    reference_scores = calibration_model.score_stream(X_reference)
    tau = calibrate(reference_scores, alpha=args.alpha)

    model = RiverHalfSpaceTreesDetector()
    model.fit(X_reference)
    scores = model.score_stream(X_stream)

    output = stream.copy()
    output["score"] = scores
    output["label"] = (scores > tau).astype(int)
    output["threshold"] = tau
    output.to_csv(args.out, index=False)
    print(f"[stream] {int(output['label'].sum())}/{len(output)} flagged; tau={tau:.6f}")
    print(f"[stream] Predictions saved to {args.out}")


if __name__ == "__main__":
    main()
