"""RQ2 - Does trend-aware prioritisation surface different cases?

Baselines   B1 = 2023 attributable deaths, B2 = 2023 ASR.
Candidate   priority = 0.40 x rate + 0.35 x worsening + 0.25 x divergence, scored two ways:
  within-risk  min-max per risk (as proposed) - for per-risk state rankings only
  cross-risk   percentiles across all pairs of log ASR, absolute ASR change and absolute
               change gap vs India, with a materiality floor (2023 ASR >= 10) for top N.
Measures at N = 10/20/30: Jaccard overlap, Spearman/Kendall, newly surfaced pairs and the
share of them that are RQ1 "clear worsening" (novelty should come from real change).
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import kendalltau, spearmanr

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from riskshift import config as C  # noqa: E402
from riskshift.common import banner, load_features, load_sets, save_table, setup_plotting, short, subset  # noqa: E402
from riskshift.scoring import components_cross, rank_with_floor, score_within, tiers  # noqa: E402


def score_core(f: pd.DataFrame) -> pd.DataFrame:
    f = f.reset_index(drop=True).copy()
    f["tier"] = tiers(f.pct_2010_23_mean, f.pct_2010_23_lo, f.divergence_pct)
    f["rank_B1_deaths"] = f.deaths_2023_mean.rank(ascending=False, method="first").astype(int)
    f["rank_B2_asr"] = f.asr_2023_mean.rank(ascending=False, method="first").astype(int)
    r, w, d = components_cross(f.asr_2023_mean, f.abs_2010_23, f.india_abs_2010_23)
    f["x_rate"], f["x_worsening"], f["x_divergence"] = r, w, d
    W = C.WEIGHTS
    f["score_cross"] = W["rate"] * r + W["worsening"] * w + W["divergence"] * d
    f["rank_cross"] = rank_with_floor(f.score_cross, f.asr_2023_mean)
    f["above_floor"] = f.asr_2023_mean >= C.MATERIALITY_ASR
    wi = score_within(f)
    f["w_rate"], f["w_worsening"], f["w_divergence"] = wi.c_rate, wi.c_worsening, wi.c_divergence
    f["score_within"] = wi.score
    f["rank_within"] = f.score_within.rank(ascending=False, method="first").astype(int)
    f["rank_within_in_risk"] = f.groupby("risk").score_within.rank(ascending=False, method="first").astype(int)
    return f


def why(r) -> str:
    parts = []
    comps = [("rate", r.x_rate, f"ASR {r.asr_2023_mean:g}"),
             ("worsening", r.x_worsening, f"{r.abs_2010_23:+.1f}/100k since 2010"),
             ("divergence", r.x_divergence, f"{r.divergence_abs:+.1f}/100k vs India's change")]
    for name, p, txt in sorted(comps, key=lambda c: -c[1]):
        if p >= 0.80:
            parts.append(f"{name} p{int(round(100 * p))} ({txt})")
    return "; ".join(parts) if parts else "balanced moderate signals"


def compare(f: pd.DataFrame, cand_rank: str, cand_score: str, label: str) -> list[dict]:
    rows = []
    for n in C.TOP_NS:
        top_c = set(f.index[f[cand_rank] <= n])
        tb1 = set(f.index[f.rank_B1_deaths <= n])
        tb2 = set(f.index[f.rank_B2_asr <= n])
        new = top_c - tb1 - tb2
        nf = f.loc[sorted(new)]
        rows.append(dict(
            variant=label, N=n,
            jaccard_B1=len(top_c & tb1) / len(top_c | tb1), jaccard_B2=len(top_c & tb2) / len(top_c | tb2),
            overlap_B1=len(top_c & tb1), overlap_B2=len(top_c & tb2),
            n_new=len(new),
            new_clear=int((nf.tier == "Clear worsening").sum()),
            new_possible=int((nf.tier == "Possible worsening").sum()),
            new_divergence=int((nf.tier == "Adverse divergence").sum()),
            new_small_base=int(nf.small_base.sum()),
            new_below_floor=int((~nf.above_floor).sum()),
            new_clear_material=int(((nf.tier == "Clear worsening") & nf.above_floor & ~nf.small_base).sum()),
            share_new_clear=(nf.tier == "Clear worsening").mean() if len(nf) else np.nan,
            n_distinct_risks_top=f.loc[sorted(top_c), "risk"].nunique(),
        ))
    for b, col in (("B1", "deaths_2023_mean"), ("B2", "asr_2023_mean")):
        rows[0][f"spearman_{b}"] = spearmanr(f[cand_score], f[col]).statistic
        rows[0][f"kendall_{b}"] = kendalltau(f[cand_score], f[col]).statistic
        el = f.above_floor
        rows[0][f"spearman_{b}_eligible"] = spearmanr(f.loc[el, cand_score], f.loc[el, col]).statistic
    for r in rows[1:]:
        for k in [k for k in rows[0] if k.startswith(("spearman", "kendall"))]:
            r[k] = rows[0][k]
    return rows


def figure(f, plt, path):
    fig, axes = plt.subplots(1, 2, figsize=(15, 6.5))
    ax = axes[0]
    top_c = f.rank_cross <= C.PRIMARY_N
    top_b = (f.rank_B1_deaths <= C.PRIMARY_N) | (f.rank_B2_asr <= C.PRIMARY_N)
    ax.scatter(f.asr_2023_mean, f.abs_2010_23, s=10, c="0.8", label="all pairs")
    ax.scatter(f.loc[top_b & ~top_c, "asr_2023_mean"], f.loc[top_b & ~top_c, "abs_2010_23"], s=30, c="#4575b4", label="burden top 20 only")
    ax.scatter(f.loc[top_b & top_c, "asr_2023_mean"], f.loc[top_b & top_c, "abs_2010_23"], s=40, c="#1a9850", label="both")
    ax.scatter(f.loc[top_c & ~top_b, "asr_2023_mean"], f.loc[top_c & ~top_b, "abs_2010_23"], s=40, c="#d73027", label="trend-aware top 20 only (new)")
    for r in f[top_c & ~top_b].itertuples():
        ax.annotate(f"{r.location[:12]} · {short(r.risk, 18)}", (r.asr_2023_mean, r.abs_2010_23), fontsize=6, xytext=(3, 2), textcoords="offset points")
    ax.axvline(C.MATERIALITY_ASR, color="k", ls=":", lw=0.8)
    ax.axhline(0, color="k", lw=0.5)
    ax.set_xscale("log")
    ax.set_xlabel("2023 ASR per 100,000 (log)  - dotted line = materiality floor")
    ax.set_ylabel("Absolute ASR change 2010-23 per 100,000")
    ax.set_title("Cross-risk trend-aware top 20 vs burden-only top 20 (B1 deaths ∪ B2 rate)")
    ax.legend(fontsize=7, loc="lower right")
    ax = axes[1]
    top_w = f.rank_within <= C.PRIMARY_N
    ax.scatter(f.asr_2023_mean, f.pct_2010_23_mean, s=10, c="0.8")
    ax.scatter(f.loc[top_w, "asr_2023_mean"], f.loc[top_w, "pct_2010_23_mean"], s=40, c=np.where(f.loc[top_w, "small_base"], "#fdae61", "#d73027"))
    for r in f[top_w].itertuples():
        ax.annotate(f"{r.location[:12]} · {short(r.risk, 18)}", (r.asr_2023_mean, r.pct_2010_23_mean), fontsize=6, xytext=(3, 2), textcoords="offset points")
    ax.set_xscale("log")
    ax.axvline(C.MATERIALITY_ASR, color="k", ls=":", lw=0.8)
    ax.set_xlabel("2023 ASR per 100,000 (log)")
    ax.set_ylabel("% change 2010-23")
    ax.set_title("Within-risk (min-max) top 20 as proposed - orange = small base")
    fig.text(0.01, -0.02, C.DISCLAIMER, fontsize=7, color="0.4")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def main():
    banner("RQ2 prioritisation")
    plt = setup_plotting()
    sets = load_sets()
    res = {}
    for tag, inc in (("all", True), ("no_other_uts", False)):
        f = score_core(subset(load_features(include_aggregate=inc), sets["core"]))
        comp = pd.DataFrame(compare(f, "rank_within", "score_within", "within-risk (proposed)") +
                            compare(f, "rank_cross", "score_cross", "cross-risk + floor"))
        save_table(comp, f"rq2_comparison_{tag}")
        res[tag] = (f, comp)
    f, comp = res["all"]

    cols = ["location", "risk", "tier", "asr_2023_mean", "deaths_2023_mean", "abs_2010_23", "pct_2010_23_mean",
            "divergence_abs", "small_base", "above_floor", "x_rate", "x_worsening", "x_divergence", "score_cross",
            "rank_cross", "score_within", "rank_within", "rank_B1_deaths", "rank_B2_asr"]
    save_table(f.sort_values("rank_cross")[cols], "rq2_scores_core")
    # overlooked pairs: in trend-aware top N, absent from both burden top N
    over = []
    for n in C.TOP_NS:
        m = (f.rank_cross <= n) & (f.rank_B1_deaths > n) & (f.rank_B2_asr > n)
        d = f[m].sort_values("rank_cross").assign(N=n)
        d["why_surfaced"] = [why(r) for r in d.itertuples()]
        over.append(d)
    over = pd.concat(over)
    save_table(over[["N"] + cols[:10] + ["rank_cross", "rank_B1_deaths", "rank_B2_asr", "why_surfaced"]], "rq2_overlooked_pairs")
    # side-by-side top 20 lists
    side = pd.DataFrame({
        "rank": range(1, 31),
        "B1_deaths": [f"{r.location} · {r.risk}" for r in f.sort_values("rank_B1_deaths").head(30).itertuples()],
        "B2_asr": [f"{r.location} · {r.risk}" for r in f.sort_values("rank_B2_asr").head(30).itertuples()],
        "cross_risk": [f"{r.location} · {r.risk}" for r in f.sort_values("rank_cross").head(30).itertuples()],
        "within_risk": [f"{r.location} · {r.risk}" for r in f.sort_values("rank_within").head(30).itertuples()],
    })
    save_table(side, "rq2_top30_side_by_side")
    per_risk = f.sort_values(["risk", "rank_within_in_risk"])[["risk", "rank_within_in_risk", "location", "score_within", "asr_2023_mean", "pct_2010_23_mean", "divergence_pct", "tier"]]
    save_table(per_risk, "rq2_within_risk_state_rankings")
    figure(f, plt, C.FIGURES / "rq2_burden_vs_trend.png")

    c20 = comp[(comp.N == 20)].set_index("variant")
    cross20 = c20.loc["cross-risk + floor"]
    success = int(cross20.new_clear_material) >= C.SUCCESS_MIN_NEW
    summary = dict(
        comparison_N20=c20.reset_index().to_dict("records"),
        success_criterion=dict(rule=f">= {C.SUCCESS_MIN_NEW} new pairs in the cross-risk top 20 that are clear-worsening, "
                               f"above the floor, not small-base, and absent from both baselines",
                               new_clear_material=int(cross20.new_clear_material), met=bool(success)),
        overlooked_N20=over[over.N == 20][["location", "risk", "tier", "asr_2023_mean", "abs_2010_23", "why_surfaced"]].to_dict("records"),
        within_top20_small_base=int(f[f.rank_within <= 20].small_base.sum()),
        within_top20_below_floor=int((~f[f.rank_within <= 20].above_floor).sum()),
        no_other_uts_N20=res["no_other_uts"][1].query("N == 20").to_dict("records"),
    )
    (C.OUT / "summary" / "rq2.json").write_text(json.dumps(summary, indent=2, default=float))
    print(comp[["variant", "N", "overlap_B1", "overlap_B2", "n_new", "new_clear", "new_clear_material", "new_small_base", "new_below_floor"]].to_string(index=False))
    print(f"  success criterion met: {success} ({int(cross20.new_clear_material)} qualifying new pairs in top 20)")


if __name__ == "__main__":
    main()
