"""06_causes - which diseases drive each worsening pair? (uses S14B's risk -> cause rows)

For every Core pair in the RQ1 watchlist that rose (clear or possible worsening), and for
India's rising risks, break the 2010-23 change in the age-standardised rate into the causes
of death listed under that risk. Level-2 risks such as "Other environmental risks" have no
cause rows of their own; their causes are taken from their child risks (summed by cause,
flagged as 'via child risks', approximate because child risks can overlap). Aggregate cause
rows ("Total cancers", "Total burden related to ...") are dropped to avoid double counting.
"""
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from riskshift import config as C  # noqa: E402
from riskshift.common import banner, load_features, load_sets, save_table, setup_plotting, short  # noqa: E402
from riskshift.scoring import tiers  # noqa: E402


def cause_rows(ann, hier, location, risk):
    rows = ann[(ann.location == location) & (ann.risk == risk) & ann.is_outcome]
    # "Total cancers", "Total burden related to ..." are aggregates of other listed causes
    rows = rows[~rows.outcome.str.startswith("Total")]
    if len(rows):
        return rows, "direct"
    kids = hier.loc[hier.parent_risk == risk, "risk"].tolist()
    parts = [cause_rows(ann, hier, location, k)[0] for k in kids]
    parts = [p for p in parts if len(p)]
    if not parts:
        return rows, "none"
    agg = pd.concat(parts).groupby("outcome", as_index=False)[["asr_2010_mean", "asr_2023_mean"]].sum()
    return agg, "via child risks"


def breakdown(ann, hier, location, risk):
    rows, src = cause_rows(ann, hier, location, risk)
    if not len(rows):
        return pd.DataFrame(), src
    d = rows[["outcome", "asr_2010_mean", "asr_2023_mean"]].copy()
    d["abs_change"] = d.asr_2023_mean - d.asr_2010_mean
    up = d.abs_change.clip(lower=0).sum()
    d["share_of_rise"] = d.abs_change.clip(lower=0) / up if up > 0 else 0
    return d.sort_values("abs_change", ascending=False), src


def main():
    banner("06_causes")
    plt = setup_plotting()
    ann = pd.read_parquet(C.ANNOTATED)
    hier = pd.read_csv(C.REFERENCE / "risk_hierarchy.csv")
    sets = load_sets()
    f = load_features()
    core = f[f.risk.isin(sets["core"])].copy()
    core["tier"] = tiers(core.pct_2010_23_mean, core.pct_2010_23_lo, core.divergence_pct)
    targets = core[core.tier.isin(["Clear worsening", "Possible worsening"])]
    ind = ann[(ann.geo == "national") & ~ann.is_outcome & ann.risk.isin(sets["core"]) & (ann.pct_asr_2010_23_mean > 0)]

    long, summ = [], []
    actual = {(r.location, r.risk): r.abs_2010_23 for r in targets.itertuples()}
    actual.update({("India", r.risk): r.asr_2023_mean - r.asr_2010_mean for r in ind.itertuples()})
    jobs = [(r.location, r.risk, r.tier) for r in targets.itertuples()] + [("India", r, "India rising") for r in ind.risk]
    for loc, risk, tier in jobs:
        d, src = breakdown(ann, hier, loc, risk)
        if d.empty:
            continue
        d.insert(0, "location", loc); d.insert(1, "risk", risk); d.insert(2, "tier", tier); d["source"] = src
        long.append(d)
        top = d[d.abs_change > 0].head(3)
        summ.append(dict(location=loc, risk=risk, tier=tier, source=src,
                         total_abs_change=round(float(actual[(loc, risk)]), 1),   # the risk's own change, not the cause sum
                         main_causes="; ".join(f"{o} ({c:+.1f}/100k, {s:.0%} of the rise)" for o, c, s in zip(top.outcome, top.abs_change, top.share_of_rise)),
                         top_cause=top.outcome.iloc[0] if len(top) else "", top_cause_share=float(top.share_of_rise.iloc[0]) if len(top) else 0.0))
    long = pd.concat(long)
    summ = pd.DataFrame(summ)
    save_table(long, "causes_breakdown_long")
    save_table(summ.sort_values(["tier", "total_abs_change"], ascending=[True, False]), "causes_summary")

    # figure: top 12 clear-worsening pairs by absolute change, stacked by cause
    cl = summ[summ.tier == "Clear worsening"].nlargest(12, "total_abs_change")
    top_causes = (long[long.tier == "Clear worsening"].groupby("outcome").abs_change.apply(lambda s: s.clip(lower=0).sum())
                  .sort_values(ascending=False).head(6).index.tolist())
    palette = ["#1b9e77", "#d95f02", "#7570b3", "#e7298a", "#66a61e", "#e6ab02", "#bbbbbb"]
    fig, ax = plt.subplots(figsize=(11, 6.5))
    for i, r in enumerate(cl.itertuples()):
        d = long[(long.location == r.location) & (long.risk == r.risk)]
        left = 0.0
        for k, cause in enumerate(top_causes + ["Other causes"]):
            # cause shares of the rise, scaled to the risk's own change (cause sums can overlap)
            sh = d[d.outcome == cause].share_of_rise.sum() if cause != "Other causes" else d[~d.outcome.isin(top_causes)].share_of_rise.sum()
            v = sh * r.total_abs_change
            ax.barh(i, v, left=left, color=palette[k], label=cause if i == 0 else None)
            left += v
    ax.set_yticks(range(len(cl)), [f"{r.location} · {short(r.risk, 26)}" for r in cl.itertuples()])
    ax.invert_yaxis()
    ax.set_xlabel("Increase in the risk's age-standardised death rate 2010-23, per 100,000, split by each cause's share of the rise")
    ax.set_title("Which causes of death drive the largest clear increases?\n" + C.DISCLAIMER, fontsize=10)
    ax.legend(fontsize=8, loc="lower right")
    fig.savefig(C.FIGURES / "causes_clear_worsening.png")
    plt.close(fig)

    clear = summ[summ.tier == "Clear worsening"]
    summary = dict(
        n_pairs=len(summ), n_clear=len(clear),
        top_cause_counts_clear=clear.top_cause.value_counts().to_dict(),
        india=summ[summ.location == "India"][["risk", "main_causes"]].to_dict("records"),
        clear_top=clear.nlargest(10, "total_abs_change")[["location", "risk", "main_causes", "source"]].to_dict("records"),
    )
    (C.OUT / "summary" / "causes.json").write_text(json.dumps(summary, indent=2, default=float))
    print(f"  broke down {len(summ)} pairs ({len(clear)} clear worsening)")
    print("  top cause among clear-worsening pairs:", summary["top_cause_counts_clear"])
    for r in summary["india"]:
        print(f"  India · {r['risk']}: {r['main_causes']}")


if __name__ == "__main__":
    main()
