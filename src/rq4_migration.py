"""RQ4 extension (4.8) - profile migration 1990 -> 2010 -> 2023.

One PCA on all three years pooled (age-standardised rates are comparable over time); each
state's path through that space; K-means centroids fitted once on the pooled data (k = 3)
and every state-year assigned to its nearest centroid; Sankey of membership across years.
Two variants: Level (log ASR) and Shape (log ASR minus the state-year mean log ASR, which
removes overall burden so only the mix of risks remains).
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from riskshift import config as C  # noqa: E402
from riskshift.common import banner, save_table, setup_plotting, short  # noqa: E402

K = 3
YEARS = ["asr1990", "asr2010", "asr2023"]


def describe(center, risks, n=3):
    o = np.argsort(center)
    hi = [short(risks[i], 22) for i in o[::-1][:n]]
    lo = [short(risks[i], 22) for i in o[:n]]
    return f"high {', '.join(hi)}; low {', '.join(lo)}"


def run(m, variant, plt):
    states, risks = m["states"], m["risks"]
    L = [np.log(np.clip(m[y], C.LOG_FLOOR, None)) for y in YEARS]
    if variant == "shape":
        L = [x - x.mean(1, keepdims=True) for x in L]
    P = np.vstack(L)                                  # (3n x p): 1990 rows, then 2010, then 2023
    mu, sd = P.mean(0), P.std(0)
    Z = (P - mu) / np.where(sd > 0, sd, 1)
    pca = PCA().fit(Z)
    S = pca.transform(Z)
    km = KMeans(K, n_init=C.KMEANS_STARTS, random_state=C.SEED).fit(Z)
    n = len(states)
    lab = km.labels_.reshape(3, n)
    # name clusters by their centroid profile
    names = {c: f"P{c + 1}" for c in range(K)}
    desc = {names[c]: describe(km.cluster_centers_[c], risks) for c in range(K)}
    traj = pd.DataFrame({"state": states})
    for t, y in enumerate([1990, 2010, 2023]):
        traj[f"pc1_{y}"] = S[t * n:(t + 1) * n, 0]
        traj[f"pc2_{y}"] = S[t * n:(t + 1) * n, 1]
        traj[f"profile_{y}"] = [names[c] for c in lab[t]]
    traj["shift_distance_1990_2023"] = np.linalg.norm(Z[2 * n:] - Z[:n], axis=1)
    traj["changed_profile"] = traj.profile_1990 != traj.profile_2023
    trans = pd.crosstab(traj.profile_1990, traj.profile_2023).rename_axis(index="1990", columns="2023")
    load = pd.DataFrame(pca.components_[:2].T, index=risks, columns=["PC1", "PC2"])
    load["PC1_var"], load["PC2_var"] = pca.explained_variance_ratio_[0], pca.explained_variance_ratio_[1]
    save_table(traj.sort_values("shift_distance_1990_2023", ascending=False), f"rq4_migration_{variant}_trajectories")
    save_table(trans.reset_index(), f"rq4_migration_{variant}_transitions_1990_2023")
    save_table(load.reset_index(names="risk"), f"rq4_migration_{variant}_loadings")

    # trajectory figure
    fig, ax = plt.subplots(figsize=(11, 8.5))
    cols = {"P1": "#1b9e77", "P2": "#d95f02", "P3": "#7570b3"}
    for r in traj.itertuples():
        xs = [r.pc1_1990, r.pc1_2010, r.pc1_2023]
        ys = [r.pc2_1990, r.pc2_2010, r.pc2_2023]
        ax.plot(xs, ys, color="0.7", lw=0.8, zorder=1)
        ax.annotate("", xy=(xs[2], ys[2]), xytext=(xs[1], ys[1]), arrowprops=dict(arrowstyle="->", color="0.5", lw=0.8))
        for x, y, p, mk in zip(xs, ys, [r.profile_1990, r.profile_2010, r.profile_2023], ["o", "s", "^"]):
            ax.scatter(x, y, color=cols[p], marker=mk, s=18, zorder=2, edgecolor="none")
        ax.annotate(r.state[:14], (xs[2], ys[2]), fontsize=6, xytext=(2, 2), textcoords="offset points")
    for p, c in cols.items():
        ax.scatter([], [], color=c, label=f"{p}: {desc[p]}")
    for mk, y in zip(["o", "s", "^"], [1990, 2010, 2023]):
        ax.scatter([], [], color="0.4", marker=mk, label=str(y))
    ax.legend(fontsize=6.5, loc="best")
    top1 = load.PC1.abs().sort_values(ascending=False).index[:3]
    top2 = load.PC2.abs().sort_values(ascending=False).index[:3]
    ax.set_xlabel(f"PC1 ({pca.explained_variance_ratio_[0]:.0%}): " + ", ".join(f"{short(r, 18)} {load.loc[r, 'PC1']:+.2f}" for r in top1), fontsize=8)
    ax.set_ylabel(f"PC2 ({pca.explained_variance_ratio_[1]:.0%}): " + ", ".join(f"{short(r, 18)} {load.loc[r, 'PC2']:+.2f}" for r in top2), fontsize=8)
    ax.set_title(f"RQ4 - State risk-profile paths 1990 -> 2010 -> 2023 ({variant} variant, pooled PCA, fixed k=3 centroids)")
    fig.text(0.01, -0.02, C.DISCLAIMER, fontsize=7, color="0.4")
    fig.savefig(C.FIGURES / f"rq4_migration_{variant}.png")
    plt.close(fig)

    # Sankey (interactive HTML)
    try:
        import plotly.graph_objects as go
        nodes = [f"{p} {y}" for y in (1990, 2010, 2023) for p in ("P1", "P2", "P3")]
        ix = {nm: i for i, nm in enumerate(nodes)}
        src, tgt, val, lab_ = [], [], [], []
        for a, b in ((1990, 2010), (2010, 2023)):
            ct = traj.groupby([f"profile_{a}", f"profile_{b}"]).state.apply(list)
            for (pa, pb), sts in ct.items():
                src.append(ix[f"{pa} {a}"]); tgt.append(ix[f"{pb} {b}"]); val.append(len(sts)); lab_.append(", ".join(sts))
        fig = go.Figure(go.Sankey(node=dict(label=nodes, color=[cols[n.split()[0]] for n in nodes], pad=18),
                                  link=dict(source=src, target=tgt, value=val, customdata=lab_,
                                            hovertemplate="%{customdata}<extra></extra>")))
        fig.update_layout(title=f"Profile membership 1990 -> 2010 -> 2023 ({variant}); "
                                + " | ".join(f"{p}: {d}" for p, d in desc.items()), font_size=11)
        fig.write_html(C.FIGURES / f"rq4_migration_{variant}_sankey.html", include_plotlyjs="cdn")
    except ImportError:
        pass
    return dict(variant=variant, pc_var=pca.explained_variance_ratio_[:3].tolist(), profiles=desc,
                transitions=trans.to_dict(), n_changed=int(traj.changed_profile.sum()),
                changed=traj[traj.changed_profile][["state", "profile_1990", "profile_2010", "profile_2023"]].to_dict("records"),
                membership_by_year={y: traj[f"profile_{y}"].value_counts().to_dict() for y in (1990, 2010, 2023)},
                top_movers=traj.nlargest(5, "shift_distance_1990_2023")[["state", "shift_distance_1990_2023"]].to_dict("records"),
                pc1_top=load.PC1.sort_values().round(2).to_dict(), pc2_top=load.PC2.sort_values().round(2).to_dict())


def main():
    banner("RQ4 migration 1990-2023")
    plt = setup_plotting()
    from rq4_features import load_inputs
    m = load_inputs()["all31"]["core"]
    out = {v: run(m, v, plt) for v in ("level", "shape")}
    (C.OUT / "summary" / "rq4_migration.json").write_text(json.dumps(out, indent=2, default=str))
    for v, o in out.items():
        print(f"  [{v}] PC var {np.round(o['pc_var'], 2)}; membership {o['membership_by_year']}; {o['n_changed']} states changed profile 1990->2023")
        for p, d in o["profiles"].items():
            print(f"     {p}: {d}")


if __name__ == "__main__":
    main()
