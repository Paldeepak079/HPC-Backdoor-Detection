# HPC Backdoor Detection — Re-audit & Issue Report

**Scope:** `C:\Users\bhauk\Documents\hackathon\HPC Backdoor Detection`
**Re-audit date:** 2026-11-15
**Basis:** Full re-read of the current working tree plus read-only execution of the test suite, linter, dashboard build, and checks against the regenerated artifacts. This report supersedes the earlier audit and the appended fix-status blocks; every claim below reflects the current files, not the pre-fix state.

> **Fresh-clone caveat:** many fixes are uncommitted. The working tree (38 changed/untracked items, listed in §6) is newer than `HEAD` (`70b0271`). A fresh clone at `HEAD` does not contain the latest `io.py`/`predict.py`/`App.tsx` fixes, `LICENSE`, `ruff.toml`, `tests/test_inference_validation.py`, or the `run.json` export. See §6.

---

## 1. Re-audit summary

The previously critical defects are fixed and independently verified:

- **0 open critical defects.** C1 (OOF repeat summing), C2 (PCA batch-dependent normalisation), C3 (unvalidated inference input), Frontend C1 (canvas crash), and Frontend C2 / MF2 (NaN upload results under a "MEASURED" badge) all hold up under the current code.
- **Verification passed:** `python -m pytest tests -q` → `11 passed, 2 xfailed`; `python -m ruff check src experiments tests train.py predict.py stream_predict.py export_dashboard.py` → `All checks passed!`; `npm run build` in `dashboard-ui/` → built successfully (rolldown reports only third-party `"use client"` directive warnings from `framer-motion`).
- **The model now calibrates and flags as designed:** `artifact/manifest.json` τ = **2.9592651748109438** at α = 0.05; `predictions.csv` is **800 rows × 7 columns, 32 flagged (4.0%), max score 7.5721**; only the two intended detectors are enabled.
- **OOF statistics are sane:** Mahalanobis `oof_mean` 1.0234, max 13.8155; PCA `oof_mean` 1.0255, max 13.8155; fused mean 1.0119, q95 2.9147. The ~10× inflation is gone.
- **Remaining known defects are non-blocking:** two statistical/metrics edge defects are documented as `xfail` regression tests; the open list in §4 is minor-level (streaming calibration, silent fallback, inert config keys, export-contract drift, packaging) plus repository hygiene in §6.

**Environment note:** this workspace interprets `python` as 3.10 with scikit-learn 1.7.2, while the pinned/committed artifact uses Python 3.13 and scikit-learn 1.9. The test suite, lint, and build pass here; the full `train.py` reproduction was performed in the pinned environment (per the fix log), and the saved outputs listed above were verified directly. Do not treat this shell as the authority for retraining.

---

## 2. Fix status — previously reported defects

| ID | Was | Status | Evidence |
|----|-----|--------|----------|
| C1 | OOF scores summed over 10 CV repeats, inflating calibration ~10× | **FIXED** | `experiments/run_experiments.py:154` now divides by the per-row holdout count only (`safe_counts = np.maximum(fold_counts, 1)`), with a fold-coverage assertion. `reports/experiment_results.json` means ≈1.02, maxima 13.8155. |
| C2 | PCA normalised against the scoring batch (batch-dependent scores; 0 for single rows) | **FIXED** | `src/hpcbd/detectors/pca.py` stores `_recon_mean/_recon_std/_t2_mean/_t2_std` at `fit()` and reuses them in `score()`. `tests/test_pca.py` covers row/batch invariance. |
| C3 | Inference accepted malformed CSVs and labelled NaN rows Clean | **FIXED** | `src/hpcbd/io.py` validates schema, numeric parsing, finiteness, and non-empty input; `predict.py`, `cli.py`, and `stream_predict.py` exit 2 with a stderr message on bad input; `tests/test_inference_validation.py` (untracked) covers the paths. |
| Frontend C1 | `rgba`→`rgbaa` canvas colour crash killed the animation loop | **FIXED** | `dashboard-ui/src/components/NeuralPipeline.tsx:70-73` adds a `withAlpha()` helper used for node colours; the canvas renders detector/fusion/verdict nodes and gauge. |
| Frontend C2 / MF2 | Uploaded CSV produced NaN KPIs while labelled "MEASURED" | **FIXED** | `App.tsx` `buildRunData` validates empty input, duplicate/missing columns, non-numeric and non-finite values, and shows a `role="alert"` rejection banner; fetch failures surface as error UI instead of an endless spinner. |
| M1 | Fusion rule ignored during calibration; `rank_mean` batch-dependent | **FIXED** | `fusion_rule` is threaded through experiments and `train.py`; `rank_references` ranks against OOF references, not the served batch. |
| M2 | `hpcbd fit` used an in-sample, 6-detector path | **FIXED** | `cli.py cmd_fit` delegates to `train.py`, so both entry points share OOF calibration and detector config. |
| M3 | CLI `evaluate` fabricated AUROC = 0.5 on single-class data | **FIXED** | `metrics.py` raises `ValueError("AUROC requires both benign and anomalous labels.")`; `cli.py cmd_evaluate` requires a binary `label` column. |
| M5 | kNN discarded the true nearest neighbour at inference | **FIXED** | `knn.py` drops the self-distance only for the exact fitted training matrix (identity check), keeping the true 1st neighbour for new data. |
| M6 | Exporter wrote bare `NaN` JSON | **FIXED** | `export_dashboard.py` converts non-finite floats to `null` and rejects missing `score`/`label` columns. |
| M7 | Quickstart failed on missing `matplotlib`; report step undocumented | **FIXED** | `requirements.txt` includes `matplotlib`, `pytest`, `ruff`; README documents the explicit `make_report.py` step and the test command. |
| MF3 | Current-run scores presented as benign OOF reference | **FIXED** | The evidence eyebrow switches between "BENIGN OOF REFERENCE DISTRIBUTION" and "CURRENT-RUN SCORES - NOT BENIGN REFERENCE"; the current flag rate is no longer labelled benign OOF FPR. |
| MF4 | Mobile CSS targeted unsupervised global classes | **FIXED** | `Layout.module.css:188-195` now hides the sidebar and adjusts main content under `@media (max-width: 680px)`; the bottom `.mobile-nav` rule lives in `app.css`. |
| MF5 | Detector nodes saturated; gauge marker used raw τ against normalised score | **FIXED** | Node scores and the gauge threshold both pass through `scoreToRank`; the seven-node visual pipeline remains connected to fusion. |
| MF6 | Dead template/scaffolding files | **FIXED** | `counter.ts`, `style.css`, template assets, `hooks/useRunData.ts`, `data/sampleRun.ts`, `TraceDetailDrawer.module.css`, and empty `src/pages/` were removed. |
| P1-1 | Seven detectors diluted the weak benign signal | **CHANGED (intentional)** | Default config, artifact, dashboard data, and `train.py` final fit now enable only **Ledoit–Wolf Mahalanobis + PCA**; the other five remain available behind `enabled: false` (`# DISABLED: P1-1` in `configs/default.yaml`). |
| P1-2 | No guard on benign false-alarm rate | **ADDED** | `train.py` rejects artifacts whose benign OOF flag rate falls outside 3–8%; measured 32/800 = 4.0%. |
| P1-3 | Derived outputs could drift from the artifact | **ADDRESSED** | `artifact/*`, `predictions.csv`, `reports/*`, and `dashboard-ui/public/data/*` share the same regeneration batch (mtimes 03:27–03:28); README documents the export step. |
| P2 | Empty `tests/`, no CI, no license/ignore rules | **MOSTLY FIXED** | 8 test files (11 passed, 2 xfailed); `.github/workflows/ci.yml` runs pytest + ruff on Python 3.13 and `npm ci && npm run build` on Node 22; `LICENSE` (MIT), `.gitignore`, and `ruff.toml` exist (but see §6 for tracking gaps). |

---

## 3. Verification evidence (this re-audit)

| Check | Command / source | Result |
|-------|------------------|--------|
| Test suite | `python -m pytest tests -q` (workdir = repo root) | `11 passed, 2 xfailed in ~3.6 s` |
| Lint | `python -m ruff check src experiments tests train.py predict.py stream_predict.py export_dashboard.py` | `All checks passed!` |
| Dashboard build | `npm run build` in `dashboard-ui/` | Built successfully; only `framer-motion` module-directive warnings |
| Artifact threshold | `artifact/manifest.json` | τ = 2.9592651748109438, α = 0.05, schema = 3 counters |
| Predictions | `predictions.csv` | 800 × 7; 32 flagged (4.0%); max 7.5721 |
| OOF calibration | `reports/experiment_results.json` | Mahalanobis mean 1.0234 / max 13.8155; PCA mean 1.0255 / max 13.8155; fused q95 2.9147 |
| Detector default | `configs/default.yaml`, `artifact/config.json` | Only `mahalanobis` and `pca` enabled; `fusion_rule: mean` |
| Evaluation honesty | `reports/evaluation_benign_only.json` | `classification_metrics_available: false`, `n_positive: 0` |
| Tracked junk | `git ls-files` | **41 tracked `.pyc` files** despite `.gitignore` |

The 2 expected failures are deliberate and still document real defects:

1. `tests/test_calibrate.py::test_conformal_threshold_limits_strict_exceedances` — `calibrate.py` uses a linearly interpolated quantile rather than the order statistic (`method="higher"`), so the finite-sample guarantee is approximate.
2. `tests/test_metrics.py::test_auroc_matches_sklearn_when_scores_tie` — `metrics.py` breaks probability ties by unstable `argsort` ordering.

---

## 4. Remaining open issues

### Backend (minor to moderate)

| ID | Issue | Where |
|----|-------|-------|
| O1 | **AUROC tie handling still wrong; `np.trapz` still used.** Ties are ordered by an unstable `argsort`; `np.trapz` is deprecated in NumPy 2.0 and removed in 2.4, so a future pin bump crashes `evaluate.py`. | `src/hpcbd/metrics.py:74-75,96` |
| O2 | **Conformal threshold uses interpolation, not the order statistic.** The `xfail` test documents it; the empirical flag budget is therefore approximate rather than the advertised finite-sample guarantee. | `src/hpcbd/calibrate.py` (~44-45) |
| O3 | **Silent in-sample fallback in `EnsembleDetector.fit`.** If `oof_scores` is `None` or missing a detector key, the reference quietly becomes in-sample training scores. No warning is emitted, so a config/detector drift can contaminate calibration without failing. | `src/hpcbd/ensemble.py` (~126-130) |
| O4 | **Streaming calibration mismatch.** `stream_predict.py` computes τ from a fresh, untrained River model's prequential scores, then fits a second model and scores with it. It also writes `--out` without creating parent directories. | `stream_predict.py:38-44,60` |
| O5 | **`explain.py` indexes the raw row with a transformed-feature index.** With six features against three raw columns, ratio features receive wrong/`None` raw values and column-order changes return misleading explanations. | `src/hpcbd/explain.py` (~86) |
| O6 | **GMM swallows all fit exceptions (`except Exception: break`).** Can leave `best_model` unset; low impact while the detector is disabled by default. | `src/hpcbd/detectors/gmm.py` (~59-60) |
| O7 | **Dead flag and output-path inconsistency.** `--run-experiments` is declared with `store_true` + `default=True` and never read; `train.py` writes `predictions.csv` to the CWD regardless of `--out`. | `train.py:47-48`, predictions write |
| O8 | **Config keys remain inert.** `preprocess.transform`/`scaler` are stored but never used (always log1p + robust); `detectors.mahalanobis.shrinkage` is never passed; `streaming.*` is read by no code, although README says streaming is "deliberately disabled" there. | `configs/default.yaml`, `preprocess.py:36-37`, `mahalanobis.py` |
| O9 | **No packaging.** No `pyproject.toml`/`setup.py`; every script re-implements `sys.path.insert`; `hpcbd` CLI is undocumented and `python src/hpcbd/cli.py` still depends on CWD/PYTHONPATH. `predict.py`, `evaluate.py`, and `cli.py` duplicate logic. | repo root |

### Frontend (minor)

| ID | Issue | Where |
|----|-------|-------|
| OF1 | **`run.json` is now exported but still unused and schema-incompatible.** `export_dashboard.py` writes `dashboard-ui/public/data/run.json` (meta `generated_at`, top-level `threshold`/`alpha`, `calibration.*`), while the app continues to build `RunData` from `predictions.csv` + `manifest.json`; nothing fetches `run.json`. The exporter's comment also still calls the current prediction scores "training scores as reference". | `export_dashboard.py` (~110, 127-146), `dashboard-ui/src/App.tsx` |
| OF2 | **Detector columns are hardcoded to seven names.** Required columns are the two enabled detectors, and `stage_scores` filters to columns that exist, so this works — but adding/removing a detector requires editing `DETECTOR_COLUMNS`; the pipeline still renders five grey/disabled nodes. | `App.tsx:25-34` |
| OF3 | **Google Fonts network `@import` remains**, violating the offline/static-build design goal and delaying first paint. | `dashboard-ui/src/styles/globals.css:1` |
| OF4 | **TypeScript strictness/lint gaps.** `tsconfig.json` enables `noUnusedLocals`/`noUnusedParameters` but not `strict`; there is no ESLint/Prettier or Vitest coverage; several previously noted a11y/empty-state edges (table empty state, canvas text alternative) remain. | `dashboard-ui/tsconfig.json` |

### Documentation drift

| ID | Claim | Reality |
|----|-------|---------|
| D1 | "Batch ensemble of scikit-learn detectors plus PyOD ECOD" (`README.md:10`) | ECOD is implemented but disabled by default; README §"Model choices" says so, the intro does not. |
| D2 | Repository layout block (`README.md:131-142`) | Omits `stream_predict.py`, `export_dashboard.py`, `tests/`, `.github/`, `LICENSE`, `report.md`, `reportupdate.md`, `reports/`. |
| D3 | Streaming "deliberately disabled in `configs/default.yaml`" (`README.md:112-113`) | The keys are inert; exclusion is by `train.py` construction, and the streaming calibration defect (O4) is not disclosed. |
| D4 | Dashboard "renders only `run.json`" (design doc) | The app still renders CSV + manifest; `run.json` is an unused export (OF1). |
| D5 | SRS NFR-03 test coverage ≥80%, NFR-04 ruff/mypy, CI double-run hash comparison | Coverage measurement, mypy, and the CI double-run are not implemented; ruff runs with a narrow rule set. |

---

## 5. Repository hygiene

1. **All recent fixes are uncommitted.** `git status` shows 38 changed/untracked items against `HEAD` (`70b0271`), including `io.py`, `predict.py`, `stream_predict.py`, `train.py`, `configs/default.yaml`, `App.tsx`, `NeuralPipeline.tsx`, `Layout.tsx`, `Layout.module.css`, tests, CI, README, the regenerated artifact/outputs, and `report.md`/`reportupdate.md`. A fresh clone at `HEAD` is materially older than this report.
2. **Untracked deliverables:** `LICENSE`, `ruff.toml`, `tests/test_inference_validation.py`, `dashboard-ui/public/data/run.json`, and the entire `files/` design-doc set. CI on a clean clone therefore runs without `ruff.toml` (default rule set, not the intended one) and without the new validation tests, and lacks a license.
3. **41 tracked `.pyc` files** under `__pycache__/` (multiple Python versions), despite the new root `.gitignore`. They show as modified on every run and will keep generating noise.
4. **Ignore/track contradictions:** `.gitignore` excludes `predictions*.csv` and `artifact/*.joblib`, yet `predictions.csv` and both joblib artifacts are tracked, so the rules have no effect for them. Decide: keep artifacts tracked (reasonable for judging) and stop ignoring them, or untrack and document regeneration.
5. **Design docs still untracked** (`files/`). One accidental delete loses the PRD/SRS/TRD set.
6. **No `pyproject.toml`**, no `Makefile`, no model card, no `CONTRIBUTING`.

---

## 6. Prioritized next steps

### P1 — Freeze the verified state

1. Commit the working tree (code, tests, CI, regenerated outputs, both reports) and add the untracked `LICENSE`, `ruff.toml`, `tests/test_inference_validation.py`, `run.json`, and `files/`.
2. Untrack all `.pyc` files (`git rm -r --cached __pycache__ src/**/__pycache__ experiments/__pycache__`) so `.gitignore` takes effect; align `predictions*.csv` / `artifact/*.joblib` rules with the tracked-artifact policy.
3. Re-run `pytest`, `ruff check`, and `npm run build` once from a clean clone to confirm the committed CI matches the working tree.

### P2 — Close remaining correctness edges (small, well-scoped)

4. Replace `np.trapz` with `np.trapezoid` and make AUROC tie-correct (average ranks) — then flip the `xfail` to a normal test (`metrics.py`).
5. Use the conformal order statistic (`method="higher"`) in `calibrate.py` — flip the other `xfail`.
6. Warn or raise in `EnsembleDetector.fit` when OOF references are missing instead of silently using in-sample scores.
7. Fix `stream_predict.py` to calibrate τ from the same model instance used for scoring (or from saved benign reference scores) and create `--out` parent directories.
8. Fix `explain.py` raw-value lookup for ratio features; harden `gmm.py` fit failure; remove the dead `--run-experiments` flag; write predictions under `--out`.
9. Make config honest: honor `preprocess.transform`/`scaler` and `mahalanobis.shrinkage`, or delete the keys; point README at the actual streaming behavior.

### P3 — Frontend and docs polish

10. Decide the dashboard contract: either wire `run.json` into the app (schema-validate with a visible error list) or delete the export and fix the exporter comment; keep the CSV+manifest path as the single source if that is simpler.
11. Self-host the Inter/JetBrains Mono fonts (remove the Google Fonts `@import`); enable `strict` in `tsconfig.json`; add an ESLint + Vitest baseline.
12. Update README layout/inclusion text (ECOD disabled by default, streaming script, tests, CI, reports, license) and document the `run.json` status.

### P4 — Evaluation (unchanged honesty rule)

13. Only when an independent labelled validation set exists: compute Accuracy / TPR / FPR / F1 / AUROC and label every number as measured. Until then, retain `classification_metrics_available: false`; benign-only flag rates are calibration diagnostics, not performance metrics.

---

## 7. What is working well

- **Honesty policy** — benign-only data is never used to claim detection metrics; `evaluate.py`, `metrics.py`, and `reports/evaluation_benign_only.json` now enforce this consistently.
- **Leakage-aware design** — repeated 5-fold × 10-repeat CV, per-fold preprocessing, redundant-coverage assertion, and rank-based calibration against OOF benign scores.
- **Artifact integrity** — SHA-256 manifest, persisted feature schema, and a verified tau save/load round-trip.
- **Regression posture** — the known calibration/tie defects are captured as explicit `xfail` tests rather than hidden, and the suite is wired into CI.
- **Demo readiness** — the dashboard builds, the canvas pipeline renders, evidence labels are honest, uploads fail loudly, and mobile layout rules work.

---

## Fix log (retained, current state)

- 2026-11-15 — OOF averaging fix (`experiments/run_experiments.py`), PCA fit-time normalisation, and kNN self-neighbour handling committed; verified OOF means ≈1 with maxima at the ECDF ceiling 13.8155.
- 2026-11-15 — Second batch: `io.py` schema/finite validation, `predict.py`/`stream_predict.py` strict inference, `hpcbd fit` delegation, single-class metric guard, fusion-rule threading, NaN-safe dashboard export, requirements/README, frontend canvas colour helper, mobile CSS modules, evidence labels, dead-file cleanup, test suite, CI, `.gitignore`, and `LICENSE` added.
- 2026-11-15 — Methodology change: default artifact reduced to Mahalanobis + PCA (`configs/default.yaml`), benign flag-rate acceptance guard (3–8%) added to `train.py`, and all derived outputs regenerated from the same run: τ = 2.95927, 32/800 flagged (4.0%), predictions 800×7, dashboard data refreshed, ruff/pytest/npm build all green.

*End of report. Statuses reflect the working tree at re-audit time; §6 records what must be committed before a fresh clone reproduces it.*
