# TRD — Technical Requirements Document

**Project:** Detection of Backdoor Attacks using Hardware Performance Counters (HPCs)
**Phase:** Documentation & research only — no code, no training, no results exist yet
**Status:** Draft v0.1 · Owner: Research Architecture · Companion docs: PRD, SRS, SYSTEM_DESIGN, TECHNICAL_DESIGN, RESEARCH, EXPERIMENT_PLAN, IMPLEMENTATION_ROADMAP, RISK_ANALYSIS, FRONTEND_UI_UX_DESIGN

---

## 1. Purpose

Define the technical requirements and constraints for a one-class (benign-only) anomaly detector that labels HPC inference traces as *clean* or *backdoor*, and for the reproducible repository that delivers it. This document is the **canonical register** of shared identifiers (assumptions, hypotheses, open decisions) used by every other document.

## 2. Source facts (from the problem statement — treat as ground truth)

| ID | Fact |
|----|------|
| F1 | Training data = one `.csv` of HPC traces from **benign** inferences. |
| F2 | Column names = HPC names. |
| F3 | **800 rows**, one row per clean inference. |
| F4 | **No backdoor traces** are provided ("strict anomaly detection scenario"). |
| F5 | Evaluation is on a **private** validation set with clean **and** backdoor traces. |
| F6 | Metrics: Accuracy, TPR, FPR, F1, AUROC. |
| F7 | Deliverables: GitHub repo with complete code + finalized parameters, a saved detector model, README, short PDF report describing the method. |
| F8 | The trace folder is a Google Drive link; **its contents were not accessible during this documentation phase** (the link returned no file listing). The number of columns, value ranges and file name are therefore **unknown**. |

## 3. Assumptions register (A = assumed, not verified)

| ID | Assumption | Impact if false |
|----|-----------|-----------------|
| A1 | One row = one inference, aggregated HPC vector (not a time series per inference). | Need sequence features / different loader. |
| A2 | All columns numeric, no label column, few or no missing values. | Loader/imputation requirements change. |
| A3 | Training rows were collected in one environment (same CPU, model, software stack); row order may carry drift. | Drift handling becomes central. |
| A4 | Validation traces share column names, hardware and measurement protocol with training. | Cross-machine shift would break any threshold. |
| A5 | Validation contains both classes at an **unknown** ratio. | Accuracy/F1 depend on prevalence; threshold choice is risky. |
| A6 | Evaluation uses our saved model or our predictions in a format we must define/document. | Interface contract must be confirmed with organizers. |
| A7 | Backdoor-triggered inferences differ measurably from clean ones in ≥1 counter or in counter *relationships*. | Task is infeasible for any method; see R-01. |
| A8 | CPU-only, laptop-class compute is sufficient (n=800, d moderate). | Deep methods become costlier. |
| A9 | "Backdoor run" means inference on trigger-bearing inputs of a backdoored model (clean inputs on that model may or may not be included). | Defines what "anomalous" means; affects expected effect size. |

## 4. Hypotheses register (H = testable, currently unproven)

| ID | Hypothesis |
|----|-----------|
| H1 | Correlation-aware (multivariate) detectors beat per-feature detectors, because a backdoor may alter joint structure while leaving marginals near-normal. |
| H2 | Count-type HPC data is heavy-tailed; log/rank transforms improve detector stability. |
| H3 | A diverse ensemble is more robust than any single detector when the anomaly's shape is unknown. |
| H4 | Backdoor effects can be in **either direction** (higher or lower counts), so scoring must be two-sided. |
| H5 | A shrinkage-regularised Mahalanobis detector is a strong baseline at n=800. |
| H6 | Deep one-class models give no reliable gain at n=800 (general benchmark evidence exists; domain evidence does not). |
| H7 | Benign-only out-of-fold score quantiles give a usable FPR-controlled threshold if A3/A4 hold. |

## 5. Open decisions register (OD — deliberately not decided yet)

| ID | Decision | Decide after |
|----|----------|--------------|
| OD-1 | Final detector family / ensemble composition | Experiments E1–E7 |
| OD-2 | Target false-positive rate α for the operating threshold | E4 + organizer clarification on prevalence |
| OD-3 | Fusion rule for ensemble scores (mean / max / rank-mean) | E7 |
| OD-4 | Feature transform (log1p+robust vs quantile vs none) | E2 |
| OD-5 | Model serialization format (joblib+manifest vs ONNX vs parameter JSON) | Organizer interface confirmation (A6) |
| OD-6 | Whether self-generated backdoor traces may be used for **validation only** | Organizer rules clarification |
| OD-7 | Use row order / drift features | E6 |
| OD-8 | Dashboard frontend stack (see FRONTEND_UI_UX_DESIGN) | Roadmap Phase 5 |

## 6. Technical requirements

### 6.1 Functional-technical (TR-F)
| ID | Requirement | Traces to |
|----|-------------|-----------|
| TR-F1 | Train **only** on the provided benign CSV; no code path may require backdoor labels or samples. | F1, F4 |
| TR-F2 | Produce a continuous anomaly score per row (higher = more anomalous) **and** a binary label at a documented threshold. | F6 (AUROC needs scores; Acc/TPR/FPR/F1 need labels) |
| TR-F3 | Detect unseen backdoor traces: method must not encode assumptions about one specific attack beyond documented hypotheses. | F5 |
| TR-F4 | Persist the trained detector, preprocessing, feature list, threshold and metadata as one versioned artifact. | F7 |
| TR-F5 | Provide a CLI and Python API for `fit`, `score`, `predict`, `evaluate`. | F7 |
| TR-F6 | Validate input schema (column names/order/dtypes) and fail loudly with actionable errors on mismatch. | A4 |
| TR-F7 | Evaluation module computes Accuracy, TPR, FPR, F1, AUROC from labelled data when labels exist. | F6 |

### 6.2 Quality attributes (TR-Q)
| ID | Requirement |
|----|-------------|
| TR-Q1 | **Reproducibility:** fixed seeds, pinned dependencies, deterministic fit; two clean runs yield identical artifacts (or identical within a documented float tolerance). |
| TR-Q2 | **Small-data reliability:** every model choice must be justified for n=800; report variability over repeated resampling, not a single split. |
| TR-Q3 | **Honest reporting:** no metric is reported unless produced by a script in the repo; proxy/synthetic validations are labelled as proxies. |
| TR-Q4 | **Latency:** scoring one row on CPU < 50 ms (target; to be confirmed). Batch of 10⁴ rows < 30 s (target). |
| TR-Q5 | **Portability:** Linux/macOS/Windows, Python ≥ 3.10, CPU only. |
| TR-Q6 | **Safety of artifacts:** no unpickling of untrusted data; artifact carries a SHA-256 manifest. |
| TR-Q7 | **Explainability:** every flagged row can be accompanied by per-feature contribution / top-k deviating counters. |

### 6.3 Technology constraints (TR-T) — *candidates, not final*
- Language: Python ≥ 3.10.
- Core libs: NumPy, pandas, SciPy, scikit-learn (covers shrinkage covariance, MinCovDet, IsolationForest, LOF, OneClassSVM, GaussianMixture, PCA).
- Optional: PyOD (ECOD/COPOD/etc., verified existence in RESEARCH.md as [K]); PyTorch **only if** E-series evidence justifies a neural model (H6).
- Tooling: pytest, ruff, pre-commit, GitHub Actions CI, `uv` or `pip-tools` for pinned environments, DVC *not* required (single small CSV).
- No GPU, no network access at inference.

## 7. Data requirements
- Raw CSV is **not committed** if redistribution is restricted by organizers (OD to confirm); repo stores a SHA-256 of the expected file and a schema file.
- Data audit report (generated by code later) must capture: shape, dtypes, NaN/inf counts, constant columns, duplicate rows/columns, per-column skew/kurtosis, correlation structure, row-order autocorrelation.

## 8. Evaluation requirements
- Primary: AUROC (threshold-free). Secondary: TPR, FPR, Accuracy, F1 at the shipped threshold.
- Because no anomalies are available, the only **measurable** quantity on real data is the benign-side behaviour (out-of-fold FPR). Detection power must be described via clearly labelled synthetic stress tests (EXPERIMENT_PLAN E5). These are *sensitivity profiles*, not performance estimates.

## 9. Deliverable requirements
| Deliverable | Requirement |
|-------------|-------------|
| Repo | Layout per SYSTEM_DESIGN §9; CI green; `make reproduce` path documented. |
| Saved model | One artifact bundle + manifest; loadable with a single documented call. |
| README | Install, data placement, train, predict, evaluate, interface contract, limitations. |
| PDF report | Short (target ≤ 6 pages): method, rationale, validation protocol, honest limitations. Generated from the same Markdown sources where possible. |

## 10. Traceability matrix (excerpt)
| Source fact | TRD req | SRS req | Verified by |
|-------------|---------|---------|-------------|
| F1/F4 | TR-F1 | FR-01 | Unit test: fit() works with no labels; static check no label args |
| F6 | TR-F2, TR-F7 | FR-05, FR-07 | Metric unit tests vs sklearn |
| F7 | TR-F4, TR-F5 | FR-08, FR-09 | Fresh-clone smoke test in CI |
| A4 | TR-F6 | FR-02 | Schema-mismatch tests |

## 11. Document consistency rules
1. IDs (F, A, H, OD, TR, FR, NFR, R, E) are defined once (here, SRS, RISK, EXPERIMENT_PLAN) and only referenced elsewhere.
2. Facts are marked **F**, assumptions **A**, hypotheses **H**; nothing else is stated as fact.
3. No document may contain performance numbers for this task until they are produced by repo code.
