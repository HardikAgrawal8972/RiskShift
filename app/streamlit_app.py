"""RiskShift-India state explorer.

Pick a state and a risk; compare its age-standardised death rate with India and with its
cluster peers, and see its RQ1 tier, RQ2 priority rank and RQ3 stability label.
Run:  streamlit run app/streamlit_app.py
"""
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from riskshift import config as C  # noqa: E402
from riskshift.common import load_features, load_india, load_sets  # noqa: E402
from riskshift.scoring import tiers  # noqa: E402

st.set_page_config(page_title="RiskShift-India explorer", layout="wide")


@st.cache_data
def data():
    f, india, sets = load_features(), load_india(), load_sets()
    f["tier"] = tiers(f.pct_2010_23_mean, f.pct_2010_23_lo, f.divergence_pct)
    scores = pd.read_csv(C.TABLES / "rq2_scores_core.csv")
    stab = pd.read_csv(C.TABLES / "rq3_stability_labels.csv")
    peers = pd.read_csv(C.TABLES / "rq4_peer_benchmark.csv")
    desc = pd.read_csv(C.TABLES / "rq4_cluster_descriptions.csv")
    return f, india, sets, scores, stab, peers, desc


f, india, sets, scores, stab, peers, desc = data()
st.title("RiskShift-India — state × risk explorer")
st.caption(C.DISCLAIMER + " Source: GBD 2023 (S14B), risk-attributable deaths.")

c1, c2, c3 = st.columns([2, 2, 1])
set_name = c3.selectbox("Risk set", ["core", "detail", "policy"], format_func=lambda s: {"core": "Core (20 level-2)", "detail": "Detail (level-3)", "policy": "Policy-salient"}[s])
states = f.drop_duplicates("location").sort_values("location").location.tolist()
state = c1.selectbox("State unit", states, index=states.index("Uttar Pradesh"))
risk = c2.selectbox("Risk factor", sets[set_name])

row = f[(f.location == state) & (f.risk == risk)].iloc[0]
ind = india.set_index("risk").loc[risk]
cluster = peers.loc[peers.location == state, "cluster"].iloc[0]
peer_states = peers[peers.cluster == cluster].location.unique().tolist()
peer_rows = f[(f.location.isin(peer_states)) & (f.risk == risk)]

m1, m2, m3, m4 = st.columns(4)
m1.metric("ASR 2023 per 100k", f"{row.asr_2023_mean:g}", f"{row.abs_2010_23:+.1f} since 2010", delta_color="inverse")
m2.metric("% change 2010-23", f"{row.pct_2010_23_mean:+.1f}%", f"India {ind.pct_2010_23_mean:+.1f}%", delta_color="off")
m3.metric("RQ1 tier", row.tier)
sc = scores[(scores.location == state) & (scores.risk == risk)]
if len(sc):
    s = sc.iloc[0]
    lab = stab[(stab.N == C.PRIMARY_N) & (stab.location == state) & (stab.risk == risk)]
    m4.metric("RQ2 cross-risk rank (of 620)", int(s.rank_cross), lab.overall_label.iloc[0] + " in top 20" if len(lab) else "not in base top 20", delta_color="off")
else:
    m4.metric("RQ2 rank", "Core set only")

st.write(f"95% UI for the 2010-23 change: {row.pct_2010_23_lo:+.1f}% to {row.pct_2010_23_hi:+.1f}%."
         + (" **Small base** (2010 ASR < 5)." if row.small_base else "")
         + (" **Recent reversal** against the 1990-2023 direction." if row.recent_reversal else ""))

left, right = st.columns(2)
yrs = [1990, 2010, 2023]
fig = go.Figure()
fig.add_scatter(x=yrs, y=[row[f"asr_{y}_mean"] for y in yrs], name=state, mode="lines+markers",
                error_y=dict(type="data", symmetric=False, array=[row[f"asr_{y}_hi"] - row[f"asr_{y}_mean"] for y in yrs],
                             arrayminus=[row[f"asr_{y}_mean"] - row[f"asr_{y}_lo"] for y in yrs]))
fig.add_scatter(x=yrs, y=[ind[f"asr_{y}_mean"] for y in yrs], name="India", mode="lines+markers", line=dict(dash="dash"))
fig.add_scatter(x=yrs, y=[peer_rows[f"asr_{y}_mean"].median() for y in yrs], name=f"Cluster {cluster} peers (median)", mode="lines+markers", line=dict(dash="dot"))
if C.BENCH_FEATURES.exists():
    bench = pd.read_parquet(C.BENCH_FEATURES)
    for name, dash in (("Global", "longdash"), ("South Asia", "dashdot")):
        bb = bench[(bench.bench == name) & (bench.risk == risk)]
        if len(bb):
            fig.add_scatter(x=yrs, y=[bb.iloc[0][f"asr_{y}_mean"] for y in yrs], name=name, mode="lines+markers", line=dict(dash=dash))
fig.update_layout(title=f"{risk}: age-standardised death rate per 100,000", yaxis_title="ASR per 100,000", height=420)
left.plotly_chart(fig, width="stretch")

allr = f[f.risk == risk].sort_values("asr_2023_mean")
bar = go.Figure(go.Bar(x=allr.asr_2023_mean, y=allr.location, orientation="h",
                       marker_color=["#d73027" if l == state else ("#fdae61" if l in peer_states else "#bbbbbb") for l in allr.location]))
bar.add_vline(x=ind.asr_2023_mean, line_dash="dash", annotation_text="India")
bar.update_layout(title="2023 ASR across state units (orange = cluster peers)", height=620, margin=dict(l=10))
right.plotly_chart(bar, width="stretch")

st.subheader(f"{state}: profile across the {set_name} set")
prof = f[(f.location == state) & (f.risk.isin(sets[set_name]))][["risk", "asr_2010_mean", "asr_2023_mean", "abs_2010_23", "pct_2010_23_mean",
                                                                 "pct_2010_23_lo", "pct_2010_23_hi", "india_pct_2010_23", "divergence_pct", "tier"]]
st.dataframe(prof.sort_values("asr_2023_mean", ascending=False).round(1), width="stretch", hide_index=True)

d3 = desc[desc.k == 3]
st.subheader("Tentative risk-profile clusters (k = 3, Core level features)")
st.caption("RQ4 found weak structure: treat these as a descriptive grouping on a gradient, not robust clusters. See docs/RESULTS.md.")
st.dataframe(d3[["cluster", "n", "description", "states"]], width="stretch", hide_index=True)
