# RiskShift-India: Project Explainer and Implementation Plan

Nov 16, 2026 · @rank sarthi

## What the project is

RiskShift-India asks whether a trend-aware, uncertainty-aware ranking of Indian state x risk-factor pairs surfaces different, defensible priorities than a simple "most deaths" or "highest death rate" ranking. It is a screening tool, not a forecast and not a causal study.

The logic in four steps:

1. **Measure** - for each of 31 Indian state units and each risk factor, take GBD 2023 risk-attributable deaths and age-standardised death rates (ASR) for 1990, 2010 and 2023 (S14B).
2. **Detect** - flag pairs whose ASR rose from 2010 to 2023, or fell less than India's, i.e. diverged adversely from the national benchmark (RQ1).
3. **Prioritise** - compare a transparent multi-criteria score (current rate + worsening + divergence) against burden-only rankings, and count what is newly surfaced (RQ2); then stress-test those ranks against weights, GBD uncertainty bounds and risk selection (RQ3).
4. **Group** - check whether states fall into compact, interpretable risk-profile clusters, and whether those clusters survive reasonable changes in features (RQ4).

The expected outputs are an emerging-pattern watchlist, a burden-vs-trend ranking comparison with stability labels, a clustering view, and a small Streamlit explorer. Status today: the proposal (27 Oct 2026) is pre-implementation; no model has been trained. This doc adds a feasibility pilot run on the real S14B India data.

## What the uploaded files are

Only one file holds analysable numbers: S14B. Everything else is reference metadata from the GBD 2023 "Diseases, Injuries and Risk Factors" (DIRF) appendices, useful for cleaning and for the methods section. S14A and S15A, named in the proposal, were not in this upload; they are optional context and nothing below depends on them.

| File | What it contains | Role in RiskShift |
| --- | --- | --- |
| S14B Global and Location-Specific Risk Factor Deaths | 595,020 rows = 705 location blocks x 844 rows (88 risk "All causes" rows + 756 risk -> cause sub-rows). Deaths, death PAF and ASR for 1990/2010/2023, % change 2010-23, each with mean / lower / upper. | Primary data for all four RQs |
| Appendix 2, Table S1 - risk hierarchy | 88 risks with level 0-4 | Selects non-overlapping risk sets (critical) |
| Appendix 2, Table S3 - risk-outcome pairs | Which risk -> cause pairs are included, new or removed in GBD 2023 | Explains sub-rows; flags definitional changes |
| Appendix 2, Tables S4-S6 | TMREL counterfactuals; mediation matrix (e.g. BMI acting through blood pressure) | Explains why risk deaths cannot be summed |
| Appendix 2, Tables S7-S8 | Data-source counts per risk; evidence star ratings for risk-outcome pairs | Optional evidence-strength weight in RQ3 |
| Appendix 1, Tables S1, S3, S12 | Location hierarchy; cause hierarchy; SDI group per location | S12 gives an external label for validating RQ4 clusters |
| Appendix 1, Tables S2, S9-S11, S13-S14 | GATHER checklist, disability weights, YLD methods, ICD map, cause source counts | Methods/limitations citations only |
| Table index | Maps table numbers to files | Navigation |

Two naming traps: the appendix titles say "Nonfatal Methods", but S14B is a mortality table; and four risk names in S14B differ slightly from the hierarchy file (e.g. "Low birth weight and short gestation"), so they need a manual mapping.

## Data audit: what the India extract actually looks like

The India slice is clean and small: 32 location blocks (India + 31 state units) x 844 rows = 27,008 rows, extracted in about 100 seconds from the 950 MB sheet. The proposal's example figures check out (Uttar Pradesh ambient PM ASR 72.7 -> 118.7 per 100,000).

| Issue found | Consequence | Rule for the pipeline |
| --- | --- | --- |
| Numbers stored as text with thousands separators | Cannot compute until parsed | Strip commas, cast to float |
| "-" in about 4.5% of risk rows | Means "not estimated", not zero | Treat as missing. All four affected risks (bullying victimization, NO2, occupational noise, occupational ergonomic factors) have no mortality anywhere in India: drop them |
| "Punjab" appears twice (India and Pakistan) | Name joins silently mix countries | Key locations by block position / parent, never by name alone |
| "Other Union Territories" is an aggregate unit | Not comparable to a single state | Keep, but label it and run every RQ with and without it |
| Risks nest across 5 levels (1 + 3 + 20 + 42 + 22) | Parent and child deaths overlap | Analyse one level at a time; never sum across levels or across risks |
| Lower bounds can be negative (e.g. handwashing) | Protective-or-harmful uncertainty | Clip at 0 only for log transforms, and record it |
| Change intervals are given only for 2010-23, not for 1990-2010 or 1990-2023 | Long-horizon uncertainty unknown | Use 1990 only as a direction check, not a scored feature |

The 20 level-2 risks are the natural analysis unit: siblings in the hierarchy, broad enough to be stable, and all with mortality. Their typical state rates span two orders of magnitude, from intimate partner violence (median 1.7 per 100,000) to air pollution (155.1), which matters for every scoring choice below.

## Feasibility pilot: four findings that change the plan

A quick pilot on the 31 states x 20 level-2 risks shows the project is feasible, but that RQ2 and RQ4 need sturdier designs than the proposal sketches. These are exploratory numbers, not results to report.

**1. Worsening is real but concentrated, and most of it is not statistically clear (RQ1).** Of 620 state x risk pairs, 185 have a higher ASR in 2023 than in 2010, but only 41 have a 2010-23 change interval wholly above zero. Of those 41, 18 are high body-mass index and 8 are high fasting plasma glucose. Nationally, these are the only two level-2 risks whose rate clearly rose (BMI +36.7%, interval 8.5 to 72.7; glucose +26.7%, interval 0.8 to 57.4).

**2. The proposed score surfaces very different cases, partly for the wrong reason (RQ2).** With the 0.40/0.35/0.25 weights and min-max scaling within each risk, only 4 of the top 20 pairs overlap with the top 20 by 2023 rate. But the new entries include drug use in Uttarakhand (7.0 per 100,000) next to dietary risks in Bihar (140.7). Within-risk scaling gives every risk's worst state a score near 1, however small the risk. Some of the "novelty" is a scaling artefact.

**3. State clusters are weak (RQ4).** Across four feature sets and k = 2 to 6, silhouette scores sit between 0.15 and 0.29. On the usual reading, 0.26-0.50 is "weak structure" and below 0.25 is "no substantial structure". K-means and Ward agree well at k = 3 (adjusted Rand index 0.82), so a 3-group partition is reproducible by method, but not well separated.

**4. Clusters are fragile to GBD uncertainty (RQ3/RQ4).** Redrawing each 2023 rate within its uncertainty interval drops agreement with the base 3-cluster solution to a median ARI of 0.38; dropping 20% of risks gives 0.60. The first principal component (49% of variance) is mostly overall burden level, not profile shape: removing level (row-centring) makes clusters weaker still (silhouette 0.16-0.19).

The tentative k = 3 groups are still interpretable, which is worth keeping as a hypothesis: (a) 9 hill / north-eastern states plus Rajasthan, with low metabolic burden and relatively high drug and alcohol burden; (b) 5 southern-central states (Andhra Pradesh, Telangana, Karnataka, Chhattisgarh, Uttarakhand) with high dietary, LDL and other-environmental burden; (c) the remaining 17. The plan below treats RQ4 as a genuine test that may return "no robust clusters", which is a reportable answer.

## Shared pipeline (feeds all four RQs)

Build this once, version it, and freeze it before any RQ analysis so results cannot be tuned by quietly changing the data.

1. **Extract** (`01_extract.py`) - stream S14B once to a numeric CSV/Parquet; slice India + 31 states by block position; parse numbers; "-" -> missing. Already prototyped.
2. **Annotate** (`02_annotate.py`) - attach risk level from the hierarchy table (with the 4-name manual map), split "All causes" rows from risk -> cause sub-rows, tag national vs state, attach SDI group from Appendix 1 S12.
3. **Analysis sets** (`03_sets.py`) - define three pre-registered risk sets:
   - **Core**: the 20 level-2 risks.
   - **Detail**: level-3 risks with mortality in all states (e.g. ambient PM vs household air pollution; smoking vs chewing tobacco).
   - **Policy-salient**: 8-10 risks chosen by an explicit rule (top national 2023 ASR plus any risk with a clearly rising national rate), fixed in writing before results are seen.
4. **Features** (`04_features.py`) - one tidy table, one row per state x risk: ASR 1990/2010/2023 with bounds; deaths 2023; PAF 2023; absolute and % change 2010-23 with GBD's interval; India's change; divergence = state % change minus India % change; flags `worse_point`, `worse_clear` (lower bound > 0), `small_base` (2010 ASR under 5 per 100,000).
5. **Data dictionary + rules log** - every choice above in one markdown file; it becomes the methods section.

Stack: Python, pandas, NumPy, SciPy, scikit-learn, Plotly, Streamlit; Git for versioning; a fixed random seed for every stochastic step.

## RQ1 - Which state x risk pairs worsened, and which diverged from India?

**Output:** a three-tier watchlist of worsening and diverging pairs, each with a one-line plain-language reason.

**Method**

1. Classify every Core-set pair into tiers using GBD's own 2010-23 % change interval:
   - **Clear worsening** - lower bound > 0 (pilot: 41 pairs).
   - **Possible worsening** - point estimate > 0 but interval crosses 0 (pilot: 144).
   - **Adverse divergence** - rate fell, but by at least 10 percentage points less than India's fall for the same risk (threshold fixed in advance; test 5 and 15 in RQ3).
2. Report absolute change alongside % change, and mark `small_base` pairs so that a rise from 2 to 4 per 100,000 is not read like a rise from 60 to 120.
3. Use the 1990 rate as a direction check: does 1990-2023 agree with 2010-23? Disagreement gets a "recent reversal" label.
4. Repeat on the Detail set to see what sits inside each level-2 signal (e.g. ambient PM rising while household air pollution falls).

**Visuals:** a state x risk heatmap of % change with tier markers; for each watchlist pair, a dumbbell chart of 2010 vs 2023 state ASR against India.

**Caveat:** an interval from GBD reflects model uncertainty in each year, and differences between pairs are not independent tests; no multiple-testing correction is valid here, so the tiers are descriptive labels, not significance claims.

## RQ2 - Does trend-aware prioritisation surface different cases?

**Output:** a burden-only vs trend-aware comparison table, plus a list of "overlooked" pairs (in the trend-aware top N, absent from the burden top N) with the reason each was surfaced.

**Baselines:** B1 = 2023 attributable deaths; B2 = 2023 ASR. **Candidate:** priority = 0.40 x current rate + 0.35 x worsening + 0.25 x divergence.

**Fix the scaling problem the pilot exposed.** Score two variants and report both:

- **Within-risk** ("which state is worst for this risk?") - min-max per risk, as proposed. Use it for per-risk state rankings only.
- **Cross-risk** ("which pairs matter most overall?") - rate signal = percentile of log ASR across all pairs; worsening = absolute ASR change (deaths per 100,000, so size counts); divergence = absolute-change gap vs India. Add a materiality floor (e.g. 2023 ASR at or above 10 per 100,000) before a pair can enter the top N.

**Measures,** each at N = 10, 20 and 30: Jaccard overlap of top-N sets; Spearman and Kendall rank correlation; count and list of newly surfaced pairs; share of new pairs that are "clear worsening" in RQ1 (a quality check: novelty should come from real change, not noise or small bases).

**Success criterion (set in advance):** the trend-aware list adds at least a few pairs per top 20 that are clear-worsening, above the materiality floor, and not in either baseline. If novelty comes mainly from small-base or interval-crossing pairs, report that honestly as a negative result.

## RQ3 - How stable are the rankings?

**Output:** a stability label on every top-N pair - Robust (in top N in at least 80% of scenarios), Moderate (50-80%), Fragile (under 50%) - plus a sensitivity summary table.

Three perturbation families, each run on the cross-risk score from RQ2:

| Family | What changes | How | Runs |
| --- | --- | --- | --- |
| Weights | The 0.40/0.35/0.25 split | Sample weights uniformly from the simplex (Dirichlet(1,1,1)); also corner cases such as rate-only and trend-only | 1,000 |
| GBD uncertainty | Rates and changes | (a) Extreme scenarios: all lower bounds, all upper bounds; (b) Monte Carlo: draw each value from a normal fitted to its 95% interval (log scale for rates), clipped at 0 | 2 + 1,000 |
| Risk selection | Which risks are ranked | Swap Core / Detail / Policy-salient sets; leave-one-risk-out; with and without "Other Union Territories" | about 25 |

**Measures:** top-N membership frequency per pair; median and 90% range of each pair's rank; Kendall tau between base and perturbed rankings; for RQ1 tiers, the share of pairs whose tier flips.

**Honest limitation to state:** IHME's 500 posterior draws are not public in S14B, so independent draws per cell ignore correlations between years, states and risks. This likely overstates rank noise for changes (because 2010 and 2023 errors are correlated) and should be described as a conservative stress test, not a true posterior. The appendix evidence star ratings (Appendix 2, S8) can optionally be added as a fourth family: down-weight pairs whose risk-outcome evidence is rated one star.

## RQ4 - Do compact, interpretable, stable state clusters exist? (detailed plan)

RQ4 should be run as a test with a pre-declared answer key, not as "run K-means and describe the groups". The pilot says weak structure is likely, so the plan must be able to conclude either "yes, these clusters are robust" or "no, India's states lie on a continuous gradient", and both are publishable answers.

### 4.1 Break RQ4 into four testable parts

| Part | Question | Main evidence |
| --- | --- | --- |
| 4a Existence | Is there more grouping than a correlated cloud of points would show? | Silhouette, gap statistic, comparison with null data |
| 4b Stability | Do the same states group together when data or choices change? | Bootstrap Jaccard, ARI across feature grid, consensus matrix |
| 4c Interpretability | Can each group be described by a few risks in plain words? | Profile heatmap, top distinguishing risks |
| 4d External meaning | Do groups line up with things they were not built from? | SDI group (Appendix 1 S12), geography, RQ1 watchlist |

### 4.2 Units and features

Units: 31 state units; every result is repeated without "Other Union Territories". With 31 units, more than 20 raw features risks noise-driven clusters, so any set wider than that is first reduced by PCA to the components covering 80% of variance.

The feature grid, fixed before analysis (the pilot showed choices matter):

| Family | Features per risk | What it captures |
| --- | --- | --- |
| F1 Level | log ASR 2023 | How heavy the burden is (pilot PC1 = 49% of variance is mostly this) |
| F2 Shape | log ASR 2023 minus the state's mean log ASR; or PAF 2023 | Which risks dominate, independent of overall level |
| F3 Change | absolute ASR change 2010-23 (signed log-ratio as a variant) | Direction of travel |
| F4 Level + change | F1 and F3, PCA-reduced | Where states are and where they are heading |

Each family x risk set (Core, Detail, Policy-salient) x scaling (z-score, robust median/IQR) = 24 feature configurations.

### 4.3 Algorithms and k

Run K-means (50 starts), Ward hierarchical, average-linkage hierarchical, and a Gaussian mixture (diagonal covariance, chosen by BIC) for k = 2 to 6. With n = 31, do not go above 6 and do not use density methods such as DBSCAN, which need far more points. Choose k per configuration by agreement of silhouette, gap statistic and Calinski-Harabasz, not by one index.

### 4.4 Existence test against null data (4a)

This is the step that makes RQ4 rigorous. For each configuration, generate 500 null datasets with no true clusters but the same correlations: draw from a multivariate normal with the observed mean and covariance (plus a column-shuffled variant). Cluster each null set the same way and record its best silhouette. Real structure is claimed only if the observed silhouette exceeds the 95th percentile of the null. This directly answers the obvious objection that K-means always returns k groups.

### 4.5 Stability tests (4b)

1. **Bootstrap states** - resample the 31 states 500 times, recluster, and compute each cluster's mean Jaccard similarity to its best match (Hennig's clusterboot logic): at least 0.75 = stable, 0.60-0.75 = pattern, under 0.50 = dissolved.
2. **Feature-choice agreement** - pairwise adjusted Rand index across all 24 configurations; summarise as a heatmap and a median.
3. **Uncertainty draws** - reuse RQ3's 1,000 Monte Carlo datasets (pilot median ARI 0.38 under independent draws).
4. **Leave-one-risk-out** - 20 refits; flag any single risk whose removal reshapes the partition.
5. **Consensus matrix** - across every run above, the share of runs in which each pair of states lands together. Reorder it hierarchically; stable cores show as dark blocks, and "floating" states (co-assignment under 0.5 with everyone) are named explicitly.

### 4.6 Decision rule (declared in advance)

Report **robust clusters** only if all four hold: observed silhouette at least 0.25; beats the null at the 95th percentile; every cluster's bootstrap Jaccard at least 0.75; median cross-configuration ARI at least 0.60. Report **partial structure** if only a stable core survives (name the core states and the floaters). Otherwise report **a gradient, not clusters**, and describe the states with the PCA axes instead.

&#91;embedded content: RQ4 answer key · 2 gates, 3 possible conclusions\]

Every configuration passes through the same two gates; the overall RQ4 verdict is the one most configurations reach.

### 4.7 Interpretation (4c) and external checks (4d)

- **Profiles:** heatmap of cluster mean z-scores by risk; for each cluster, the 3 risks that most separate it from the rest, in one sentence (e.g. "low metabolic burden, relatively high drug and alcohol burden").
- **PCA biplot:** pilot loadings suggest PC1 = overall burden and PC2 = traditional risks (tobacco, malnutrition, occupational) versus metabolic risks (BMI, LDL, kidney) - an epidemiological-transition axis worth naming if it holds.
- **External labels:** cross-tabulate clusters with SDI group (Appendix 1 S12) and with region; report ARI. Agreement makes the clusters credible; low agreement means they carry information SDI does not.
- **Link to RQ1/RQ2:** test whether watchlist pairs concentrate in one cluster, and add a **peer benchmark**: compare each state to its cluster's median as well as to India, which can reveal divergence hidden by a national average.

### 4.8 Extension that fits the project name: profile migration 1990 -> 2010 -> 2023

Fit one PCA on all three years pooled (age-standardised rates are comparable over time), then plot each state's path through the same space and cluster each year with fixed centroids. A Sankey of cluster membership across years shows which states "shifted" profile, e.g. from a traditional-risk to a metabolic-risk pattern. This uses the 1990 data the other RQs only use as a direction check.

### 4.9 RQ4 deliverables

- Existence table: per configuration, k, silhouette, null 95th percentile, verdict.
- Consensus heatmap with named cores and floaters.
- PCA biplot with 1990-2023 trajectories.
- Cluster profile heatmap and one-sentence cluster descriptions.
- Optional India map (needs an external state boundary file that merges J&K and Ladakh and groups the small UTs to match GBD).

**Code:** `rq4_features.py`, `rq4_cluster_grid.py`, `rq4_null.py`, `rq4_stability.py`, `rq4_migration.py`, `rq4_figures.ipynb`. Compute is small: the full grid (24 configurations x 4 methods x 5 values of k, plus 500 nulls and 500 bootstraps each) runs on a laptop in well under an hour.

## Timeline, deliverables and risks

An 8-week plan fits the work, with RQ4 given the most time because its null and stability tests are the project's main methodological contribution.

&#91;embedded content: suggested plan · 8 weeks; no deadline was given, so weeks are relative\]

RQ4 can start in week 4 because it needs only the frozen features, not RQ2's scores; its uncertainty test reuses RQ3's Monte Carlo draws.

| Deliverable | From | Format |
| --- | --- | --- |
| Cleaned India extract + data dictionary + rules log | Pipeline | Parquet/CSV, markdown |
| Emerging-pattern watchlist (3 tiers, plain-language reasons) | RQ1 | Table + heatmap |
| Burden-only vs trend-aware comparison, overlooked-pairs list | RQ2 | Table |
| Stability labels and sensitivity summary | RQ3 | Table + rank-range plot |
| Existence table, consensus heatmap, PCA trajectories, cluster profiles | RQ4 | Figures + table |
| State explorer: pick a state and risk, compare with India and with cluster peers | All | Streamlit app |
| Reproducible repository with fixed seeds | All | Git |

**Main risks and fallbacks**

- **RQ4 finds no robust clusters** (likely, per the pilot) - report the gradient and the stable core as the answer; this is still a full result.
- **RQ2 novelty is mostly noise** - the materiality floor and the RQ1 "clear worsening" cross-check expose this; report it as a negative finding.
- **Over-interpreting causation** - every output carries the line "association in modelled estimates; not causal; not an intervention recommendation".
- **Proposal files S14A/S15A missing from this upload** - nothing in the plan depends on them; add them later only for global context.
