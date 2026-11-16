"""RQ3 - How stable are the cross-risk rankings?

Three perturbation families on the RQ2 cross-risk score (Core set, materiality floor):
  Weights      1,000 Dirichlet(1,1,1) weight vectors + corner cases
  Uncertainty  all-lower / all-upper bound scenarios + 1,000 Monte Carlo draws
               (2023 ASR ~ lognormal fitted to its 95% UI; 2010-23 % change ~ normal fitted to
               GBD's change interval; 2010 ASR implied, so the year-to-year correlation that
               GBD's change interval encodes is respected; cells drawn independently)
  Selection    leave-one-risk-out (20), Policy-salient set, without "Other Union Territories"
Stability label for each base top-N pair: Robust >= 80% of scenarios in top N, Moderate
50-80%, Fragile < 50% - per family, and overall = the weakest family label.
The Monte Carlo draws are saved for reuse by RQ4.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import kendalltau

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from riskshift import config as C  # noqa: E402
from riskshift.common import banner, load_features, load_india, load_sets, save_table, setup_plotting, short, subset  # noqa: E402
from riskshift.scoring import components_cross, rank_with_floor, tiers  # noqa: E402

LABELS = ["Robust", "Moderate", "Fragile"]


def label(freq):
    return np.where(freq >= C.ROBUST_FREQ, "Robust", np.where(freq >= C.MODERATE_FREQ, "Moderate", "Fragile"))


def rank_from(asr23, abs_ch, india_abs, w=None):
    r, wo, d = components_cross(asr23, abs_ch, india_abs)
    w = w or C.WEIGHTS
    s = w["rate"] * r + w["worsening"] * wo + w["divergence"] * d
    return rank_with_floor(s, asr23)


# ------------------------------------------------------------------ Monte Carlo draws
def lognormal_draws(rng, mean, lo, hi, n):
    m = np.log(np.clip(mean, C.LOG_FLOOR, None))
    sd = (np.log(np.clip(hi, C.LOG_FLOOR, None)) - np.log(np.clip(lo, C.LOG_FLOOR, None))) / (2 * 1.96)
    return np.exp(m + np.clip(sd, 0, None) * rng.standard_normal((n, len(mean))))


def pct_draws(rng, mean, lo, hi, n):
    sd = np.clip((np.asarray(hi) - np.asarray(lo)) / (2 * 1.96), 0, None)
    return np.clip(np.nan_to_num(mean) + np.nan_to_num(sd) * rng.standard_normal((n, len(mean))), -99.0, None)


def make_mc(f_union: pd.DataFrame, india: pd.DataFrame, rng) -> dict:
    n = C.N_MC_DRAWS
    a23 = lognormal_draws(rng, f_union.asr_2023_mean.values, f_union.asr_2023_lo.values, f_union.asr_2023_hi.values, n)
    pc = pct_draws(rng, f_union.pct_2010_23_mean.values, f_union.pct_2010_23_lo.values, f_union.pct_2010_23_hi.values, n)
    a10 = a23 / (1 + pc / 100)
    ia23 = lognormal_draws(rng, india.asr_2023_mean.values, india.asr_2023_lo.values, india.asr_2023_hi.values, n)
    ipc = pct_draws(rng, india.pct_2010_23_mean.values, india.pct_2010_23_lo.values, india.pct_2010_23_hi.values, n)
    ia10 = ia23 / (1 + ipc / 100)
    return dict(location=np.asarray(f_union.location, dtype=str), risk=np.asarray(f_union.risk, dtype=str),
                asr2023=a23.astype(np.float32), asr2010=a10.astype(np.float32), pct=pc.astype(np.float32),
                india_risk=np.asarray(india.risk, dtype=str), india_asr2023=ia23.astype(np.float32),
                india_asr2010=ia10.astype(np.float32), india_pct=ipc.astype(np.float32))


# ------------------------------------------------------------------ families
def family_weights(f, rng):
    comps = np.vstack(components_cross(f.asr_2023_mean, f.abs_2010_23, f.india_abs_2010_23))
    W = rng.dirichlet([1, 1, 1], size=C.N_WEIGHT_DRAWS)
    corners = np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1], [0, .5, .5], [1 / 3, 1 / 3, 1 / 3]])
    names = [f"dirichlet_{i}" for i in range(len(W))] + ["rate_only", "worsening_only", "divergence_only", "trend_only", "equal"]
    W = np.vstack([W, corners])
    scores = W @ comps
    ranks = np.vstack([rank_with_floor(s, f.asr_2023_mean) for s in scores]).astype(float)
    return names, ranks


def family_uncertainty(f, mc, keys):
    idx = pd.Series(range(len(mc["location"])), index=pd.MultiIndex.from_arrays([mc["location"], mc["risk"]]))
    sel = idx.loc[list(keys)].values
    iidx = pd.Series(range(len(mc["india_risk"])), index=mc["india_risk"]).loc[f.risk].values
    names, ranks = [], []
    for b in ("lo", "hi"):
        a23, a10 = f[f"asr_2023_{b}"].values, f[f"asr_2010_{b}"].values
        names.append(f"all_{b}_bounds")
        ranks.append(rank_from(a23, a23 - a10, f[f"india_abs_{b}"].values))
    for i in range(C.N_MC_DRAWS):
        a23, a10 = mc["asr2023"][i, sel].astype(float), mc["asr2010"][i, sel].astype(float)
        ia = (mc["india_asr2023"][i, iidx] - mc["india_asr2010"][i, iidx]).astype(float)
        names.append(f"mc_{i}")
        ranks.append(rank_from(a23, a23 - a10, ia))
    return names, np.vstack(ranks).astype(float)


def family_selection(f, f_full, sets, keys):
    names, ranks = [], []
    pos = pd.Series(range(len(keys)), index=pd.MultiIndex.from_tuples(keys))

    def place(d):
        out = np.full(len(keys), np.nan)
        r = rank_from(d.asr_2023_mean.values, d.abs_2010_23.values, d.india_abs_2010_23.values)
        k = list(zip(d.location, d.risk))
        present = [i for i, kk in enumerate(k) if kk in pos.index]
        out[pos.loc[[k[i] for i in present]].values] = r[present]
        return out

    for r in sets["core"]:
        names.append(f"drop_{r}")
        ranks.append(place(f[f.risk != r]))
    names.append("policy_salient_set")
    ranks.append(place(subset(f_full, sets["policy"])))
    names.append("without_other_uts")
    ranks.append(place(f[~f.is_aggregate]))
    return names, np.vstack(ranks)


# ------------------------------------------------------------------ main
def main():
    banner("RQ3 stability")
    plt = setup_plotting()
    rng = np.random.default_rng(C.SEED)
    rng_w, rng_mc = rng.spawn(2)
    sets = load_sets()
    f_full, india = load_features(), load_india()
    f = subset(f_full, sets["core"]).reset_index(drop=True)
    ind = india.set_index("risk")
    for b in ("lo", "hi"):
        f[f"india_abs_{b}"] = f.risk.map(ind[f"asr_2023_{b}"] - ind[f"asr_2010_{b}"])
    keys = list(zip(f.location, f.risk))
    base = rank_from(f.asr_2023_mean.values, f.abs_2010_23.values, f.india_abs_2010_23.values)

    union = sorted(set(sets["core"]) | set(sets["detail"]) | set(sets["policy"]))
    fu = subset(f_full, union).reset_index(drop=True)
    iu = india[india.risk.isin(union)].reset_index(drop=True)
    mc = make_mc(fu, iu, rng_mc)
    np.savez_compressed(C.MC_DRAWS, **mc)
    print(f"  saved {C.N_MC_DRAWS} Monte Carlo draws for {len(fu)} state x risk cells -> {C.MC_DRAWS.relative_to(C.ROOT)}")

    fams = {"Weights": family_weights(f, rng_w),
            "Uncertainty": family_uncertainty(f, mc, keys),
            "Selection": family_selection(f, f_full, sets, keys)}

    out = f[["location", "risk"]].copy()
    out["base_rank"] = base
    kt_rows = []
    for fam, (names, R) in fams.items():
        for n in C.TOP_NS:
            present = ~np.isnan(R)
            out[f"{fam}_freq_top{n}"] = np.where(present.sum(0) > 0, ((R <= n) & present).sum(0) / present.sum(0), np.nan)
        out[f"{fam}_median_rank"] = np.nanmedian(R, axis=0)
        out[f"{fam}_rank_p05"] = np.nanpercentile(R, 5, axis=0)
        out[f"{fam}_rank_p95"] = np.nanpercentile(R, 95, axis=0)
        taus = []
        for nm, r in zip(names, R):
            m = ~np.isnan(r)
            taus.append(kendalltau(base[m], r[m]).statistic)
        taus = np.array(taus)
        kt_rows.append(dict(family=fam, scenarios=len(names), kendall_median=np.median(taus),
                            kendall_p05=np.percentile(taus, 5), kendall_min=taus.min()))
        if fam == "Selection":
            kt_rows[-1]["kendall_by_scenario"] = dict(zip(names, np.round(taus, 3)))
    labels_out = []
    for n in C.TOP_NS:
        top = out[out.base_rank <= n].copy()
        for fam in fams:
            top[f"{fam}_label"] = label(top[f"{fam}_freq_top{n}"].values)
        top["overall_label"] = top[[f"{fam}_label" for fam in fams]].apply(lambda r: max(r, key=LABELS.index), axis=1)
        top["N"] = n
        labels_out.append(top)
    lab = pd.concat(labels_out)
    lab = lab.merge(f[["location", "risk", "asr_2023_mean", "abs_2010_23", "pct_2010_23_mean", "small_base"]], on=["location", "risk"])
    lab["tier"] = lab.merge(f.assign(tier=tiers(f.pct_2010_23_mean, f.pct_2010_23_lo, f.divergence_pct))[["location", "risk", "tier"]],
                            on=["location", "risk"])["tier"].values
    save_table(lab.sort_values(["N", "base_rank"]), "rq3_stability_labels")
    save_table(out.sort_values("base_rank"), "rq3_rank_distributions")
    kt = pd.DataFrame(kt_rows)
    save_table(kt.drop(columns="kendall_by_scenario", errors="ignore"), "rq3_kendall_summary")

    # sensitivity summary table: label counts per family and N
    summ = []
    for n in C.TOP_NS:
        t = lab[lab.N == n]
        for col in [f"{fam}_label" for fam in fams] + ["overall_label"]:
            vc = t[col].value_counts()
            summ.append(dict(N=n, family=col.replace("_label", ""), **{k: int(vc.get(k, 0)) for k in LABELS}))
    summ = pd.DataFrame(summ)
    save_table(summ, "rq3_sensitivity_summary")

    # RQ1 tier flips
    tier_base = tiers(f.pct_2010_23_mean, f.pct_2010_23_lo, f.divergence_pct)
    flips = []
    for t in C.DIVERGENCE_PP_ALT:
        tt = tiers(f.pct_2010_23_mean, f.pct_2010_23_lo, f.divergence_pct, t)
        flips.append(dict(perturbation=f"divergence threshold {t:g} pp", share_flipped=float((tt != tier_base).mean()), n_flipped=int((tt != tier_base).sum())))
    for b in ("lo", "hi"):   # point estimate replaced by a bound (interval-based 'clear' unchanged)
        ip = f.risk.map(ind[f"pct_2010_23_{b}"])
        tt = tiers(f[f"pct_2010_23_{b}"], f.pct_2010_23_lo, f[f"pct_2010_23_{b}"] - ip)
        flips.append(dict(perturbation=f"point change at {b} bound", share_flipped=float((tt != tier_base).mean()), n_flipped=int((tt != tier_base).sum())))
    idx = pd.Series(range(len(mc["location"])), index=pd.MultiIndex.from_arrays([mc["location"], mc["risk"]])).loc[keys].values
    iidx = pd.Series(range(len(mc["india_risk"])), index=mc["india_risk"]).loc[f.risk].values
    flip_counts = np.zeros(len(f))
    for i in range(C.N_MC_DRAWS):
        p, ip = mc["pct"][i, idx].astype(float), mc["india_pct"][i, iidx].astype(float)
        tt = tiers(p, f.pct_2010_23_lo, p - ip)
        flip_counts += tt != tier_base
    fs = flip_counts / C.N_MC_DRAWS
    flips.append(dict(perturbation="Monte Carlo (mean share of draws)", share_flipped=float(fs.mean()), n_flipped=int((fs > 0.5).sum())))
    wl = tier_base != "None"
    flips.append(dict(perturbation="Monte Carlo, watchlist pairs only (mean share)", share_flipped=float(fs[wl].mean()), n_flipped=int((fs[wl] > 0.5).sum())))
    for tname in ["Clear worsening", "Possible worsening", "Adverse divergence"]:
        m = tier_base == tname
        flips.append(dict(perturbation=f"Monte Carlo, base tier = {tname} (mean share)", share_flipped=float(fs[m].mean()), n_flipped=int((fs[m] > 0.5).sum())))
    flips = pd.DataFrame(flips)
    save_table(flips, "rq3_tier_flips")

    # Detail-set ranking (what a finer-grained list would surface; not counted in Core labels)
    fd = subset(f_full, sets["detail"]).reset_index(drop=True)
    fd["rank_cross"] = rank_from(fd.asr_2023_mean.values, fd.abs_2010_23.values, fd.india_abs_2010_23.values)
    save_table(fd.sort_values("rank_cross").head(30)[["rank_cross", "location", "risk", "level2_risk", "asr_2023_mean", "abs_2010_23", "pct_2010_23_mean"]], "rq3_detail_set_top30")

    # rank-range plot
    top = out[out.base_rank <= C.PRIMARY_N].sort_values("base_rank")
    l20 = lab[lab.N == C.PRIMARY_N].set_index(["location", "risk"])
    fig, ax = plt.subplots(figsize=(10, 8))
    colors = {"Weights": "#1b9e77", "Uncertainty": "#d95f02", "Selection": "#7570b3"}
    for j, fam in enumerate(fams):
        y = np.arange(len(top)) + (j - 1) * 0.25
        ax.hlines(y, top[f"{fam}_rank_p05"], top[f"{fam}_rank_p95"], color=colors[fam], lw=2, label=f"{fam} (5-95% range)")
        ax.scatter(top[f"{fam}_median_rank"], y, color=colors[fam], s=14, zorder=3)
    ax.scatter(top.base_rank, np.arange(len(top)), marker="|", color="k", s=120, zorder=4, label="base rank")
    ax.axvline(C.PRIMARY_N + 0.5, color="k", ls=":", lw=0.8)
    ax.set_yticks(range(len(top)), [f"{r.location} · {short(r.risk, 22)}  [{l20.loc[(r.location, r.risk), 'overall_label']}]" for r in top.itertuples()], fontsize=7)
    ax.invert_yaxis()
    ax.set_xscale("log")
    ax.set_xlabel("Rank under perturbation (log scale; dotted = top-20 cut-off)")
    ax.set_title("RQ3 - Rank ranges of the base top-20 cross-risk pairs, by perturbation family")
    ax.legend(fontsize=7, loc="lower right")
    fig.text(0.01, -0.02, C.DISCLAIMER, fontsize=7, color="0.4")
    fig.savefig(C.FIGURES / "rq3_rank_ranges.png")
    plt.close(fig)

    summary = dict(
        sensitivity_summary=summ.to_dict("records"), kendall=kt.to_dict("records"),
        tier_flips=flips.to_dict("records"),
        top20=l20.reset_index()[["location", "risk", "base_rank", "Weights_label", "Uncertainty_label", "Selection_label", "overall_label",
                                  "Weights_freq_top20", "Uncertainty_freq_top20", "Selection_freq_top20"]].to_dict("records"),
    )
    (C.OUT / "summary" / "rq3.json").write_text(json.dumps(summary, indent=2, default=float))
    print(summ[summ.N == C.PRIMARY_N].to_string(index=False))
    print(kt.drop(columns="kendall_by_scenario", errors="ignore").to_string(index=False))
    print(flips.to_string(index=False))


if __name__ == "__main__":
    main()
