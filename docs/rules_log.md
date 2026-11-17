# Rules log

Every analytic choice is listed here and fixed in `riskshift/config.py` before any results were computed. This file becomes the methods section.

## Data rules

| # | Rule | Why |
| --- | --- | --- |
| D1 | Locations are keyed by block position in S14B (India = 353, states = 354–384), never by name. | "Punjab" appears for both India and Pakistan. |
| D2 | Thousands separators are stripped and values cast to float. "-" is treated as missing, not zero. | S14B stores numbers as text, and "-" means "not estimated". |
| D3 | Four risks are dropped: bullying victimization, nitrogen dioxide pollution, occupational noise, and occupational ergonomic factors. | They have no estimated mortality anywhere in India (4.6% of risk rows were "-"). |
| D4 | Risk levels come from GBD Appendix 2 Table S1, carried in the pilot extract and frozen in `data/reference/risk_hierarchy.csv`. Four names are mapped by hand: low birth weight and short gestation → 3, low birth weight → 4, diet low in fiber → 3, bullying victimization → 3. | S14B names differ slightly from the hierarchy table. |
| D5 | Parent risk is taken from the published depth-first row order. | The hierarchy table itself was not uploaded. |
| D6 | Analyse one hierarchy level at a time. Never sum across levels or across risks. | Risks nest across levels and are mediated (for example, BMI acts through blood pressure), so attributable deaths overlap. |
| D7 | "Other Union Territories" is kept but flagged, and every RQ is repeated without it. | It is an aggregate unit, not a single state. |
| D8 | Negative lower bounds are kept. Values are clipped at 0.05 only for log transforms. 225 risk rows have a negative lower bound. | A negative bound means the risk could be protective or harmful. |
| D9 | 1990 is used only as a direction check (`recent_reversal`). It is never a scored feature, except in the RQ4 migration extension, which uses point estimates. | No interval is published for changes from 1990. |
| D10 | One cell (Sikkim, high temperature) has ASR 0.0 in both years and no % change. Its direction is set to 0. | Zero base. |
| D11 | Detail-set inclusion requires ASR ≥ 0.5 in every state unit in 2010 and 2023. | S14B rounds ASR to 0.1, so smaller values carry more than 10% rounding error. |
| D12 | In the Detail set, particulate matter pollution is split into ambient PM and household air pollution (both level 4). | The plan asks for this contrast, and those two risks sit at level 4. |

| D13 | Benchmarks are keyed by block position: Global = 0, South Asia region = 350. Block 349 is the South Asia super-region, which has the same name. S14B's Global rows stand in for S14A. | The plan named S14A for global context, and S14B holds the same Global rows. |
| D14 | Cause breakdown drops aggregate cause rows ("Total cancers", "Total burden related to …"). Level-2 risks with no cause rows of their own use their child risks' causes, summed by cause and flagged "via child risks". Bars are scaled to the risk's own change. | Aggregates double-count, and child risks can overlap. |

## RQ rules

| # | Rule |
| --- | --- |
| R1.1 | **Clear worsening**: GBD 2010–23 % change lower bound > 0. **Possible worsening**: point estimate > 0 and the interval crosses 0. **Adverse divergence**: the rate fell (or was flat), but by at least 10 percentage points less than India's change. The 5 and 15 pp thresholds are tested in RQ3. |
| R1.2 | Tiers are descriptive labels, not significance tests. No multiple-testing correction is applied, because cells are not independent tests. |
| R2.1 | Baselines: B1 = 2023 deaths and B2 = 2023 ASR. Weights are 0.40 rate, 0.35 worsening and 0.25 divergence. |
| R2.2 | **Within-risk** score: min-max per risk of ASR 2023, % change and % divergence. It is used only for per-risk state rankings. |
| R2.3 | **Cross-risk** score: percentile across all pairs of log ASR 2023, absolute ASR change, and the absolute-change gap vs India. A pair needs 2023 ASR ≥ 10 per 100,000 to enter a top N. |
| R2.4 | Success criterion: at least 3 new pairs in the cross-risk top 20 that are clear-worsening, at or above the floor, not small-base, and absent from both baseline top 20s. |
| R3.1 | Weights: 1,000 Dirichlet(1,1,1) draws plus 5 corner cases. Uncertainty: an all-lower-bounds scenario, an all-upper-bounds scenario, and 1,000 Monte Carlo draws. Selection: 20 leave-one-risk-out runs, the Policy-salient set, and a run without Other UTs. |
| R3.2 | Monte Carlo draws: 2023 ASR is lognormal, fitted to its 95% interval on the log scale. The 2010–23 % change is normal, fitted to GBD's change interval and clipped at −99%. 2010 ASR is implied by these two. Cells are drawn independently. This is a conservative stress test, not a posterior, because IHME's draws are not public. |
| R3.3 | Labels: Robust if the pair is in the top N in at least 80% of scenarios, Moderate if 50–80%, Fragile if under 50%. Each label is computed per family. The overall label is the weakest family label. |
| R4.1 | Feature grid: 4 families (F1 level, F2 shape, F3 change, F4 level + change) × 3 risk sets × 2 scalings (z-score, median/IQR) = 24 configurations, for 31 and for 30 units. Sets wider than 20 features, and every F4, are reduced by PCA to 80% of variance. |
| R4.2 | Algorithms: K-means (50 starts), Ward, average linkage, and diagonal Gaussian mixture, each for k = 2–6. k is chosen by majority vote of silhouette, gap statistic (Tibshirani rule, 50 uniform references in a PCA-aligned box) and Calinski–Harabasz. If there is no majority, silhouette decides. A gap vote for k = 1 counts as no vote, but it is reported. |
| R4.3 | Null test: 500 multivariate-normal datasets with the observed mean and covariance, plus 500 column-shuffled datasets. Each is scored by its best K-means silhouette over k = 2–6. **Gate 1** requires an observed silhouette ≥ 0.25 that also exceeds the 95th percentile of the multivariate-normal null. |
| R4.4 | **Gate 2** requires every cluster's bootstrap Jaccard (500 resamples, Hennig's method) to be ≥ 0.75, and the configuration's median ARI with the other 23 configurations to be ≥ 0.60. |
| R4.5 | Verdict per configuration: **robust** if it passes both gates. **Partial** if it passes gate 1 and has at least one cluster with Jaccard ≥ 0.75. Otherwise **gradient, not clusters**. The overall verdict is the one most configurations reach. |
| R4.6 | Consensus matrix: the equal-weight average of four co-assignment sources (the configuration grid, bootstraps, the 1,000 uncertainty refits, and leave-one-risk-out refits). States with co-assignment ≥ 0.70 under average linkage form a stable core. A floater is a state whose highest co-assignment with any other state is below 0.50. |
| R4.7 | External label: Zonal Councils. SDI (Appendix 1 S12) was not supplied. |
| R4.8 | Peer benchmark: state % change minus the median % change of its k = 3 cluster peers. A pair is a "hidden divergence" if it is at least 10 pp worse than its peers while carrying no RQ1 tier against India. |
| R4.9 | Migration extension: one PCA over 1990, 2010 and 2023 pooled, with K-means centroids (k = 3) fitted once on the pooled data. There are two variants: level, and shape (row-centred). |

## Fixed seeds and settings

The seed is `20261116`, used for every stochastic step. Draw counts and thresholds are in `riskshift/config.py`.

## Deviations from the plan

* S14A, S15A, the Appendix 2 hierarchy file and Appendix 1 S12 (SDI) were not in the folder. Hierarchy levels came from the pilot extract (D4). The SDI check is replaced by a Zonal Council check. The S14A global benchmark is taken from S14B's own Global block (D13).
* `rq4_figures` is a script, not a notebook, so the whole pipeline runs from `run_all.py`.
* The optional evidence-star family (Appendix 2 S8) and the India map (which needs an external boundary file) were not done.
* F2 "shape" uses the row-centred log ASR. The PAF variant mentioned in the plan was not run.
