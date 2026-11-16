"""RQ1 - Which state x risk pairs worsened, and which diverged from India?

Three-tier watchlist on the Core set (31 units x 20 level-2 risks), using GBD's own
2010-23 % change interval; repeated on the Detail set to show what sits inside each
level-2 signal. Tiers are descriptive labels, not significance claims.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from riskshift import config as C  # noqa: E402
from riskshift.common import banner, load_features, load_india, load_sets, save_table, setup_plotting, short, subset  # noqa: E402
from riskshift.scoring import TIERS, tiers  # noqa: E402


def classify(f: pd.DataFrame, thr=C.DIVERGENCE_PP) -> pd.DataFrame:
    f = f.copy()
    f["tier"] = tiers(f.pct_2010_23_mean, f.pct_2010_23_lo, f.divergence_pct, thr)
    for t in C.DIVERGENCE_PP_ALT:
        f[f"tier_div{int(t)}"] = tiers(f.pct_2010_23_mean, f.pct_2010_23_lo, f.divergence_pct, t)
    f["reason"] = [reason(r) for r in f.itertuples()]
    return f


def reason(r) -> str:
    if r.tier == "None":
        return ""
    s = (f"ASR {r.asr_2010_mean:g} -> {r.asr_2023_mean:g} per 100k "
         f"({r.pct_2010_23_mean:+.1f}%, UI {r.pct_2010_23_lo:+.1f} to {r.pct_2010_23_hi:+.1f}; "
         f"{r.abs_2010_23:+.1f} absolute); India {r.india_pct_2010_23:+.1f}%")
    if r.tier == "Clear worsening":
        s = "Rose, interval wholly above zero: " + s
    elif r.tier == "Possible worsening":
        s = "Rose, but interval crosses zero: " + s
    else:
        s = f"Fell {r.divergence_pct:.0f} pp less than India: " + s
    if r.small_base:
        s += " [small base: 2010 ASR < 5]"
    if r.recent_reversal:
        s += " [recent reversal vs 1990-2023 direction]"
    return s


def heatmap(f, india, risks, plt, path):
    import matplotlib.colors as mcolors
    w = f.pivot_table(index="location", columns="risk", values="pct_2010_23_mean")
    t = f.pivot(index="location", columns="risk", values="tier")
    order = f.drop_duplicates("location").sort_values("block").location.tolist()
    w, t = w.loc[order, risks], t.loc[order, risks]
    ind = india.set_index("risk").loc[risks, "pct_2010_23_mean"]
    w = pd.concat([pd.DataFrame([ind.values], index=["INDIA"], columns=risks), w])
    fig, ax = plt.subplots(figsize=(12, 11))
    norm = mcolors.TwoSlopeNorm(vmin=-80, vcenter=0, vmax=80)
    im = ax.imshow(w.values.clip(-80, 80), cmap="RdBu_r", norm=norm, aspect="auto")
    mk = {"Clear worsening": ("o", "k", 34), "Possible worsening": ("o", "none", 30), "Adverse divergence": ("D", "none", 22)}
    for i, loc in enumerate(order, start=1):
        for j, r in enumerate(risks):
            tt = t.loc[loc, r]
            if tt in mk:
                m, fc, s = mk[tt]
                ax.scatter(j, i, marker=m, s=s, facecolors=fc, edgecolors="k", linewidths=0.9)
    ax.set_xticks(range(len(risks)), [short(r) for r in risks], rotation=60, ha="right")
    ax.set_yticks(range(len(w)), w.index)
    ax.get_yticklabels()[0].set_fontweight("bold")
    ax.axhline(0.5, color="k", lw=1)
    cb = fig.colorbar(im, ax=ax, shrink=0.5, pad=0.01)
    cb.set_label("% change in age-standardised death rate, 2010-23 (clipped at ±80)")
    for lbl, (m, fc, s) in mk.items():
        ax.scatter([], [], marker=m, s=s, facecolors=fc, edgecolors="k", label=lbl)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=3, frameon=False)
    ax.set_title("RQ1 - Change in risk-attributable death rate by state and level-2 risk, with watchlist tiers\n" + C.DISCLAIMER, fontsize=10)
    fig.savefig(path)
    plt.close(fig)


def dumbbells(f, india, risks, plt, path):
    wl = f[f.tier != "None"]
    use = [r for r in risks if (wl.risk == r).any()]
    ncol = 4
    nrow = int(np.ceil(len(use) / ncol))
    heights = [max(3, wl[wl.risk.isin(use[i * ncol:(i + 1) * ncol])].groupby("risk").size().max() * 0.28 + 1) for i in range(nrow)]
    fig, axes = plt.subplots(nrow, ncol, figsize=(17, sum(heights)), gridspec_kw={"height_ratios": heights})
    col = {"Clear worsening": "#b2182b", "Possible worsening": "#ef8a62", "Adverse divergence": "#7b3294"}
    ind = india.set_index("risk")
    for ax, r in zip(axes.flat, use):
        d = wl[wl.risk == r].sort_values("asr_2023_mean")
        y = np.arange(len(d))
        for yi, row in zip(y, d.itertuples()):
            ax.plot([row.asr_2010_mean, row.asr_2023_mean], [yi, yi], color=col[row.tier], lw=1.6)
            ax.scatter(row.asr_2010_mean, yi, color="white", edgecolor=col[row.tier], s=18, zorder=3)
            ax.scatter(row.asr_2023_mean, yi, color=col[row.tier], s=18, zorder=3)
        yi = len(d)
        ax.plot([ind.loc[r, "asr_2010_mean"], ind.loc[r, "asr_2023_mean"]], [yi, yi], color="k", lw=2)
        ax.scatter(ind.loc[r, "asr_2010_mean"], yi, color="white", edgecolor="k", s=22, zorder=3)
        ax.scatter(ind.loc[r, "asr_2023_mean"], yi, color="k", s=22, zorder=3)
        ax.set_yticks(list(y) + [yi], [l + (" *" if sb else "") for l, sb in zip(d.location, d.small_base)] + ["INDIA"], fontsize=7)
        ax.get_yticklabels()[-1].set_fontweight("bold")
        ax.set_title(short(r, 34), fontsize=9)
        ax.tick_params(axis="x", labelsize=7)
    for ax in list(axes.flat)[len(use):]:
        ax.axis("off")
    for lbl, c in col.items():
        axes.flat[0].plot([], [], color=c, lw=2, label=lbl)
    fig.legend(loc="upper center", ncol=3, frameon=False, bbox_to_anchor=(0.5, 1.0))
    fig.suptitle("RQ1 - Watchlist pairs: ASR 2010 (open) -> 2023 (filled) per 100,000 vs India  (* = small base)", y=1.015)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def main():
    banner("RQ1 watchlist")
    plt = setup_plotting()
    sets = load_sets()
    f_all, india = load_features(), load_india()

    core = classify(subset(f_all, sets["core"]))
    detail = classify(subset(f_all, sets["detail"]))
    cols = ["location", "zone", "is_aggregate", "risk", "tier", "asr_1990_mean", "asr_2010_mean", "asr_2023_mean",
            "abs_2010_23", "pct_2010_23_mean", "pct_2010_23_lo", "pct_2010_23_hi", "india_pct_2010_23",
            "divergence_pct", "small_base", "recent_reversal", "tier_div5", "tier_div15", "reason"]
    tier_order = {t: i for i, t in enumerate(TIERS)}
    for name, d in (("core", core), ("detail", detail)):
        out = d[cols].assign(_o=d.tier.map(tier_order)).sort_values(["_o", "abs_2010_23"], ascending=[True, False]).drop(columns="_o")
        save_table(out, f"rq1_tiers_{name}_all")
        save_table(out[out.tier != "None"], f"rq1_watchlist_{name}")

    # counts
    counts = core.groupby(["risk", "tier"]).size().unstack(fill_value=0).reindex(columns=TIERS, fill_value=0)
    counts.loc["TOTAL"] = counts.sum()
    save_table(counts.reset_index(), "rq1_tier_counts_by_risk")
    by_state = core.groupby(["location", "tier"]).size().unstack(fill_value=0).reindex(columns=TIERS, fill_value=0)
    save_table(by_state.sort_values("Clear worsening", ascending=False).reset_index(), "rq1_tier_counts_by_state")
    thr = pd.DataFrame({f"{t:g} pp": pd.Series(tiers(core.pct_2010_23_mean, core.pct_2010_23_lo, core.divergence_pct, t)).value_counts()
                        for t in [5, 10, 15]}).reindex(TIERS).fillna(0).astype(int)
    save_table(thr.reset_index(names="tier"), "rq1_divergence_threshold_sensitivity")

    # detail decomposition of each Core watchlist pair
    rows = []
    for r in core[core.tier != "None"].itertuples():
        kids = detail[(detail.location == r.location) & (detail.level2_risk == r.risk)]
        for k in kids.itertuples():
            rows.append(dict(location=r.location, level2_risk=r.risk, level2_tier=r.tier, level2_pct=r.pct_2010_23_mean,
                             detail_risk=k.risk, detail_tier=k.tier, detail_asr_2023=k.asr_2023_mean,
                             detail_pct=k.pct_2010_23_mean, detail_abs=k.abs_2010_23))
    decomp = pd.DataFrame(rows)
    save_table(decomp, "rq1_detail_decomposition")
    # national-level picture of what sits inside each level-2 signal
    ind = india.set_index("risk")
    nat = pd.DataFrame([dict(level2_risk=sets["level2_parent"][r], detail_risk=r, india_asr_2023=ind.loc[r, "asr_2023_mean"],
                             india_pct=ind.loc[r, "pct_2010_23_mean"], india_lo=ind.loc[r, "pct_2010_23_lo"],
                             india_hi=ind.loc[r, "pct_2010_23_hi"],
                             states_clear=int(((detail.risk == r) & (detail.tier == "Clear worsening")).sum()),
                             states_point_up=int(((detail.risk == r) & (detail.pct_2010_23_mean > 0)).sum()))
                        for r in sets["detail"]])
    save_table(nat, "rq1_detail_national")

    heatmap(core, india, sets["core"], plt, C.FIGURES / "rq1_heatmap_core.png")
    dumbbells(core, india, sets["core"], plt, C.FIGURES / "rq1_dumbbells_core.png")

    tc = core.tier.value_counts().to_dict()
    clear = core[core.tier == "Clear worsening"]
    summary = dict(
        n_pairs=len(core), tier_counts=tc, point_up=int(core.worse_point.sum()),
        clear_by_risk=clear.risk.value_counts().to_dict(),
        clear_small_base=int(clear.small_base.sum()),
        watchlist_small_base=int(core[core.tier != "None"].small_base.sum()),
        recent_reversal_in_watchlist=int(core[core.tier != "None"].recent_reversal.sum()),
        india_clearly_rising=india[(india.risk.isin(sets["core"])) & (india.pct_2010_23_lo > 0)][["risk", "pct_2010_23_mean", "pct_2010_23_lo", "pct_2010_23_hi"]].to_dict("records"),
        threshold_sensitivity=thr.to_dict(),
        detail_tier_counts=detail.tier.value_counts().to_dict(),
        detail_clear_by_risk=detail[detail.tier == "Clear worsening"].risk.value_counts().to_dict(),
        without_other_uts=core[~core.is_aggregate].tier.value_counts().to_dict(),
    )
    (C.OUT / "summary").mkdir(exist_ok=True)
    (C.OUT / "summary" / "rq1.json").write_text(json.dumps(summary, indent=2, default=float))
    print(f"  Core tiers: {tc}")
    print(f"  clear worsening by risk: {summary['clear_by_risk']}")
    print(f"  Detail tiers: {summary['detail_tier_counts']}")


if __name__ == "__main__":
    main()
