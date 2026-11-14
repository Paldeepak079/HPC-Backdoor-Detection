# TECHNICAL_DESIGN — Anomaly Detection, Features, Preprocessing, Model Selection, Threshold Calibration

Everything here is a **design proposal to be tested**; no result is claimed. Evidence status tags: **[V]** literature verified in this session, **[K]** from background knowledge — verify before citing (see RESEARCH.md).

---

## 1. Problem formalisation
Given benign vectors x₁…x₈₀₀ ∈ ℝᵈ (d unknown, F8), learn s: ℝᵈ → ℝ such that backdoor vectors receive larger s than benign ones, then choose τ for labels. Formally one-class / novelty detection with **no access to the anomaly distribution** and **unknown prevalence**.

Consequences:
- Model selection cannot use anomaly-labelled performance on real data.
- AUROC depends only on score ranking; Accuracy/TPR/FPR/F1 additionally depend on τ.
- Only benign-side behaviour (FPR) is measurable on real data.

## 2. Data characteristics to expect (hypotheses H2, H4)
- Counter values are non-negative counts with large dynamic ranges, heavy right tails, and frequent strong correlations between related events (e.g., instructions/cycles, cache references/misses) — [K] general HPC knowledge; to be confirmed by E0.
- Run-to-run non-determinism and overcount in HPC measurements exist [K: Weaver et al., ISPASS 2013], so benign spread is non-trivial.
- A backdoor effect could be (a) a shift in some counters, (b) a change in dispersion, (c) a change in **relationships** between counters, or (d) negligible. A detector family covering (a)–(c) is preferred (H1, H3, H4). Case (d) is a hard limit (R-01); a related stealthy-trojan paper reports near-chance detection by coarse runtime counters for its own attack, **[V]** (see RESEARCH §4.3) — a reason to avoid over-claiming.

## 3. Preprocessing pipeline (all fitted on train folds only)
| Step | Options | Default candidate | Decided by |
|------|---------|-------------------|-----------|
| 3.1 Validation | finite check, dtype cast, schema | strict reject | — |
| 3.2 Column pruning | drop constant, near-constant (var < ε), exact duplicates | on | E0 |
| 3.3 Variance-stabilising transform | none / `log1p` / Yeo-Johnson / quantile→normal | `log1p` for non-negative skewed columns | E2 (OD-4) |
| 3.4 Centering/scaling | standard / robust (median, IQR→MAD) | robust | E2 |
| 3.5 Winsorisation | clip at benign 0.1/99.9 percentiles (optional) | off | E2 |
| 3.6 Decorrelation | none / PCA-whitening / shrinkage whitening | handled inside detectors | E1 |
Notes: quantile transforms on n=800 create ties/plateaus and compress tail information — relevant because anomalies often live *beyond* benign tails; therefore tail-preserving transforms (log, robust) are preferred by default while quantile transform is tested as a comparator.

## 4. Feature engineering (unsupervised, label-free)
| Family | Description | Rationale |
|--------|-------------|-----------|
| Raw counters (transformed) | the d columns | Baseline |
| Ratios | e.g., misses/references, branch-misses/branches, IPC-like (instructions/cycles) — **only for counter pairs present** in the file | Ratios normalise workload scale and expose behavioural change (H1) |
| Log-ratios | log of the above | Symmetric two-sided deviations |
| Pairwise residuals | residual of counter *i* regressed on correlated counters (robust regression) | Detects broken relationships (H1) |
| PCA scores / residual norm | top-k PC coordinates and reconstruction error | Joint structure |
| Row-order features | rolling median of counters | Only if E6 shows drift (OD-7); default **off** |
Feature selection policy: **unsupervised only** (variance, correlation clustering, stability across bootstrap). Do **not** select features by performance on synthetic anomalies alone (risk R-06: proxy overfitting). Minor PCA directions (low variance) must be retained for Mahalanobis/PCA-residual detectors since anomalies breaking correlations appear there.

## 5. Candidate detectors
| # | Detector | Score | Strength | Weakness / mitigation | Evidence |
|---|----------|-------|----------|----------------------|----------|
| D1 | **Shrinkage Mahalanobis** (Ledoit-Wolf or OAS covariance; robust MCD variant) | (x−μ)ᵀΣ⁻¹(x−μ) | Captures joint structure; two-sided; closed-form; n=800 friendly with shrinkage | Gaussianity assumption; sensitive to contamination → compare MCD | [K] Mahalanobis, Ledoit–Wolf 2004, Rousseeuw 1999 |
| D2 | **PCA reconstruction + Hotelling T²** | residual norm & score-space distance | Exposes correlation breaks | Choice of k → select by retained-variance or parallel analysis | [K] Chandola survey; classical |
| D3 | **Isolation Forest** | mean path length | Few assumptions, scalable, no scaling needed | Weak on subtle correlation-only anomalies | [K] Liu, Ting, Zhou ICDM 2008; ADBench lists it among competitive shallow methods **[V]** |
| D4 | **kNN distance / LOF** | k-th NN distance / local density ratio | Non-parametric, multi-modal benign data | Curse of dimensionality; k choice | [K] LOF (Breunig 2000); kNN competitive in benchmarks **[V: arXiv 2507.15584 discussion]** |
| D5 | **Gaussian Mixture log-likelihood** | −log p(x) | Multi-modal benign behaviour (e.g., different input classes) | Covariance estimation at small n → diagonal/tied/shrunk, BIC for components | GMM is the modelling principle behind AdvHunter's HPC detector **[V]** |
| D6 | **ECOD / COPOD** | tail-probability aggregation | Parameter-free, fast, interpretable per-feature | Ignores dependencies by design (marginal-based) | [K] Li et al., COPOD ICDM 2020; ECOD TKDE 2022 |
| D7 | **One-class SVM** (RBF) | −decision function | Flexible boundary | ν,γ sensitive; hard to tune without anomalies | [K] Schölkopf et al. 2001 |
| D8 | **Autoencoder / Deep SVDD** | recon error / distance to center | Non-linear structure | ADBench reports deep unsupervised methods underperforming some shallow ones; tuning without labels is hard → **only enter if E-series shows a gap** | ADBench **[V]**; Deep SVDD [K] Ruff 2018 |

**Prior hypothesis for ordering (to be tested, not assumed):** D1/D2/D5 (structure-aware) + D3/D4 (non-parametric) form the core pool; D6 as a cheap marginal baseline; D7/D8 as comparators.

## 6. Ensemble and score fusion
1. **Normalise** each detector's score using its benign out-of-fold empirical CDF F_j: u_j = −log(1 − F_j(s_j) + 1/(n+1)) (a conformal-style p-value transform; comparable across detectors; larger = more anomalous).
2. **Fuse**: candidates — mean(u_j), max(u_j), rank-mean, or Fisher-style Σu_j. Max favours detectors that catch isolated strong signals; mean favours consensus. Decision = OD-3 via E7.
3. **Diversity check**: pairwise Spearman correlation of OOF scores; drop redundant detectors.
Hypothesis H3 predicts ensembles are more robust when the anomaly type is unknown; E7 tests this on synthetic profiles and benign stability — it cannot prove performance on real backdoors.

## 7. Hyperparameter policy (no anomaly labels)
- Prefer **defaults + regularisation** over search.
- Allowed label-free criteria: (i) OOF score **stability** across bootstrap/CV repeats (rank correlation), (ii) **calibration** (OOF FPR vs α), (iii) **BIC** for GMM, (iv) retained-variance for PCA, (v) **sensitivity profile** on synthetic stress tests used only as a *tie-breaker among stable configs*.
- Pre-registered selection rule (written before running E1–E7) — see EXPERIMENT_PLAN §8.
- Search budgets are small and logged; all configs tried are reported.

## 8. Threshold calibration
Let s*(x) be the fused score, S_oof = {s*(x_i)} computed out-of-fold on benign rows (n=800, repeated K-fold, scores averaged per row or taken per repeat).
- **Split-conformal quantile:** τ(α) = the ⌈(n+1)(1−α)⌉-th smallest of S_oof (guarantees marginal benign FPR ≤ α under exchangeability, **if A3/A4 hold** [K: Vovk et al.; conformal anomaly detection literature]).
- Statistical precision at n=800: standard error of an observed FPR p̂ ≈ √(α(1−α)/800): α=0.05 → ≈ 0.0077; α=0.01 → ≈ 0.0035 (arithmetic, not an experimental result). Hence α < 0.01 is poorly estimable.
- **Choice of α (OD-2).** Trade-off: lower α → fewer false alarms but lower TPR; the TPR side is unobservable. Because validation prevalence p is unknown (A5), expected accuracy = (1−p)(1−FPR) + p·TPR, so the best α depends on p. Candidate policy: report a small grid α ∈ {0.01, 0.05, 0.10}; ship one (default candidate 0.05) after organizer clarification; document the others in the report with their thresholds so the interface can swap.
- **Threshold stability**: bootstrap confidence interval for τ; if wide, prefer larger α or fewer detectors.
- **Fail-safe**: `CalibrationError` if n(1−α)< 20 effective tail points.
- AUROC is unaffected by τ; therefore **ranking quality is the first-order objective**, thresholding second.

## 9. Explainability
- Mahalanobis: per-feature contribution via decomposition of the quadratic form (e.g., diag of Σ⁻¹(x−μ)⊙(x−μ)) — signed deviation reported separately.
- PCA: per-feature squared residual.
- IForest/kNN/GMM: permutation-style or marginal z-score fallback.
- Output top-k with direction ("higher/lower than benign") — supports H4 and the dashboard (US-4).

## 10. Validation protocol (summary; details in EXPERIMENT_PLAN)
Repeated stratification-free K-fold (e.g., 5×10) producing OOF scores; time-blocked folds if drift suspected; bootstrap stability; calibration check; synthetic stress tests as labelled proxies; ablations; sensitivity to contamination.

## 11. Computational design
n=800 ⇒ all candidates fit in seconds–minutes on CPU; kNN/LOF O(n²) trivial. Cache OOF scores to disk keyed by config hash so selection experiments are re-analyzable without refits.

## 12. Known limitations of the design
1. Cannot measure TPR on real backdoors (F4).
2. Threshold validity depends on A3/A4 (no distribution shift).
3. Adaptive attackers can mimic benign HPC profiles (research gap, see RESEARCH §7).
4. If A7 fails, no detector will succeed; the design only guarantees honest reporting, not feasibility.
