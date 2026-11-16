"""RQ4 cluster grid - K-means (50 starts), Ward, average linkage and diagonal GMM for
k = 2..6 on every configuration; k chosen per configuration by agreement of silhouette,
gap statistic and Calinski-Harabasz. The base partition of each configuration is K-means
at its chosen k (used by the null, stability and interpretation steps).
"""
import os

os.environ.setdefault("OMP_NUM_THREADS", "1")
import pickle  # noqa: E402
import sys  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from joblib import Parallel, delayed  # noqa: E402
from sklearn.metrics import adjusted_rand_score as ARI  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from riskshift import config as C  # noqa: E402
from riskshift.clustering import METHODS, build_X, choose_k, cluster, configs, gap_statistic, gmm_bic, indices  # noqa: E402
from riskshift.common import banner, save_table  # noqa: E402

GRID = C.PROCESSED / "rq4_grid.pkl"


def run_config(u, cfg, m):
    X = build_X(m["asr2023"], m["asr2010"], cfg["family"], cfg["scaling"])
    rows, labels = [], {}
    for meth in METHODS:
        for k in C.K_RANGE:
            lab = cluster(X, meth, k)
            labels[(meth, k)] = lab
            s, ch, db = indices(X, lab)
            rows.append(dict(units=u, config=cfg["cid"], method=meth, k=k, silhouette=s, calinski_harabasz=ch,
                             davies_bouldin=db, n_clusters_found=len(set(lab)), min_cluster_size=int(np.bincount(lab).min()),
                             bic=gmm_bic(X, k) if meth == "gmm" else np.nan))
    g = pd.DataFrame(rows)
    km = g[g.method == "kmeans"].set_index("k")
    gap, gap_s, gap_k = gap_statistic(X)
    k_star, rule = choose_k(km.silhouette.to_dict(), km.calinski_harabasz.to_dict(), gap_k)
    gm = g[g.method == "gmm"].set_index("k")
    sel = dict(units=u, config=cfg["cid"], risk_set=cfg["rset"], family=cfg["family"], scaling=cfg["scaling"],
               k_silhouette=int(km.silhouette.idxmax()), k_ch=int(km.calinski_harabasz.idxmax()), k_gap=int(gap_k),
               k_star=int(k_star), k_rule=rule, k_gmm_bic=int(gm.bic.idxmin()),
               sil_at_kstar=float(km.loc[k_star, "silhouette"]), sil_best=float(km.silhouette.max()),
               sil_range=f"{km.silhouette.min():.2f}-{km.silhouette.max():.2f}",
               gap_at_1=float(gap[1]), gap_at_kstar=float(gap[k_star]))
    base = labels[("kmeans", k_star)]
    for meth in METHODS[1:]:
        sel[f"ari_kmeans_vs_{meth}_kstar"] = ARI(base, labels[(meth, k_star)])
        sel[f"ari_kmeans_vs_{meth}_k3"] = ARI(labels[("kmeans", 3)], labels[(meth, 3)])
    return g, sel, labels, X


def main():
    banner("RQ4 cluster grid")
    from rq4_features import load_inputs
    data = load_inputs()
    jobs = [(u, cfg) for u in data for cfg in configs()]
    res = Parallel(n_jobs=C.N_JOBS)(delayed(run_config)(u, cfg, data[u][cfg["rset"]]) for u, cfg in jobs)
    grid = pd.concat([r[0] for r in res])
    sel = pd.DataFrame([r[1] for r in res])
    out = {(u, cfg["cid"]): dict(cfg=cfg, labels=r[2], X=r[3], k_star=r[1]["k_star"],
                                 states=data[u][cfg["rset"]]["states"]) for (u, cfg), r in zip(jobs, res)}
    GRID.write_bytes(pickle.dumps(out))
    save_table(grid, "rq4_cluster_grid_indices")
    save_table(sel, "rq4_k_selection")
    s = sel[sel.units == "all31"]
    print(s[["config", "k_silhouette", "k_ch", "k_gap", "k_star", "k_gmm_bic", "sil_at_kstar", "sil_range", "ari_kmeans_vs_ward_k3"]].to_string(index=False))
    print(f"  silhouette (K-means, k=2..6) across all 31-unit configs: {grid[(grid.units=='all31')&(grid.method=='kmeans')].silhouette.min():.2f}"
          f" - {grid[(grid.units=='all31')&(grid.method=='kmeans')].silhouette.max():.2f}")


if __name__ == "__main__":
    main()
