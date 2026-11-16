# RiskShift-India

This project screens Indian state × risk-factor pairs using GBD 2023 risk-attributable deaths (S14B). It asks whether a ranking that accounts for trends and uncertainty surfaces different, defensible priorities than a ranking by burden alone. It is a screening tool, not a forecast and not a causal study.

**Results: [docs/RESULTS.md](docs/RESULTS.md)**. Methods: [docs/rules_log.md](docs/rules_log.md). Data: [docs/data_dictionary.md](docs/data_dictionary.md). Plan: `RiskShift-India Project Explainer and Implementation Plan.md`.

## Run

```bash
python -m venv .venv
```
```bash
.venv/Scripts/python -m pip install -r requirements.txt
```
```bash
.venv/Scripts/python run_all.py
```
```bash
.venv/Scripts/python -m streamlit run app/streamlit_app.py
```

`run_all.py` streams the raw S14B workbook (about 20 s) and runs every step with fixed seeds, in about 5 minutes. Pass `--reuse` to skip re-extraction.

## Layout

| Path | What |
| --- | --- |
| `riskshift/config.py` | Every threshold, weight and seed, fixed before analysis |
| `riskshift/common.py`, `scoring.py`, `clustering.py` | Shared helpers, RQ1/RQ2 scoring rules, RQ4 algorithms |
| `src/01_extract.py` … `04_features.py` | Shared pipeline: extract → annotate → risk sets → features |
| `src/rq1_watchlist.py` | RQ1: three-tier watchlist of worsening and diverging pairs |
| `src/rq2_prioritise.py` | RQ2: burden-only vs trend-aware rankings, with an overlooked-pairs list |
| `src/rq3_stability.py` | RQ3: weight, uncertainty and selection stress tests, with stability labels |
| `src/rq4_*.py` | RQ4: feature grid, clustering grid, null test, stability, migration, figures |
| `src/make_report.py` | Builds `docs/RESULTS.md` from the outputs |
| `app/streamlit_app.py` | State explorer |
| `outputs/tables`, `outputs/figures`, `outputs/summary` | Results |
| `data/reference/risk_hierarchy.csv` | Frozen risk hierarchy |

Every output carries this note: *association in modelled estimates; not causal; not an intervention recommendation.*
