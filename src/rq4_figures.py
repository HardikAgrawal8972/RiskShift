"""RQ4 figures, interpretation (4c) and external checks (4d).

Primary configuration for interpretation: Core set, F1 level (log ASR 2023), z-scored,
K-means - the set-up closest to the feasibility pilot. Profiles are shown at the pilot's
k = 3 hypothesis and at the configuration's own chosen k.
"""
import json
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import chi2_contingency, kruskal
from sklearn.decomposition import PCA
from sklearn.metrics import adjusted_rand_score as ARI

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from riskshift import config as C  # noqa: E402
from riskshift.clustering import _scale  # noqa: E402
from riskshift.common import banner, load_features, load_sets, save_table, setup_plotting, short, subset  # noqa: E402
from riskshift.scoring import tiers  # noqa: E402

PRIMARY = ("all31", "core-F1-z")
PILOT_GROUPS = {   # tentative k = 3 groups reported in the feasibility pilot
    "a": ["Arunachal Pradesh", "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Sikkim", "Tripura",
          "Himachal Pradesh", "Jammu & Kashmir and Ladakh", "Rajasthan"],
    "b": ["Andhra Pradesh", "Telangana", "Karnataka", "Chhattisgarh", "Uttarakhand"],
}


def describe(Zdf, lab, c, n=3):
    inn = Zdf[lab == c].mean()
    out = Zdf[lab != c].mean()
    d = (inn - out).sort_values(key=np.abs, ascending=False).head(n)
    parts = [f"{'high' if v > 0 else 'low'} {short(r, 30).lower()}" for r, v in d.items()]
    return ", ".join(parts), d.to_dict()


def name_groups(lab, states):
    """Stable cluster ids ordered by size (largest = A)."""
    sizes = pd.Series(lab).value_counts()
    m = {c: chr(65 + i) for i, c in enumerate(sizes.index)}
    return np.array([m[c] for c in lab])


def main():
    banner("RQ4 figures & interpretation")
    plt = setup_plotting()
    import matplotlib.patches as patches
    grid = pickle.loads((C.PROCESSED / "rq4_grid.pkl").read_bytes())
    stab = pickle.loads((C.PROCESSED / "rq4_stability.pkl").read_bytes())
    ex = pd.read_csv(C.TABLES / "rq4_existence_null_test.csv")
    dec = pd.read_csv(C.TABLES / "rq4_decision_table.csv")
    sets = load_sets()
    f = load_features()
    summary = {}

    # ---------------- 1. existence plot
    for u in ("all31", "no_other_uts30"):
        e = ex[ex.units == u].reset_index(drop=True)
        fig, ax = plt.subplots(figsize=(12, 4.8))
        x = np.arange(len(e))
        ax.vlines(x, e.null_mvn_median, e.null_mvn_p95, color="0.6", lw=6, alpha=0.6, label="null (MVN): median to 95th pct")
        ax.scatter(x, e.null_shuffle_p95, marker="_", s=120, color="#7570b3", label="null (column-shuffled) 95th pct")
        ax.scatter(x, e.observed_best_sil, color=np.where(e.gate1_existence, "#1a9850", "#d73027"), s=30, zorder=3, label="observed best silhouette")
        ax.axhline(C.SIL_MIN, color="k", ls=":", lw=0.8)
        ax.text(len(e) - 0.5, C.SIL_MIN + 0.005, "0.25", fontsize=7, ha="right")
        ax.set_xticks(x, e.config, rotation=60, ha="right", fontsize=7)
        ax.set_ylabel("Silhouette (best over k = 2..6)")
        ax.set_title(f"RQ4 4a - Observed clustering vs null data with no clusters ({u}); green = passes gate 1")
        ax.legend(fontsize=7, loc="upper left")
        fig.savefig(C.FIGURES / f"rq4_existence_{u}.png")
        plt.close(fig)

    # ---------------- 2. cross-config ARI heatmap
    A = pd.read_csv(C.TABLES / "rq4_cross_config_ari_all31.csv", index_col=0)
    fig, ax = plt.subplots(figsize=(9, 8))
    im = ax.imshow(A.values, cmap="viridis", vmin=-0.1, vmax=1)
    ax.set_xticks(range(len(A)), A.columns, rotation=75, fontsize=6.5)
    ax.set_yticks(range(len(A)), A.index, fontsize=6.5)
    off = A.values[~np.eye(len(A), dtype=bool)]
    ax.set_title(f"RQ4 4b - Agreement between feature configurations (ARI, K-means at chosen k)\nmedian off-diagonal ARI = {np.median(off):.2f}")
    fig.colorbar(im, ax=ax, shrink=0.7)
    fig.savefig(C.FIGURES / "rq4_cross_config_ari.png")
    plt.close(fig)

    # ---------------- 3. consensus heatmap
    for u, cons in stab["consensus"].items():
        M, states, order = cons["M"], cons["states"], cons["order"]
        Mo = M[np.ix_(order, order)]
        so = [states[i] for i in order]
        fig, ax = plt.subplots(figsize=(10, 9))
        im = ax.imshow(Mo, cmap="Blues", vmin=0, vmax=1)
        lbl = [s + ("  (floater)" if s in cons["floaters"] else "") for s in so]
        ax.set_xticks(range(len(so)), so, rotation=75, fontsize=6.5)
        ax.set_yticks(range(len(so)), lbl, fontsize=6.5)
        for c in cons["cores"]:
            idx = sorted(so.index(s) for s in c["states"])
            if idx == list(range(idx[0], idx[-1] + 1)):
                ax.add_patch(patches.Rectangle((idx[0] - .5, idx[0] - .5), len(idx), len(idx), fill=False, ec="#d73027", lw=1.5))
        fig.colorbar(im, ax=ax, shrink=0.7, label="share of runs in which the two states share a cluster")
        ax.set_title(f"RQ4 4b - Consensus matrix ({u}); red boxes = stable cores (co-assignment >= {C.CORE_COASSIGN})")
        fig.savefig(C.FIGURES / f"rq4_consensus_{u}.png")
        plt.close(fig)

    # ---------------- 4. profiles for the primary configuration
    g = grid[PRIMARY]
    states = g["states"]
    m = pickle.loads((C.PROCESSED / "rq4_inputs.pkl").read_bytes())["all31"]["core"]
    Z = _scale(np.log(np.clip(m["asr2023"], C.LOG_FLOOR, None)), "z")
    Zdf = pd.DataFrame(Z, index=states, columns=m["risks"])
    prof = {}
    k_star = g["k_star"]
    for k in sorted({3, k_star}):
        lab = name_groups(g["labels"][("kmeans", k)], states)
        prof[k] = lab
    fig, axes = plt.subplots(1, len(prof), figsize=(7 * len(prof), 6.5), squeeze=False)
    descs = {}
    for ax, (k, lab) in zip(axes[0], prof.items()):
        cl = sorted(set(lab))
        H = pd.DataFrame({c: Zdf[lab == c].mean() for c in cl}).T
        im = ax.imshow(H.values, cmap="RdBu_r", vmin=-1.6, vmax=1.6, aspect="auto")
        ax.set_xticks(range(H.shape[1]), [short(r, 24) for r in H.columns], rotation=70, ha="right", fontsize=7)
        ax.set_yticks(range(len(cl)), [f"{c} (n={int((lab == c).sum())})" for c in cl])
        for i, c in enumerate(cl):
            for j in range(H.shape[1]):
                ax.text(j, i, f"{H.iloc[i, j]:.1f}", ha="center", va="center", fontsize=5.5)
        ax.set_title(f"k = {k}" + (" (chosen k)" if k == k_star else " (pilot hypothesis)"))
        descs[k] = {c: dict(states=list(np.array(states)[lab == c]), description=describe(Zdf, lab, c)[0]) for c in cl}
    fig.colorbar(im, ax=axes[0].tolist(), shrink=0.6, label="cluster mean z-score of log ASR 2023")
    fig.suptitle("RQ4 4c - Cluster profiles, primary configuration (Core, level, z-score, K-means)")
    fig.savefig(C.FIGURES / "rq4_cluster_profiles.png")
    plt.close(fig)
    rows = [dict(k=k, cluster=c, n=len(d["states"]), description=d["description"], states="; ".join(d["states"]))
            for k, dd in descs.items() for c, d in dd.items()]
    save_table(pd.DataFrame(rows), "rq4_cluster_descriptions")
    summary["profiles"] = descs
    # pilot reproduction
    pilot = np.array(["a" if s in PILOT_GROUPS["a"] else "b" if s in PILOT_GROUPS["b"] else "c" for s in states])
    summary["ari_vs_pilot_k3_groups"] = float(ARI(pilot, prof[3]))

    # ---------------- 5. PCA biplot
    p = PCA().fit(Z)
    S = p.transform(Z)
    L = pd.DataFrame(p.components_[:2].T, index=m["risks"], columns=["PC1", "PC2"])
    fig, ax = plt.subplots(figsize=(10, 8))
    lab = prof[3]
    cols = {"A": "#1b9e77", "B": "#d95f02", "C": "#7570b3", "D": "#e7298a", "E": "#66a61e", "F": "#e6ab02"}
    for c in sorted(set(lab)):
        mm = lab == c
        ax.scatter(S[mm, 0], S[mm, 1], color=cols[c], s=30, label=f"cluster {c} (k=3)")
    for i, s in enumerate(states):
        ax.annotate(s[:16], (S[i, 0], S[i, 1]), fontsize=6.5, xytext=(2, 2), textcoords="offset points")
    sc = np.abs(S[:, :2]).max() * 0.9
    for r in L.index:
        ax.arrow(0, 0, L.loc[r, "PC1"] * sc, L.loc[r, "PC2"] * sc, color="0.45", lw=0.6, head_width=0.08)
        ax.text(L.loc[r, "PC1"] * sc * 1.07, L.loc[r, "PC2"] * sc * 1.07, short(r, 20), fontsize=6, color="0.3")
    ax.set_xlabel(f"PC1 ({p.explained_variance_ratio_[0]:.0%} of variance)")
    ax.set_ylabel(f"PC2 ({p.explained_variance_ratio_[1]:.0%})")
    ax.axhline(0, color="0.85", lw=0.5); ax.axvline(0, color="0.85", lw=0.5)
    ax.set_title("RQ4 4c - PCA biplot of state risk profiles (Core, log ASR 2023, z-scored)")
    ax.legend(fontsize=7)
    fig.text(0.01, -0.02, C.DISCLAIMER, fontsize=7, color="0.4")
    fig.savefig(C.FIGURES / "rq4_pca_biplot.png")
    plt.close(fig)
    save_table(L.assign(PC1_var=p.explained_variance_ratio_[0], PC2_var=p.explained_variance_ratio_[1]).reset_index(names="risk"), "rq4_pca_loadings_core_F1")
    summary["pca"] = dict(var=p.explained_variance_ratio_[:3].tolist(),
                          corr_pc1_mean_level=float(np.corrcoef(S[:, 0], Z.mean(1))[0, 1]),
                          pc1=L.PC1.sort_values().round(2).to_dict(), pc2=L.PC2.sort_values().round(2).to_dict())

    # ---------------- 6. external labels: Zonal Councils (SDI not supplied)
    zone = np.array([C.ZONE[s] for s in states])
    ct = pd.crosstab(pd.Series(prof[3], name="cluster (k=3)"), pd.Series(zone, name="zone"))
    save_table(ct.reset_index(), "rq4_cluster_by_zone_primary")
    zrows = []
    for u in ("all31", "no_other_uts30"):
        for (uu, cid), gg in grid.items():
            if uu != u:
                continue
            z = np.array([C.ZONE[s] for s in gg["states"]])
            zrows.append(dict(units=u, config=cid, k_star=gg["k_star"], ari_vs_zone_kstar=ARI(z, gg["labels"][("kmeans", gg["k_star"])]),
                              ari_vs_zone_k3=ARI(z, gg["labels"][("kmeans", 3)])))
    zt = pd.DataFrame(zrows)
    save_table(zt, "rq4_ari_vs_zone")
    summary["zone"] = dict(primary_ari_k3=float(ARI(zone, prof[3])), median_ari_all_configs=float(zt[zt.units == "all31"].ari_vs_zone_kstar.median()),
                           crosstab=ct.to_dict(), sdi="not available: GBD Appendix 1 Table S12 was not in the upload")

    # ---------------- 7. RQ1 watchlist concentration by cluster
    core = subset(f, sets["core"]).copy()
    core["tier"] = tiers(core.pct_2010_23_mean, core.pct_2010_23_lo, core.divergence_pct)
    st = core.groupby("location").agg(clear=("tier", lambda s: (s == "Clear worsening").sum()),
                                      watch=("tier", lambda s: (s != "None").sum())).reindex(states)
    st["cluster"] = prof[3]
    kw_clear = kruskal(*[st[st.cluster == c].clear for c in sorted(set(prof[3]))])
    kw_watch = kruskal(*[st[st.cluster == c].watch for c in sorted(set(prof[3]))])
    tab = st.groupby("cluster").agg(states=("clear", "size"), clear_pairs=("clear", "sum"), watch_pairs=("watch", "sum"),
                                    clear_per_state=("clear", "mean"), watch_per_state=("watch", "mean"))
    chi = chi2_contingency(np.vstack([tab.clear_pairs, tab.states * 20 - tab.clear_pairs]))
    save_table(tab.reset_index(), "rq4_watchlist_by_cluster")
    summary["watchlist_concentration"] = dict(table=tab.reset_index().to_dict("records"), kruskal_clear_p=float(kw_clear.pvalue),
                                              kruskal_watch_p=float(kw_watch.pvalue), chi2_clear_p=float(chi.pvalue))

    # ---------------- 8. peer benchmark: state vs its cluster median as well as India
    core["cluster"] = core.location.map(dict(zip(states, prof[3])))
    core["peer_median_pct"] = core.groupby(["cluster", "risk"]).pct_2010_23_mean.transform("median")
    core["peer_median_asr_2023"] = core.groupby(["cluster", "risk"]).asr_2023_mean.transform("median")
    core["divergence_vs_peers_pp"] = core.pct_2010_23_mean - core.peer_median_pct
    core["hidden_divergence"] = (core.divergence_vs_peers_pp >= C.DIVERGENCE_PP) & (core.tier == "None")
    pb = core[["location", "cluster", "risk", "asr_2023_mean", "pct_2010_23_mean", "india_pct_2010_23", "peer_median_pct",
               "divergence_pct", "divergence_vs_peers_pp", "tier", "hidden_divergence"]]
    save_table(pb.sort_values("divergence_vs_peers_pp", ascending=False), "rq4_peer_benchmark")
    hd = pb[pb.hidden_divergence]
    save_table(hd.sort_values("divergence_vs_peers_pp", ascending=False), "rq4_hidden_divergence")
    summary["peer_benchmark"] = dict(n_hidden=int(len(hd)), by_risk=hd.risk.value_counts().head(8).to_dict(),
                                     top=hd.nlargest(10, "divergence_vs_peers_pp")[["location", "risk", "pct_2010_23_mean", "india_pct_2010_23", "peer_median_pct"]].to_dict("records"))

    summary["decision"] = dec.groupby("units").verdict.value_counts().unstack(fill_value=0).to_dict("index")
    (C.OUT / "summary" / "rq4_interpretation.json").write_text(json.dumps(summary, indent=2, default=str))
    print(f"  ARI vs pilot k=3 groups: {summary['ari_vs_pilot_k3_groups']:.2f}; ARI vs zone (primary, k=3): {summary['zone']['primary_ari_k3']:.2f}")
    for k, dd in descs.items():
        for c, d in dd.items():
            print(f"  k={k} {c} (n={len(d['states'])}): {d['description']}  | {', '.join(d['states'])}")
    print(f"  watchlist by cluster: KW p(clear)={kw_clear.pvalue:.3f}, p(any)={kw_watch.pvalue:.3f}")
    print(f"  hidden divergence pairs (vs peers, not vs India): {len(hd)}")


if __name__ == "__main__":
    main()
