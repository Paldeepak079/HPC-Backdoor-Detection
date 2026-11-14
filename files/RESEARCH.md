# RESEARCH — Literature Review, Related Work, Feasibility, Research Gaps

**Citation integrity policy.** Entries are tagged:
- **[V]** — existence, title, authors and venue confirmed by web search during this documentation phase. Content claims are limited to what the search snippets showed.
- **[K]** — recalled from background knowledge; **not re-verified here**. Check title, venue and year against the publisher before putting it in the PDF report.
No experimental number from any paper is reproduced unless it appeared in a retrieved snippet; those are attributed to the authors. Nothing below is a result of this project.

---

## 1. Scope of the review
Four strands: (1) neural backdoor attacks and non-HPC defences; (2) HPCs for security / side channels and their pitfalls; (3) HPC-based detection of DNN attacks; (4) unsupervised anomaly detection for small tabular data and calibration.

## 2. Backdoor attacks and defence taxonomy
| Work | Tag | Relevance |
|------|-----|-----------|
| Gu et al., *BadNets* (2017) | [K]; named as an early backdoor attack in a retrieved related-work section [V-context] | Canonical trigger-based backdoor |
| Chen et al., *Targeted backdoor attacks … data poisoning* (2017) | [K] | Poisoning-based, blended triggers |
| Liu et al., *Trojaning Attack on Neural Networks*, NDSS 2018 | [K] | Trojan insertion without original data |
| Wang et al., *Neural Cleanse*, IEEE S&P 2019 | [V-context] (cited in AEVA related work) | Trigger reverse-engineering; needs model access |
| Liu et al., *ABS* (2019) | [V-context] | Neuron-stimulation analysis; white-box |
| Chen et al., *Activation Clustering* (2018) | [V-context] | Separates poisoned samples by activations; needs training data |
| Tran et al., *Spectral Signatures*, NeurIPS 2018 | [K]; referenced as covariance-spectrum approach [V-context] | Poison-sample detection |
| Gao et al., *STRIP*, ACSAC 2019 | [K] | Input-perturbation entropy at runtime |
| Liu et al., *Fine-Pruning*, RAID 2018 | [K] | Mitigation |
| Guo, Li, Liu, *AEVA: Black-box Backdoor Detection Using Adversarial Extreme Value Analysis*, ICLR 2022 (arXiv 2110.14880) | **[V]** | Black-box, hard-label model-level detection (needs queries, not HPCs) |
| Dong et al., *Black-Box Detection of Backdoor Attacks with Limited Information and Data*, ICCV 2021 | **[V]** | Query-only detection |

**Takeaway.** Most mainstream defences need white-box access, clean/poisoned training data, or many queries. The HPC route is a *side-channel* defence needing only a runtime measurement — which is the premise of this competition.

## 3. HPCs for security
| Work | Tag | Relevance |
|------|-----|-----------|
| Demme et al., *On the Feasibility of Online Malware Detection with Performance Counters*, ISCA 2013 | [K] | Early evidence that HPC features support supervised malware detection |
| Tang, Sethumadhavan, Stolfo, *Unsupervised Anomaly-Based Malware Detection Using Hardware Features*, RAID 2014 | [K] | **Closest methodological precedent**: one-class modelling of benign HPC behaviour |
| Das et al., *SoK: The Challenges, Pitfalls, and Perils of Using Hardware Performance Counters for Security*, IEEE S&P 2019 | [K] | Documents nondeterminism, multiplexing, overcount, portability problems |
| Weaver, Terpstra, Moore, *Non-determinism and Overcount on Modern Hardware Performance Counter Implementations*, ISPASS 2013 | [K] | Measurement noise characteristics |
| Linux `perf_event_open(2)` man page; Intel® 64 and IA-32 SDM Vol. 3B (performance monitoring) | [K] official docs | Counter semantics, multiplexing |
| A UC Davis ICTAI paper on stealthy malware found in search (Rafatirad group) | **[V]** exists; snippet states HPC-based detection degrades for stealthy malware | Illustrates HPC detectors' weakness against evasive behaviour (different domain) |

## 4. HPC-based detection for neural-network attacks
### 4.1 Backdoor detection from HPCs
- **Alam, Wang, Maniatakos, *Detecting Backdoor Attacks in Black-Box Neural Networks through Hardware Performance Counters*, DATE 2024.** **[V]** (title, authors, venue). This is the paper whose setting this competition most plausibly derives from (an inference *from the title*; it is **not** a confirmed fact that the competition is based on it). **Method details and results were not retrievable here — read the paper before relying on them.**
### 4.2 Adversarial-example detection from HPCs
- **AdvHunter: Detecting Adversarial Perturbations in Black-Box Neural Networks through Hardware Performance Counters** (ACM, Nov 2024, DOI 10.1145/3649329.3655682). **[V]** Retrieved abstract: monitors microarchitectural activity during inference and uses principles of **Gaussian Mixture Models** to detect adversarial examples. Supports GMM (D5) as a literature-grounded candidate.
- **Rahaman, Chatterjee, Bhunia, *Runtime Detection of Adversarial Attacks in AI Accelerators Using Performance Counters* (SAMURAI / TANTO), arXiv 2503.07568.** **[V]** Introduces AI performance counters + an analysis engine; the authors claim up to 97% accuracy on adversarial attacks (author claim, adversarial—not backdoor—setting, accelerator-specific counters).
### 4.3 Counter-evidence on stealthy trojans
- **(A)iSpy: Parasitic Trojans for Machine Learning Infrastructure** (arXiv 2607.17550). **[V]** Appendix L.1 (as retrieved) reports that a SAMURAI-style counter-based detector performed near chance (mean ROC-AUC 0.492, accuracy 48%) against the authors' *runtime-level* trojan designed to preserve activation statistics and timing. Different attack class and different counters, so **not directly transferable**, but a caution for assumption A7.
### 4.4 Side-channel recovery of DNN structure (context for feasibility)
- Yan et al., *Cache Telepathy*, USENIX Security 2020, and related DNN architecture-extraction side-channel work (e.g., DeepSniffer, ASPLOS 2020) — [K], authors/venues to verify. They indicate that microarchitectural signals encode network structure/behaviour; presence of **some** input-dependent signal is plausible, magnitude for backdoor triggers is unknown (H-level).

## 5. Unsupervised anomaly detection (small tabular data)
| Work | Tag | Use here |
|------|-----|----------|
| Han et al., **ADBench**, NeurIPS 2022 D&B (arXiv 2206.09426) | **[V]** | 30 algorithms × 57 datasets; retrieved summary: no unsupervised method statistically dominates; deep methods (DeepSVDD, DAGMM) can underperform some shallow ones |
| arXiv 2507.15584 (benchmark-practice critique; title not captured) | **[V]** exists; snippet says kNN and Isolation Forest perform competitively, and questions pooling dissimilar datasets | Supports using simple baselines and per-problem evaluation |
| Chandola, Banerjee, Kumar, *Anomaly Detection: A Survey*, ACM CSUR 2009 | [K] | Taxonomy |
| Liu, Ting, Zhou, *Isolation Forest*, ICDM 2008 | [K] | D3 |
| Breunig et al., *LOF*, SIGMOD 2000 | [K] | D4 |
| Schölkopf et al., *Estimating the Support of a High-Dimensional Distribution*, Neural Computation 2001 | [K] | D7 |
| Ruff et al., *Deep One-Class Classification*, ICML 2018 | [K] | D8 |
| Li et al., *COPOD* (ICDM 2020), *ECOD* (TKDE 2022) | [K] | D6 |
| Zhao, Nasrullah, Li, *PyOD*, JMLR 2019 | [K] | Library |
| Ledoit & Wolf, *A well-conditioned estimator for large-dimensional covariance matrices*, J. Multivariate Analysis 2004; Rousseeuw, *MCD* 1999 | [K] | D1 covariance estimation |
| Vovk, Gammerman, Shafer, *Algorithmic Learning in a Random World*; conformal anomaly detection (e.g., Laxhammar & Falkman) | [K] | Threshold calibration |

## 6. Technical feasibility assessment
| Question | Assessment | Status |
|----------|-----------|--------|
| Can a one-class model be trained on 800 rows? | Yes for low-capacity models; d vs n unknown (F8). Shrinkage/PCA make high d workable. | Reasoned |
| Is a signal likely to exist? | Plausible (HPC literature on DNN side channels; task design presupposes it) but **unverified** for this data (A7). Counter-evidence for stealthy trojans exists (4.3). | Hypothesis |
| Can FPR be controlled? | Yes, in principle, via conformal quantile if A3/A4 hold. | Reasoned |
| Can TPR be estimated? | **No** on real data (F4). Only synthetic sensitivity profiles. | Fact-by-construction |
| Is deep learning warranted? | Not by default (H6). | Hypothesis |
| Is the evaluation threshold-sensitive? | Yes for Accuracy/F1; AUROC is not. | Fact |

## 7. Research gaps (opportunities and honest limits)
1. **Benign-only HPC backdoor detection** has little public methodology to benchmark against; we found only the DATE 2024 title for the setting (details unread).
2. **Joint-structure vs marginal detection** on HPC vectors is under-explored in what we retrieved; H1 is testable on our data.
3. **Threshold calibration without anomalies** under unknown prevalence — conformal quantiles are standard in ML, rarely reported for HPC security (not verified exhaustively).
4. **Cross-machine / cross-session generalisation** of HPC detectors is a known pitfall class (SoK [K]); out of scope but central to A4.
5. **Adaptive attackers** who shape triggers to preserve HPC profiles — (A)iSpy-type evidence hints at feasibility of evasion; no defence is evaluated here.

## 8. Reading list to complete before final report (priority order)
1. Alam et al. DATE 2024 (full text) — method, features, thresholding, reported limits.
2. AdvHunter full text — GMM details for HPC data.
3. Tang et al. RAID 2014 — unsupervised HPC anomaly design.
4. Das et al. S&P 2019 SoK — measurement pitfalls checklist.
5. ADBench full text — algorithm settings and caveats.
6. Weaver et al. ISPASS 2013 — noise model.

## 9. Conclusions for design (carried into TECHNICAL_DESIGN)
- Use a **small pool of diverse, regularised shallow detectors**; include a GMM and a structure-aware Gaussian method.
- Do not claim domain-specific superiority; ADBench-type evidence is general, not HPC-specific.
- Treat threshold calibration as a first-class component.
- Document A7 and R-01 prominently.
