# HPC Backdoor Detection

Clean-only anomaly detection for hardware performance counter (HPC) traces.
The competition training file contains 800 benign traces:
`cache-references`, `cycles`, and `LLC-loads`.

## What is included

- Leakage-safe preprocessing with ratio features, `log1p`, and robust scaling.
- Batch ensemble of scikit-learn detectors plus PyOD ECOD.
- Optional River Half-Space Trees wrapper for ordered/prequential streams.
- Repeated fold-held-out calibration using only benign traces.
- SHA-256 verified saved model/preprocessing artifact.
- CSV inference and labelled evaluation scripts.
- `reports/methodology_report.pdf` describing the method and limitations.

The supplied data contains no attack labels. Consequently, the project does
not claim Accuracy, TPR, FPR, F1 or AUROC from the benign-only file. Those
metrics are computed only by `evaluate.py` when an independent labelled CSV
contains both classes.

## Setup

Use Python 3.13 (the current verified environment) or a compatible supported
Python version:

```powershell
python -m pip install -r requirements.txt
```

## Train and reproduce the artifact

Run from the repository root:

```powershell
python train.py --data "HPC traces/trace.csv" --out artifact/
```

Training always runs the configured repeated cross-validation before fitting
the final model. Every CV fold fits its own preprocessor and detectors on the
fold's benign training partition. The final model is then fitted on all 800
benign rows, while its score reference distribution and threshold come from
fold-held-out scores.

Generated files:

- `artifact/preprocessor.joblib`
- `artifact/ensemble_detector.joblib`
- `artifact/config.json`
- `artifact/manifest.json`
- `predictions.csv`
- `reports/data_audit.{json,md}`
- `reports/experiment_results.json`
- `reports/methodology_report.pdf`

## Score unseen traces

```powershell
python predict.py `
  --input "path\to\unseen.csv" `
  --artifact artifact\ `
  --out predictions.csv
```

The output preserves input columns and adds `score`, `label`, and each
per-detector score. `label=0` is Clean and `label=1` is Suspicious.

## Evaluate labelled data

The labelled file must contain the three feature columns and a binary
`label` column (`0=Clean`, `1=Suspicious`):

```powershell
python evaluate.py `
  --input "path\to\labelled.csv" `
  --artifact artifact\ `
  --out reports\evaluation.json
```

The JSON contains Accuracy, TPR, FPR, F1, AUROC, confusion counts, sample
count, positive count, and the saved threshold.

## River streaming mode

River is not mixed into the batch ensemble because it is valuable only when
trace order and incremental adaptation matter. Its
`RiverHalfSpaceTreesDetector.score_stream` method scores each row before
learning that row (prequential operation). It is available for a downstream
ordered-stream adapter:

```powershell
python stream_predict.py `
  --reference "HPC traces\trace.csv" `
  --input "path\to\ordered_stream.csv" `
  --out stream_predictions.csv
```

It is deliberately disabled in `configs/default.yaml` for the competition
batch submission.

## Model choices and calibration

The final batch ensemble uses:

1. Ledoit-Wolf Mahalanobis distance.
2. PCA reconstruction error plus Hotelling T².
3. Isolation Forest.
4. k-nearest-neighbour distance.
5. BIC-selected Gaussian mixture negative log likelihood.
6. One-Class SVM.
7. PyOD ECOD.

Each detector's score is mapped with the empirical CDF of its fold-held-out
benign scores, then scores are averaged. The threshold is the conformal
finite-sample upper quantile at `alpha=0.05`. This controls the benign
screening false-alarm budget; it is not an attack detection guarantee.

## Repository layout

```text
train.py                 Reproducible final training entry point
predict.py               Unseen-trace CSV inference
evaluate.py              Labelled metrics
make_report.py           Methodology PDF generation
experiments/             Leakage-safe CV benchmarking
src/hpcbd/               Preprocessing, detectors, calibration, artifacts
configs/default.yaml     Final parameters
HPC traces/trace.csv     800 benign training traces
```
