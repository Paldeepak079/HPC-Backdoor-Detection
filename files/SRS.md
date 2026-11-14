# SRS — Software Requirements Specification

Structure follows the general shape of ISO/IEC/IEEE 29148 (requirements engineering). IDs F/A/H/OD are defined in TRD.md.

---

## 1. Introduction
### 1.1 Purpose
Specify behaviour, interfaces and constraints of the **HPC Backdoor Detector** software (library + CLI), and of the optional read-only dashboard.
### 1.2 Scope
Software that fits an unsupervised detector on benign HPC rows, scores/labels new rows, evaluates labelled data, and exports an artifact. It does not collect HPCs and does not train on backdoor data.
### 1.3 Definitions
HPC: hardware performance counter. Trace row: one inference's counter vector (A1). Score: real number, larger = more anomalous. Label: 1 = backdoor/anomalous, 0 = clean. α: target benign false-positive rate.

## 2. Overall description
### 2.1 Product perspective
Standalone Python package `hpcbd` (name provisional). Optional dashboard consumes JSON/CSV outputs; it never alters scoring.
### 2.2 User classes
Team developer; judge/evaluator; dashboard viewer.
### 2.3 Operating environment
Python ≥ 3.10, CPU, Linux/macOS/Windows.
### 2.4 Constraints
C1 one-class training only · C2 n=800 benign rows · C3 private validation set · C4 deliverables per F7 · C5 deterministic builds.
### 2.5 Assumptions/dependencies
A1–A9 (TRD §3).

## 3. Functional requirements
| ID | Requirement | Priority |
|----|-------------|----------|
| FR-01 | `fit` shall accept an unlabeled benign CSV and shall expose no parameter that requires anomaly labels. | MUST |
| FR-02 | The loader shall validate: file exists; numeric columns; no all-NaN columns; column set equals the training schema at inference (order-insensitive, name-based). On mismatch it shall raise a typed error listing missing/extra columns. | MUST |
| FR-03 | Data audit shall emit a machine-readable report (JSON) and a human-readable Markdown summary. | MUST |
| FR-04 | Preprocessing shall be fitted on training data only and serialized with the model (no refitting at inference). | MUST |
| FR-05 | `score` shall return one anomaly score per row; `predict` shall additionally return a binary label using the stored threshold, overridable by `--threshold` or `--alpha`. | MUST |
| FR-06 | Threshold calibration shall use benign out-of-fold scores and a documented quantile rule (TECHNICAL_DESIGN §8). | MUST |
| FR-07 | `evaluate` shall compute Accuracy, TPR, FPR, F1, AUROC when a label column is supplied; AUROC from scores, others at the active threshold. | MUST |
| FR-08 | `save`/`load` shall round-trip the detector and produce a manifest (library versions, seed, config hash, data hash, feature list, threshold, α, creation time). | MUST |
| FR-09 | CLI shall provide: `audit`, `fit`, `score`, `predict`, `evaluate`, `explain`, `export`. | MUST |
| FR-10 | `explain` shall return top-k contributing features with signed deviation (robust z or Mahalanobis contribution). | SHOULD |
| FR-11 | Experiment runner shall execute all baselines under identical resampling and write a comparable results table + raw OOF scores. | MUST |
| FR-12 | Stress-test module shall generate synthetic perturbations of benign rows and flag every output as `synthetic_proxy=true`. | SHOULD |
| FR-13 | Ensemble module shall support score normalisation and fusion rules from a config file. | SHOULD |
| FR-14 | Exporter shall write dashboard JSON (scores, labels, explanations, run metadata) matching the schema in §6.3. | COULD |
| FR-15 | Reproduction command shall regenerate all report figures/tables from raw inputs. | MUST |

## 4. Non-functional requirements
| ID | Requirement | Verification |
|----|-------------|--------------|
| NFR-01 | Determinism: same seed + inputs ⇒ same artifact hash (or within documented tolerance). | CI double-run test |
| NFR-02 | Performance: single-row scoring < 50 ms; 10⁴ rows < 30 s on a laptop CPU (targets). | Benchmark script |
| NFR-03 | Test coverage ≥ 80% on core modules; property tests for metrics and thresholding. | pytest-cov |
| NFR-04 | Style/static: ruff + type hints on public API; mypy optional. | CI |
| NFR-05 | Security: artifact loading restricted to repo-produced files; manifest hash verified; no `eval`/unpickle of user-supplied files. | Code review |
| NFR-06 | Usability: all CLI errors actionable; `--help` complete. | Manual + tests |
| NFR-07 | Documentation: README quick-start works from a fresh clone in ≤ 5 commands. | CI smoke test |
| NFR-08 | Licensing: all dependencies permissive/compatible; repo license declared. | License check |
| NFR-09 | Dashboard accessibility: WCAG 2.2 AA targets (FRONTEND doc). | axe + manual |

## 5. System features by use case
1. **Audit** → reads CSV → writes audit report.
2. **Select** → runs experiment grid → writes comparison table → human selects configuration (OD-1..4).
3. **Fit & freeze** → fits final config on all 800 rows, calibrates threshold, writes artifact.
4. **Predict** → loads artifact, scores new CSV, writes predictions.
5. **Evaluate** → if labels exist, computes metrics.
6. **Explain/Visualize** → exports JSON for dashboard.

## 6. External interface requirements
### 6.1 Input CSV
Header row of HPC names; one numeric row per inference; optional `label` column (0 clean / 1 backdoor) used **only** by `evaluate`.
### 6.2 Output predictions CSV (provisional; confirm with organizers — A6)
| Column | Type | Meaning |
|--------|------|---------|
| `row_id` | int | Input row index |
| `score` | float | Anomaly score (higher = more anomalous) |
| `label` | int | 1 = backdoor/anomalous, 0 = clean |
| `threshold` | float | Threshold used |
### 6.3 Dashboard JSON (provisional)
`run.json` {meta, schema_hash, threshold, alpha}, `rows[]` {row_id, score, label, top_features[{name, z, direction}], stage_scores{detector→score}}, `calibration` {oof_score_quantiles, oof_fpr_at_alpha}. Fields absent ⇒ UI shows "no data", never placeholders presented as results.
### 6.4 Software interfaces
Python API: `Detector.fit(X)`, `.score(X)`, `.predict(X)`, `.explain(X, k)`, `.save(path)`, `Detector.load(path)`.

## 7. Data requirements
Schema file `schema.json` (column names, dtypes, training min/max/quantiles) generated by `audit`; data hash recorded; no raw data in repo unless permitted.

## 8. Error handling
Typed exceptions: `SchemaMismatchError`, `NonFiniteValueError`, `ArtifactIntegrityError`, `CalibrationError` (e.g., α too small for n). Non-finite values: reject by default; optional documented imputation flag (not default).

## 9. Acceptance criteria (release gate)
- [ ] Fresh clone → `make reproduce` completes
- [ ] Artifact loads and predicts on a held-out benign split
- [ ] Out-of-fold FPR within tolerance of α (EXPERIMENT_PLAN E4)
- [ ] All reported numbers regenerate from scripts
- [ ] README + PDF present; limitations section maps to A/R IDs
