# Data dictionary

Source: GBD 2023 *Diseases, Injuries and Risk Factors*, appendix table **S14B — Global and location-specific risk factor deaths** (`S14B_Global_and_Location_Specific_Risk_Factor_Deaths.XLSX`). It has 595,020 data rows: 705 location blocks × 844 rows (88 risk "All causes" rows and 756 risk → cause rows).

## Files produced by the pipeline

| File | Step | Grain | Notes |
| --- | --- | --- | --- |
| `data/interim/s14b_india_extract.csv` | 01_extract | 27,008 rows = 32 blocks × 844 | Text values exactly as published. Checked cell by cell against the supplied pilot extract (identical). |
| `data/reference/risk_hierarchy.csv` | 02_annotate | 88 risks | Level 0–4, parent, level-1 and level-2 ancestor, and where each level came from. |
| `data/interim/s14b_india_annotated.parquet` | 02_annotate | 26,720 rows | Numbers parsed; 4 no-mortality risks dropped; geography tags added. |
| `data/processed/risk_sets.json` | 03_sets | — | Core / Detail / Policy-salient members, the rules that define them, and the excluded risks. |
| `data/processed/features_state_risk.parquet` (+ `.csv`) | 04_features | 2,604 rows = 31 state units × 84 risks | Analysis table, one row per state × risk. |
| `data/processed/features_india_risk.parquet` (+ `.csv`) | 04_features | 84 rows | The same measures for India (the national benchmark). |
| `data/processed/mc_draws.npz` | rq3_stability | 1,000 draws × 1,457 cells | Monte Carlo datasets, reused by RQ4. |
| `data/processed/rq4_*.pkl` | rq4_* | — | Intermediate clustering objects (regenerable). |

## Columns in `features_state_risk`

| Column | Meaning | Units |
| --- | --- | --- |
| `block` | Position of the location block in S14B. This is the location key; names are never used to join. | integer (354–384) |
| `location` | State unit name as published | — |
| `zone` | Government of India Zonal Council (external geography label for RQ4) | — |
| `is_aggregate` | True for "Other Union Territories", which is an aggregate of several UTs | bool |
| `sdi_group` | SDI group from GBD Appendix 1 Table S12. **Empty, because that table was not in the upload.** | — |
| `risk`, `risk_level`, `parent_risk`, `level2_risk`, `order` | Risk name, hierarchy level, parent, level-2 ancestor, and published order | — |
| `asr_{1990,2010,2023}_{mean,lo,hi}` | Age-standardised risk-attributable death rate, with its 95% uncertainty interval | per 100,000 |
| `deaths_2023_{mean,lo,hi}`, `deaths_2010_mean` | Risk-attributable deaths (all ages) | count |
| `paf_2023_{mean,lo,hi}` | Population attributable fraction of all deaths | % |
| `pct_2010_23_{mean,lo,hi}` | GBD's % change in ASR from 2010 to 2023, with GBD's own interval | % |
| `abs_2010_23` | ASR 2023 − ASR 2010 | per 100,000 |
| `abs_1990_2010`, `abs_1990_2023`, `pct_1990_2023` | Long-horizon changes, computed from the means. No interval is published, so they are used only to check direction. | per 100,000 / % |
| `india_asr_2010`, `india_asr_2023`, `india_pct_2010_23`, `india_abs_2010_23` | India's values for the same risk | — |
| `divergence_pct` | State % change − India % change | percentage points |
| `divergence_abs` | State absolute change − India absolute change | per 100,000 |
| `worse_point` | `pct_2010_23_mean > 0` | bool |
| `worse_clear` | `pct_2010_23_lo > 0` (the whole interval is above zero) | bool |
| `small_base` | `asr_2010_mean < 5` | bool |
| `dir_1990_2010`, `dir_1990_2023`, `dir_2010_2023` | Sign of each change (−1, 0, +1) | — |
| `recent_reversal` | The 2010–23 direction is the opposite of the 1990–2023 direction | bool |
| `neg_lower_bound` | At least one lower bound for deaths, PAF or ASR is negative (the risk could be protective or harmful) | bool |

## Risk sets

* **Core**: the 20 level-2 risks.
* **Detail**: 27 risks. These are the level-3 risks with ASR ≥ 0.5 in every state unit in both 2010 and 2023. Particulate matter pollution is replaced by its two components, ambient PM and household air pollution. Twelve level-3 risks are excluded; `risk_sets.json` lists them.
* **Policy-salient**: 10 risks. The rule is the 8 risks with the highest national 2023 ASR from the non-overlapping pool, plus every pool risk whose national interval is wholly above zero and whose national ASR is at least 10. The result is ambient PM, household air pollution, ozone, lead, smoking, high fasting plasma glucose, LDL, systolic blood pressure, BMI and kidney dysfunction.
