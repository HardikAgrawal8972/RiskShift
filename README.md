# RiskShift-India

**Which health risks are getting worse in Indian states, and would a simple "most deaths" ranking miss them?**

This project looks at deaths linked to 20 health risk factors (high blood pressure, air pollution, high blood sugar, tobacco and so on) in 31 Indian state units, using data from the **Global Burden of Disease (GBD) 2023** study. It finds the risks that are getting worse, ranks them in a smarter way, tests how much those rankings can be trusted, and checks whether states fall into natural groups.

> 📄 **Read the results here: [docs/RESULTS.md](docs/RESULTS.md)**. It is a plain-language report with all charts and comparisons.

*Everything here is based on modelled estimates. It shows associations, not cause and effect, and it is not advice on where to spend money.*

---

## Contents

1. [The main findings](#1-the-main-findings)
2. [The four questions](#2-the-four-questions)
3. [The data](#3-the-data)
4. [How it works, step by step](#4-how-it-works-step-by-step)
5. [How to run it](#5-how-to-run-it)
6. [Every file explained](#6-every-file-explained)
7. [Key words](#7-key-words)
8. [Limits](#8-limits)

---

## 1. The main findings

| | Finding |
| --- | --- |
| 📈 | Of 620 state × risk combinations, **185 got worse** from 2010 to 2023. **41 are clearly worse** even after allowing for uncertainty. Most of these are **high BMI and high blood sugar**. |
| 🩺 | **Type 2 diabetes** is the main cause of death behind 27 of those 41 clear increases. |
| 🌍 | India is moving **against the world trend**: its death rates for high BMI (+37%), high blood sugar (+27%) and physical inactivity (+10%) rose, while the world's barely moved or fell. |
| 🔀 | Ranking by "current burden + how fast it is worsening" puts **11 new cases** in the top 20 that a "most deaths" or "highest rate" list misses. These are mainly blood pressure and diet in Bihar, Chhattisgarh, Karnataka, Haryana and Assam. |
| ⚖️ | The new ranking barely changes when the scoring weights change, but GBD's own uncertainty moves it more. **3 of the top 20 are robust**, 13 moderate and 4 fragile. |
| 🧩 | States **do not form clear groups**. They sit on a spectrum. A few small sets of states do consistently look alike. |
| ⏳ | Between 1990 and 2023, most states shifted from **malnutrition, unsafe water and air pollution** to **metabolic risks** such as blood sugar and cholesterol. |

---

## 2. The four questions

| # | Question | How we answer it | Code |
| --- | --- | --- | --- |
| **Q1** | Which state × risk pairs got worse, or fell behind India? | Compare the 2010 and 2023 death rates. Use GBD's uncertainty range to sort each pair into: **clear worsening**, **possible worsening**, or **falling behind India**. | `src/rq1_watchlist.py` |
| **Q2** | Does a trend-aware ranking find different cases from a burden-only ranking? | Compare three top-20 lists: most deaths, highest rate, and our score (40% current rate + 35% rise + 25% gap vs India). Count the new cases. | `src/rq2_prioritise.py` |
| **Q3** | How much can we trust the ranking? | Re-run it thousands of times with different weights, values redrawn within GBD's uncertainty, and different risk lists. Label each top case **Robust / Moderate / Fragile**. | `src/rq3_stability.py` |
| **Q4** | Do states fall into clear groups? | Try 24 clustering set-ups and compare each with random "no-group" data. Check whether groups survive resampling. Also track how profiles shifted from 1990 to 2023. | `src/rq4_*.py` |

There are two extra analyses, which compare **India with the world and South Asia** (`src/05_benchmarks.py`) and show **which diseases drive each increase** (`src/06_causes.py`).

---

## 3. The data

| File | What it is |
| --- | --- |
| `S14B_Global_and_Location_Specific_Risk_Factor_Deaths.XLSX` | **The main data** (118 MB, about 595,000 rows). It covers 705 places × 844 rows each: deaths, death rates and the share of deaths linked to each risk, for 1990, 2010 and 2023, each with a low and high estimate. **It is not on GitHub because it is too big (GitHub's limit is 100 MB).** Put it in the main folder to re-run the extraction. |
| `RiskShift_India_S14B_extract.csv` | An earlier extract of just India + 31 states (27,008 rows). The code checks its own extract against this one, and they match exactly. It also stands in for the big file if that file is missing. |
| `RiskShift_India_GBD_Research_Review_and_Project_Proposal.pdf` | The original project proposal (problem, research questions, method ideas). |
| `RiskShift-India Project Explainer and Implementation Plan.md` | The detailed plan this code follows. |

**What we use from S14B:** India (block 353), its 31 state units (blocks 354–384), and as comparisons the **World** (block 0) and **South Asia** (block 350). Places are always picked by position, never by name, because "Punjab" exists in both India and Pakistan.

**Which risks:** GBD arranges risks in a tree with 5 levels. We mainly use the **20 broad "level-2" risks**, which do not overlap with each other. We also use 27 more detailed risks and a 10-risk policy-focused list. Deaths from different risks overlap, so we never add them together.

---

## 4. How it works, step by step

`run_all.py` runs these scripts in order:

```
 S14B.xlsx
    │
 01_extract ──► pull India + 31 states + World + South Asia out of the big file
 02_annotate ─► turn text into numbers, add the risk tree, tag regions
 03_sets ─────► choose the three risk lists (broad / detailed / policy)
 04_features ─► one clean table: one row per state × risk, with all the measures
 05_benchmarks► compare India and states with the World and South Asia
 06_causes ───► split each increase into causes of death (e.g. diabetes, heart disease)
    │
 rq1_watchlist ► Q1: which pairs got worse
 rq2_prioritise► Q2: compare the three rankings
 rq3_stability ► Q3: stress-test the ranking
 rq4_features ─► Q4: build 24 feature set-ups
 rq4_cluster_grid ► cluster each set-up (4 methods, 2–6 groups)
 rq4_null ─────► compare with random "no-group" data
 rq4_stability ► resampling, uncertainty and leave-one-out tests, final verdict
 rq4_migration ► how state profiles moved 1990 → 2010 → 2023
 rq4_figures ──► group profiles, maps of states, peer comparison
    │
 make_report ──► writes docs/RESULTS.md from all the results
```

Every random step uses the same fixed seed (`20261116`), so every run gives the same numbers.

---

## 5. How to run it

You need Python 3.12. Run these commands from the project folder.

**1. Create a virtual environment**

```bash
python -m venv .venv
```

**2. Install the packages**

```bash
.venv/Scripts/python -m pip install -r requirements.txt
```

(On Mac or Linux, use `.venv/bin/python` instead of `.venv/Scripts/python`.)

**3. Run the whole analysis.** This takes about 5–10 minutes.

```bash
.venv/Scripts/python run_all.py
```

Add `--reuse` to skip re-reading the big XLSX if the extract already exists.

**4. Open the interactive explorer**

```bash
.venv/Scripts/python -m streamlit run app/streamlit_app.py
```

The explorer opens in your browser. Pick any state and risk to see:
- its death rate in 1990, 2010 and 2023, compared with India, similar states, South Asia and the world
- its Q1 group, Q2 rank and Q3 stability label
- how it compares with every other state

---

## 6. Every file explained

### Top level

| File | What it does |
| --- | --- |
| `README.md` | This file. |
| `run_all.py` | Runs every step in order. It is the one command that rebuilds everything. |
| `requirements.txt` | The Python packages needed, with exact versions. |
| `.gitignore` | Files kept out of GitHub: the big XLSX, the virtual environment, and temporary files that can be rebuilt. |

### `riskshift/`: shared code used by all the scripts

| File | What it does |
| --- | --- |
| `config.py` | **Every setting in one place**: file paths, block positions, thresholds (for example "falling behind India" means 10 percentage points), scoring weights (40/35/25), the minimum death rate for ranking (10 per 100,000), the number of random runs, and the random seed. |
| `common.py` | Small helpers: load data, save tables, turn text into numbers, set chart style, shorten long risk names. |
| `scoring.py` | The rules for the Q1 groups and the Q2 scores, kept in one place so Q3 reuses exactly the same rules. |
| `clustering.py` | The Q4 tools: building features, the four clustering methods, choosing the number of groups, random comparison data, and resampling stability. |
| `__init__.py` | Marks the folder as a Python package. |

### `src/`: the analysis steps (run in this order)

| File | What it does | Main outputs |
| --- | --- | --- |
| `01_extract.py` | Reads the 950 MB sheet inside the XLSX, keeps India, the 31 states, the World and South Asia, and checks the result against the earlier extract. | `data/interim/*.csv` |
| `02_annotate.py` | Converts text to numbers ("-" means missing, not zero). Adds each risk's level and parent in the risk tree. Marks "Other Union Territories" as a combined unit. Drops 4 risks that have no death estimates for India. | `data/interim/*.parquet`, `data/reference/risk_hierarchy.csv` |
| `03_sets.py` | Picks the three risk lists using fixed written rules. | `data/processed/risk_sets.json` |
| `04_features.py` | Builds the main table: rates, changes, India's change, gap vs India, and warning flags such as "small base". | `data/processed/features_*.parquet/.csv` |
| `05_benchmarks.py` | India and states compared with the World and South Asia. | `bench_*` tables, `bench_india_vs_world.png` |
| `06_causes.py` | For each rising pair, which causes of death the increase comes from. | `causes_*` tables, `causes_clear_worsening.png` |
| `rq1_watchlist.py` | **Q1.** Sorts every pair into a group and writes a one-line reason for each. | `rq1_*` tables, heatmap and dumbbell charts |
| `rq2_prioritise.py` | **Q2.** Builds the three rankings, compares them, and lists the new cases with reasons. | `rq2_*` tables, `rq2_burden_vs_trend.png` |
| `rq3_stability.py` | **Q3.** Runs about 2,000 re-rankings and labels each top case. Saves the random draws for Q4. | `rq3_*` tables, `rq3_rank_ranges.png` |
| `rq4_features.py` | **Q4.** Builds the 24 set-ups (3 risk lists × 4 feature types × 2 scalings). | `rq4_feature_configs.csv` |
| `rq4_cluster_grid.py` | Clusters every set-up with K-means, Ward, average linkage and Gaussian mixture, for 2 to 6 groups, and picks the best number of groups. | `rq4_cluster_grid_indices.csv`, `rq4_k_selection.csv` |
| `rq4_null.py` | Makes 1,000 random "no-group" datasets per set-up and checks whether the real data group better. | `rq4_existence_null_test.csv` |
| `rq4_stability.py` | Tests whether groups survive resampling, uncertainty and dropping one risk. Builds the "how often are two states together" matrix and gives the final verdict. | `rq4_decision_table.csv`, `rq4_consensus_*`, `rq4_cross_config_*` |
| `rq4_migration.py` | Tracks each state's risk profile from 1990 to 2023. | `rq4_migration_*` tables, charts and Sankey diagrams |
| `rq4_figures.py` | Group profiles, a map of states, comparison with regions, and peer comparison. | `rq4_*` charts, `rq4_cluster_descriptions.csv`, `rq4_peer_benchmark.csv` |
| `make_report.py` | Writes `docs/RESULTS.md` from all the results. No numbers are typed in by hand. | `docs/RESULTS.md` |

### `app/`

| File | What it does |
| --- | --- |
| `streamlit_app.py` | The interactive explorer (see [How to run it](#5-how-to-run-it)). |

### `docs/`

| File | What it is |
| --- | --- |
| `RESULTS.md` | **The final report**, in plain language with all charts and tables. |
| `rules_log.md` | Every decision and threshold, and why. Use it as the methods section. |
| `data_dictionary.md` | What every data file and column means. |

### `data/`

| File | What it is |
| --- | --- |
| `reference/risk_hierarchy.csv` | The GBD risk tree: 88 risks, their level (0–4) and their parent. |
| `processed/features_state_risk.csv` / `.parquet` | **The main analysis table**: 31 states × 84 risks. It has death rates for 1990, 2010 and 2023 (with ranges), deaths, % change, India's change and the gap vs India. |
| `processed/features_india_risk.csv` / `.parquet` | The same measures for India as a whole. |
| `processed/features_benchmarks.parquet` | The same measures for the World and South Asia. |
| `processed/risk_sets.json` | The three risk lists and the rules that made them. |
| `interim/` *(not on GitHub)* | Raw extracts. They are rebuilt by `01_extract.py`. |

### `outputs/figures/`: charts (all used in the report)

| File | Shows |
| --- | --- |
| `bench_india_vs_world.png` | India vs South Asia vs the world, 2010 → 2023, for each risk. |
| `causes_clear_worsening.png` | Which diseases drive the biggest increases. |
| `rq1_heatmap_core.png` | Map of change for every state × risk, with the Q1 groups marked. |
| `rq1_dumbbells_core.png` | 2010 vs 2023 rates for every watchlist pair, next to India. |
| `rq2_burden_vs_trend.png` | Which cases each ranking puts on top. |
| `rq3_rank_ranges.png` | How far each top-20 case moves under each test. |
| `rq4_existence_*.png` | Real grouping vs random data. |
| `rq4_consensus_*.png` | How often each pair of states ends up in the same group. |
| `rq4_cross_config_ari.png` | How much the 24 clustering set-ups agree. |
| `rq4_cluster_profiles.png` | The average risk profile of each group. |
| `rq4_pca_biplot.png` | A 2-D map of states by risk profile. |
| `rq4_migration_shape.png` / `_level.png` | Each state's path from 1990 to 2023. |
| `rq4_migration_*_sankey.html` | Interactive flow of states between profiles (open in a browser). |

`*_all31` means all 31 state units. `*_no_other_uts30` means the same analysis without the combined "Other Union Territories" unit.

### `outputs/tables/`: all result tables (CSV, opens in Excel)

| Files starting with | What they contain |
| --- | --- |
| `bench_` | India and states vs the World and South Asia, ratios to the world rate, and states rising while the world falls. |
| `causes_` | Cause-of-death breakdown for every rising pair (`causes_summary.csv` is the short version). |
| `rq1_` | Q1 group for every pair (`_all`), only flagged pairs (`watchlist_`), counts by risk and by state, detailed-risk breakdown, and cut-off sensitivity. |
| `rq2_` | All scores, the side-by-side top-30 lists, new cases with reasons, comparison measures, and state rankings within each risk. |
| `rq3_` | Stability labels, rank ranges, label counts per test, rank correlations, and how often Q1 groups change. |
| `rq4_` | Feature set-ups, clustering scores, number of groups chosen, the random-data test, the decision table, agreement matrices, group descriptions, region comparison, peer comparison, and migration paths. |

### `outputs/summary/`

Small JSON files (`rq1.json`, `rq2.json`, `bench.json`, …) holding the key numbers from each step. `make_report.py` reads them to write the report.

---

## 7. Key words

| Word | Meaning |
| --- | --- |
| **GBD** | Global Burden of Disease, a worldwide study that estimates deaths and illness by cause and risk. |
| **Risk factor** | Something that raises the chance of dying early, such as high blood pressure, smoking or dirty air. |
| **Attributable deaths** | Deaths that GBD's models link to a risk factor. They are estimates, not counted death certificates. |
| **Death rate (ASR)** | Deaths per 100,000 people, *age-standardised*: adjusted so states with older or younger populations can be compared fairly. |
| **Uncertainty range** | GBD's low and high estimates (95%). A "clear" rise means even the low estimate shows a rise. |
| **pp** | Percentage points, the difference between two percentages. |
| **Clustering** | A method that puts similar items into groups automatically. |
| **Robust / Moderate / Fragile** | Stays in the top 20 in at least 80% / 50–80% / under 50% of the re-runs. |

---

## 8. Limits

- These are **modelled estimates**, and there are only three years (1990, 2010, 2023). This is a snapshot comparison, not a forecast.
- Deaths from different risks **overlap**, so they are never added up.
- It shows **associations only**, not causes.
- "Other Union Territories" combines several small territories. Every result was re-checked without it, and the conclusions held.
- Two optional GBD files were not available: the socio-demographic index groups and the evidence-strength ratings. India's Zonal Councils were used as the outside comparison instead.
