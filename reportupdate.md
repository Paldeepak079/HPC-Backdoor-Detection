# Current Development Status (as of 2026-11-15)

> This file supersedes the earlier status template. Bracketed placeholders are
> replaced with verified facts about the repository at
> `C:\Users\bhauk\Documents\hackathon\HPC Backdoor Detection`.
> No detection metrics are claimed or implied anywhere in this document; see §5.

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
The implementation went further; the as-built pipeline is:

- **Preprocessing:** log1p on raw counters, 3 ratio features
  (`llc_per_cache_ref`, `llc_per_cycle`, `cache_ref_per_cycle`), robust
  scaling — 6 features total. No PCA reduction of the input space (the
  original "10–15 components" item is not applicable to 3 counters).
- **Detectors (7, fused by mean):** Ledoit–Wolf Mahalanobis; PCA
  reconstruction error + Hotelling T²; Isolation Forest; kNN distance;
  BIC-selected GMM (up to 6 components); One-Class SVM; PyOD ECOD. Optional
  River Half-Space Trees wrapper exists but is disabled.
- **Validation protocol:** repeated 5-fold × 10-repeat CV, seeded (42), with
  per-fold preprocessing and out-of-fold (OOF) scoring.
- **Calibration:** per-detector ECDF normalisation against OOF benign scores,
  mean fusion, conformal threshold at α = 0.05 (≈95th percentile, matching
  the planned 95th–99th band). Saved threshold τ = 2.72978 in
  `artifact/manifest.json`.
- **No deep learning, no synthetic anomaly tuning** — as planned.

**Caveat:** the OOF averaging and PCA normalisation have verified defects
(`report.md` C1, C2) that currently invalidate the threshold transfer. The
methodology above describes design intent, not a validated result.

## 4. Code status — backend COMPLETE, delivery hardening NOT complete

| Component | Status |
|---|---|
| Data audit | Complete (`src/hpcbd/audit.py`, reports generated) |
| Preprocessing + detectors + ensemble | Complete |
| Training pipeline (`train.py`) | Complete and has been run |
| Inference (`predict.py`, `stream_predict.py`) | Complete; **no input validation** (report.md C3) |
| Evaluation (`evaluate.py`) | Complete; refuses metrics on single-class data |
| Explainability (`explain.py`), PDF report, dashboard export | Complete |
| Model artifact + SHA-256 manifest | Complete |
| Tests (`tests/`) | **Not started — directory is empty** |
| CI | **Not started — no workflow exists** |
| Frontend (`dashboard-ui/`) | Builds and typechecks; flagship canvas visualization **throws at runtime** (report.md Frontend C1); several design features unimplemented |
| License / root `.gitignore` packaging | **Missing** |

Known open defects: 3 critical backend, 12 major backend, 2 critical
frontend, 9 major frontend — full inventory with file:line references and
remediation plan in `report.md`.

## 5. Model status — trained and saved; NO performance metrics measured

- **Artifact exists:** `artifact/preprocessor.joblib`,
  `artifact/ensemble_detector.joblib`, `artifact/config.json`,
  `artifact/manifest.json` (hashes + schema + τ).
- **Benign-only outputs exist:** `predictions.csv` (800 rows: score, label,
  7 per-detector scores).
- **No labelled data has ever been available**, so **Accuracy, TPR, FPR, F1
  and AUROC have not been computed and are not claimed.**
  `reports/evaluation_benign_only.json` explicitly records
  `classification_metrics_available: false`.
- **Benign-side diagnostic (not a performance metric):** using the shipped
  artifact, 0 of 800 training rows exceed τ. Under the stated conformal
  design ≈5% should. This is evidence of the C1 calibration defect, not a
  detection result, and must be re-measured after the fix and retrain.
- All OOF statistics in `reports/experiment_results.json` are currently
  inflated ~10× by the same defect; do not cite them.

## 6. Known risks — updated with realized findings

1. **(Original) Triggers may not leave detectable HPC signatures** — still
   unknown; unmeasurable without labelled data.
2. **(Original) Background noise may dominate** — cannot be assessed yet.
3. **(Original) Small sample size (800) limits covariance estimation** —
   mitigated by Ledoit–Wolf shrinkage; residual risk remains.
4. **(Original) Threshold may not transfer to the private set** — **realized
   in a concrete form:** the shipped threshold does not even transfer to the
   training data (0/800 flagged) due to a verified averaging bug. This is a
   code defect, not a statistical limitation, and is fixable.
5. **(New) Batch-size dependence** — PCA scores depend on how many rows are
   scored together, so results vary with input file size.
6. **(New) Unvalidated inference input** — malformed CSVs are silently
   zero-filled or scored NaN and labelled Clean.
7. **(New) Demo risk** — the dashboard's main visualization crashes on first
   animation frame; the dashboard currently reads hand-copied data rather
   than generated artifacts.

## 7. Next step (in order)

1. Apply P0 fixes from `report.md` §7: OOF averaging
   (`experiments/run_experiments.py:121`), PCA fit-time normalisation, input
   validation, canvas colour fix.
2. Re-run `train.py` and confirm the benign-side flag rate is ~5% before
   trusting any artifact; regenerate `predictions.csv`, reports, and
   dashboard data.
3. Add the minimal test suite and CI (P2 in `report.md`), flipping the
   known-bug xfails into regression tests after the fixes.
4. Only after a labelled validation set is obtained: compute and report
   Accuracy / TPR / FPR / F1 / AUROC — and label them as measured.

**Rule retained:** no number is added to this document unless it was
genuinely computed; detection metrics require both classes.
