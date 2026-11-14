# Current Development Status (as of 2026-11-15)

> This file supersedes the earlier status template. It describes the verified
> working tree at `C:\Users\bhauk\Documents\hackathon\HPC Backdoor Detection`.
> No detection metrics are claimed or implied anywhere in this document; see §5.
> Remaining defects and file:line references are in `report.md`.

---

## 1. Dataset access — RESOLVED

- The dataset **is available locally** at `HPC traces/trace.csv` and has been
  inspected (see `reports/data_audit.{json,md}`). The earlier Google Drive
  link typo is moot: the file is in the repository.
- **Verified shape:** 800 rows × 3 columns — `cache-references`, `cycles`,
  `LLC-loads`.
- **Verified quality:** 0 duplicate rows, no constant columns, no missing
  values. `cache-references` and `LLC-loads` are strongly correlated
  (Pearson 0.9196); `cycles` is moderately correlated with both (~0.53).

## 2. Assumptions — verified / refuted

| Assumption from the earlier plan | Status |
|---|---|
| CSV contains 800 rows of benign HPC traces | **Verified** — 800 rows, audit clean |
| Columns are HPC counter names | **Verified** — exactly the 3 counters above |
| No backdoor samples or labels present | **Verified** — no `label` column; `reports/evaluation_benign_only.json` records `n_positive: 0` |

## 3. Methodology — implemented (differs from the research-phase sketch)

The research phase proposed *Mahalanobis (Ledoit–Wolf) + diagonal GMM only*.
The delivered pipeline is:

- **Preprocessing:** log1p on raw counters, 3 ratio features
  (`llc_per_cache_ref`, `llc_per_cycle`, `cache_ref_per_cycle`), robust
  scaling — 6 features total. No PCA reduction of the input space.
- **Detectors (2 enabled, fused by mean):** Ledoit–Wolf Mahalanobis and PCA
  reconstruction error + Hotelling T². Isolation Forest, kNN, BIC-GMM,
  One-Class SVM, and PyOD ECOD remain in the codebase but are disabled by
  default (`# DISABLED: P1-1` in `configs/default.yaml`). The River
  Half-Space Trees wrapper is also disabled.
- **Validation protocol:** repeated 5-fold × 10-repeat CV, seeded (42), with
  per-fold preprocessing and out-of-fold (OOF) scoring. Each row's repeated
  validation scores are averaged by its holdout count.
- **Calibration:** per-detector ECDF normalisation against OOF benign scores,
  mean fusion, conformal threshold at α = 0.05. Saved threshold
  τ = 2.9592651748109438 in `artifact/manifest.json`.
- **No deep learning, no synthetic anomaly tuning.**

**Verified implementation detail:** PCA normalization statistics are fit once
on training data and reused at inference, so a row's score is independent of
the scoring batch size (`tests/test_pca.py`).

## 4. Code status — backend COMPLETE; remaining work is hardening

| Component | Status |
|---|---|
| Data audit | Complete (`src/hpcbd/audit.py`, reports generated) |
| Preprocessing + detectors + ensemble | Complete; two detectors enabled by default |
| Training pipeline (`train.py`) | Complete; OOF-calibrated, benign flag-rate guard 3–8% |
| Inference (`predict.py`, `stream_predict.py`) | Complete; rejects empty, schema-mismatched, non-numeric, NaN, and infinite input with exit status 2 |
| Evaluation (`evaluate.py`, `hpcbd evaluate`) | Complete; refuses classification metrics on single-class data |
| Explainability (`explain.py`), PDF report, dashboard export | Complete; minor raw-value lookup bug open in `explain.py` |
| Model artifact + SHA-256 manifest | Complete |
| Tests (`tests/`) | 8 files; `python -m pytest tests -q` → **11 passed, 2 xfailed** |
| Lint | `python -m ruff check ...` → **All checks passed** |
| CI | GitHub Actions: Python 3.13 (pytest + ruff) and dashboard build on Node 22 |
| Frontend (`dashboard-ui/`) | `npm run build` succeeds; canvas pipeline, CSV validation, error UI, and mobile layout work; `run.json` export is not yet consumed |
| License / root `.gitignore` packaging | MIT license, `.gitignore`, and `ruff.toml` exist (tracking gaps in §7) |

The 2 expected failures intentionally document real defects: interpolated
(vs order-statistic) conformal quantile in `calibrate.py`, and tie-incorrect
AUROC in `metrics.py`. Other open items — streaming calibration, silent
in-sample fallback, inert config keys, export-contract drift, packaging — are
inventoried in `report.md` §4. **No critical defects remain known.**

## 5. Model status — trained and saved; NO performance metrics measured

- **Artifact exists:** `artifact/preprocessor.joblib`,
  `artifact/ensemble_detector.joblib`, `artifact/config.json`,
  `artifact/manifest.json` (hashes + schema + τ).
- **Benign-only outputs exist:** `predictions.csv` is 800 rows × 7 columns:
  the 3 raw counters, `score`, `label`, `score_mahalanobis`, `score_pca`.
- **No labelled data has ever been available**, so **Accuracy, TPR, FPR, F1
  and AUROC have not been computed and are not claimed.**
  `reports/evaluation_benign_only.json` records
  `classification_metrics_available: false` and `n_positive: 0`.
- **Benign-side calibration diagnostic (not a performance metric):**
  **32 of 800 rows exceed τ (4.0%)**, inside the configured 3–8% acceptance
  range around α = 0.05. Maximum fused score is 7.5721.
- **OOF statistics are per-sample repeated-CV means:** Mahalanobis mean
  1.0234 / max 13.8155; PCA mean 1.0255 / max 13.8155; fused mean 1.0119 /
  q95 2.9147. The prior ~10× repeat-sum inflation is gone.
- **Artifact, predictions, reports, and dashboard data** were regenerated in
  one batch (file mtimes 03:27–03:28 on 2026-11-15). Retraining requires the
  pinned Python 3.13 / scikit-learn 1.9 environment; this workspace's
  interpreter is Python 3.10 / scikit-learn 1.7.2, so the reproduction command
  was not re-executed here — the saved outputs above were verified directly.

## 6. Known risks — updated

1. **(Original) Triggers may not leave detectable HPC signatures** — still
   unknown; unmeasurable without labelled data.
2. **(Original) Background noise may dominate** — cannot be assessed yet.
3. **(Original) Small sample size (800) limits covariance estimation** —
   mitigated by Ledoit–Wolf shrinkage; residual risk remains.
4. **(Original) Threshold may not transfer to the private set** — still an
   inherent deployment risk; it needs a separately collected validation set.
5. **Input integrity:** malformed input is now rejected before scoring; any
   operational integration must preserve this validation path rather than
   bypassing it with raw `pd.read_csv`.
6. **Streaming mode:** `stream_predict.py` calibrates τ on a cold-start model
   instance different from the one used for scoring (open defect O4).
7. **Calibration references:** `EnsembleDetector.fit` silently falls back to
   in-sample scores if OOF references are missing (open defect O3).
8. **Dashboard contract:** `run.json` is exported but unused; the app still
   renders CSV + manifest, so the two artifacts can drift (open defect OF1).
9. **Repository state:** fixes are uncommitted; `HEAD` is older than this
   document, and 41 `.pyc` files remain tracked (see §7).

## 7. Repository hygiene snapshot

- Working tree vs `HEAD` (`70b0271`): **38 changed/untracked items**, including
  the latest `io.py`, `predict.py`, `stream_predict.py`, `train.py`,
  `configs/default.yaml`, `App.tsx`, `NeuralPipeline.tsx`, `Layout.tsx`,
  `Layout.module.css`, tests, CI, README, regenerated artifact/outputs, and
  both reports. **A fresh clone at `HEAD` does not reproduce this state.**
- Untracked deliverables: `LICENSE`, `ruff.toml`,
  `tests/test_inference_validation.py`, `dashboard-ui/public/data/run.json`,
  and the `files/` design-doc set.
- 41 tracked `.pyc` files under `__pycache__/` despite the root `.gitignore`.
- `.gitignore` excludes `predictions*.csv` and `artifact/*.joblib`, but those
  files are already tracked; the policy needs to be made consistent.

## 8. Next step (in order)

1. **Commit the verified working tree** and add the untracked license, lint
   config, validation test, dashboard export, and design docs; untrack
   `__pycache__` and reconcile the artifact/prediction ignore rules.
2. Re-run pytest, ruff, and the dashboard build from a clean clone to confirm
   CI matches the working tree.
3. Close the two documented `xfail` defects (tie-correct AUROC +
   `np.trapezoid`; order-statistic conformal quantile), then flip them to
   normal tests.
4. Fix the remaining hardening items in `report.md` §6 (stream calibration,
   silent fallback, `explain.py` indexing, inert config keys, packaging,
   `run.json` contract).
5. Only after a labelled validation set is obtained: compute and report
   Accuracy / TPR / FPR / F1 / AUROC — and label them as measured.

**Rule retained:** no number is added to this document unless it was
genuinely computed; detection metrics require both classes.
