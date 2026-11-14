# PRD — Product Requirements Document

**Product:** HPC Backdoor Sentinel (working name) — a benign-only anomaly detector for neural-backdoor inference traces, plus an optional companion dashboard.
**Status:** Draft v0.1 · IDs referenced (A, H, OD, F) are defined in TRD.md

---

## 1. Problem statement
A neural network supplied by an untrusted party may behave normally except on inputs containing a hidden trigger. The organizers provide HPC traces from **800 clean inferences only**. The product must label unseen traces as clean or backdoor, scored on a private set (Accuracy, TPR, FPR, F1, AUROC).

## 2. Users and stakeholders
| Persona | Need |
|---------|------|
| **Competition team** (primary) | A defensible, reproducible detector built under a strict one-class constraint; fast iteration; clear evidence of method soundness. |
| **Judges / organizers** | Clone-and-run repo, saved model that loads, predictable I/O, honest report. |
| **Security researchers / reviewers** | Transparent assumptions, ablations, limitations, citation integrity. |
| **Demo audience** (secondary) | Understand what the detector sees and why a trace is flagged — via the dashboard. |

## 3. Goals
| ID | Goal | Success measure |
|----|------|-----------------|
| G1 | Maximize detection of unseen backdoor traces under one-class training | AUROC / TPR on private set (**no numeric target promised**; see §7) |
| G2 | Keep false alarms controlled and predictable | Out-of-fold FPR within tolerance of chosen α (EXPERIMENT_PLAN E4) |
| G3 | Fully reproducible delivery | Fresh clone → train → identical artifact; CI passes |
| G4 | Honest, auditable method | Every number in report traceable to a repo script; proxies labelled |
| G5 | Explainable alerts | Top-k deviating counters per flagged row |
| G6 | Clear, premium demo | Dashboard (optional) renders real artifacts only |

## 4. Non-goals
- Training on, simulating or fabricating backdoor traces as evidence of performance.
- Classifying *which* attack or trigger is present.
- Defending against adaptive attackers who optimise against this detector (documented as limitation).
- Real-time on-device deployment, GPU optimization, or collecting HPCs ourselves (unless OD-6 allows and time permits).

## 5. Scope
**MUST (MVP):** data audit; preprocessing; ≥3 baseline detectors; model selection protocol; threshold calibration; saved artifact; CLI predict/evaluate; README; PDF report; tests; CI.
**SHOULD:** ensemble with fusion; per-feature explanations; stress-test suite; model card.
**COULD:** companion dashboard (static, offline, reads result artifacts); ONNX/parameter-JSON export; drift monitor.
**WON'T (this phase):** any implementation.

## 6. User stories
| ID | Story | Acceptance |
|----|-------|-----------|
| US-1 | As a judge, I run one command to score a CSV and get labels + scores. | CLI documented; output columns fixed (SRS §6). |
| US-2 | As a team member, I compare detectors under identical resampling. | One config → comparable table with variability. |
| US-3 | As a reviewer, I see which assumptions the method relies on. | README + report "Assumptions & Limitations" section maps to A-IDs. |
| US-4 | As an analyst, I see why a trace was flagged. | Top-k counters with direction (high/low) and magnitude. |
| US-5 | As a presenter, I watch a trace flow through the pipeline and be classified. | Dashboard neural visualization driven by real scoring output. |

## 7. Success criteria and honesty policy
- **Deliverable success** (measurable now): repo completeness, reproducibility, CI, documented interface, report.
- **Detection success** (measurable only on the organizers' private set): AUROC, TPR, FPR, Accuracy, F1.
- We do **not** commit to numeric detection targets before a data audit; any target will be set after E0 and labelled as aspirational.
- Reports must separate: **measured** (benign-side, real) / **simulated** (stress tests) / **hypothesised**.

## 8. Dependencies
- Access to the organizers' CSV (not verified accessible during this phase — F8).
- Clarifications from organizers: interface contract (A6), prevalence (A5), self-generated validation data policy (OD-6), submission deadline (unknown).

## 9. Release plan (maps to IMPLEMENTATION_ROADMAP)
| Release | Content |
|---------|---------|
| R0 | Data audit + baseline harness |
| R1 | Calibrated single best detector, artifact, CLI |
| R2 | Ensemble + explanations + stress tests |
| R3 | Final repo, README, PDF report |
| R3+ | Optional dashboard |

## 10. Key product risks (see RISK_ANALYSIS)
Infeasibility if counters carry no signal (R-01); threshold miscalibration under unknown prevalence (R-03); validation shift from training (R-04); proxy overfitting (R-06).
