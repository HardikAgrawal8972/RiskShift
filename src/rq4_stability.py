"""RQ4 stability (4b) and the pre-declared decision rule (4.6).

Per configuration (base = K-means at its chosen k):
  1. bootstrap states 500x, Hennig clusterboot Jaccard per cluster
  2. agreement across the 24 feature configurations (pairwise ARI)
  3. GBD uncertainty: refit on each of RQ3's 1,000 Monte Carlo datasets, ARI vs base
  4. leave-one-risk-out refits; a risk whose removal drops ARI below 0.60 is flagged
  5. consensus matrix: share of runs in which each pair of states lands together
     (the four sources above averaged with equal weight), reordered hierarchically.
Decision rule: robust if silhouette >= 0.25, beats the null 95th percentile, every cluster's
bootstrap Jaccard >= 0.75 and the configuration's median ARI with the other 23 >= 0.60;
partial if gate 1 passes and at least one cluster is bootstrap-stable (>= 0.75); else gradient.
"""
import os

os.environ.setdefault("OMP_NUM_THREADS", "1")
import json  # noqa: E402
import pickle  # noqa: E402
import sys  # noqa: E402
from collections import Counter  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from joblib import Parallel, delayed  # noqa: E402
from scipy.cluster.hierarchy import fcluster, leaves_list, linkage  # noqa: E402
from scipy.spatial.distance import squareform  # noqa: E402
from sklearn.metrics import adjusted_rand_score as ARI  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from riskshift import config as C  # noqa: E402
from riskshift.clustering import bootstrap_jaccard, build_X, cluster, coassign, configs  # noqa: E402
from riskshift.common import banner, save_table  # noqa: E402

GRID = C.PROCESSED / "rq4_grid.pkl"
STAB = C.PROCESSED / "rq4_stability.pkl"


def mc_matrices(mc, states, risks):
    idx = pd.Series(range(len(mc["location"])), index=pd.MultiIndex.from_arrays([mc["location"], mc["risk"]]))
    pos = idx.loc[[(s, r) for s in states for r in risks]].values.reshape(len(states), len(risks))
    return pos


def run_config(key, g, m, mc_a23, mc_a10, pos, seed):
    cfg, base, k = g["cfg"], g["labels"][("kmeans", g["k_star"])], g["k_star"]
    X = g["X"]
    jac, bco, bcnt = bootstrap_jaccard(X, base, k, C.N_BOOT, seed)
    # uncertainty draws
    unc_ari, uco = [], np.zeros((len(base), len(base)))
    for i in range(mc_a23.shape[0]):
        Xi = build_X(mc_a23[i][pos], mc_a10[i][pos], cfg["family"], cfg["scaling"])
        lab = cluster(Xi, "kmeans", k, seed=i, n_init=C.KMEANS_STARTS_RESAMPLE)
        unc_ari.append(ARI(base, lab))
        uco += coassign(lab)
    # leave one risk out
    loro, lco = {}, np.zeros((len(base), len(base)))
    for j, r in enumerate(m["risks"]):
        keep = [c for c in range(len(m["risks"])) if c != j]
        Xj = build_X(m["asr2023"][:, keep], m["asr2010"][:, keep], cfg["family"], cfg["scaling"])
        lab = cluster(Xj, "kmeans", k, n_init=C.KMEANS_STARTS_RESAMPLE)
        loro[r] = ARI(base, lab)
        lco += coassign(lab)
    return dict(jaccard=jac, boot_co=bco, boot_cnt=bcnt, unc_ari=np.array(unc_ari), unc_co=uco / mc_a23.shape[0],
                loro=loro, loro_co=lco / len(m["risks"]))


def cores_and_floaters(M, states):
    D = 1 - M
    np.fill_diagonal(D, 0)
    Z = linkage(squareform(D, checks=False), method="average")
    order = leaves_list(Z)
    grp = fcluster(Z, 1 - C.CORE_COASSIGN, criterion="distance")
    off = M.copy()
    np.fill_diagonal(off, -1)
    floaters = [states[i] for i in range(len(states)) if off[i].max() < C.FLOAT_COASSIGN]
    cores = []
    for g in sorted(set(grp)):
        mem = np.where(grp == g)[0]
        if len(mem) >= 2:
            sub = M[np.ix_(mem, mem)]
            within = sub[np.triu_indices(len(mem), 1)].mean()
            cores.append(dict(states=[states[i] for i in mem], size=len(mem), mean_coassignment=float(within)))
    cores.sort(key=lambda c: -c["size"])
    return order, cores, floaters


def main():
    banner("RQ4 stability")
    from rq4_features import load_inputs
    data = load_inputs()
    grid = pickle.loads(GRID.read_bytes())
    mc = dict(np.load(C.MC_DRAWS))
    ex = pd.read_csv(C.TABLES / "rq4_existence_null_test.csv").set_index(["units", "config"])
    keys = list(grid)
    jobs = []
    for n, key in enumerate(keys):
        u, cid = key
        m = data[u][grid[key]["cfg"]["rset"]]
        pos = mc_matrices(mc, m["states"], m["risks"])
        jobs.append(delayed(run_config)(key, grid[key], m, mc["asr2023"], mc["asr2010"], pos, C.SEED + n))
    res = dict(zip(keys, Parallel(n_jobs=C.N_JOBS, max_nbytes="1M")(jobs)))

    rows, summary, consensus = [], {}, {}
    for u in data:
        ks = [k for k in keys if k[0] == u]
        cids = [k[1] for k in ks]
        L = {k[1]: grid[k]["labels"][("kmeans", grid[k]["k_star"])] for k in ks}
        L3 = {k[1]: grid[k]["labels"][("kmeans", 3)] for k in ks}
        A = pd.DataFrame([[ARI(L[a], L[b]) for b in cids] for a in cids], index=cids, columns=cids)
        A3 = pd.DataFrame([[ARI(L3[a], L3[b]) for b in cids] for a in cids], index=cids, columns=cids)
        save_table(A.reset_index(names="config"), f"rq4_cross_config_ari_{u}")
        save_table(A3.reset_index(names="config"), f"rq4_cross_config_ari_k3_{u}")
        off = ~np.eye(len(cids), dtype=bool)
        med_all = float(np.median(A.values[off]))
        med_all3 = float(np.median(A3.values[off]))
        for k in ks:
            cid = k[1]
            r = res[k]
            jac = r["jaccard"]
            e = ex.loc[(u, cid)]
            med_cfg = float(np.median(A.loc[cid].drop(cid)))
            gate1 = bool(e.gate1_existence)
            gate2 = min(jac.values()) >= C.BOOT_JACCARD_STABLE and med_cfg >= C.ARI_MIN
            stable_any = max(jac.values()) >= C.BOOT_JACCARD_STABLE
            verdict = "Robust clusters" if gate1 and gate2 else ("Partial structure" if gate1 and stable_any else "Gradient, not clusters")
            flagged = [rk for rk, a in r["loro"].items() if a < C.ARI_MIN]
            rows.append(dict(units=u, config=cid, k_star=grid[k]["k_star"], observed_best_sil=e.observed_best_sil,
                             null_mvn_p95=e.null_mvn_p95, gate1_existence=gate1,
                             boot_jaccard_min=min(jac.values()), boot_jaccard_max=max(jac.values()),
                             boot_jaccard_by_cluster="; ".join(f"{c}:{v:.2f}" for c, v in jac.items()),
                             n_clusters_stable=sum(v >= C.BOOT_JACCARD_STABLE for v in jac.values()),
                             n_clusters_dissolved=sum(v < C.BOOT_JACCARD_DISSOLVED for v in jac.values()),
                             median_ari_vs_other_configs=med_cfg, gate2_stability=gate2,
                             unc_ari_median=float(np.median(r["unc_ari"])), unc_ari_p05=float(np.percentile(r["unc_ari"], 5)),
                             unc_ari_p95=float(np.percentile(r["unc_ari"], 95)),
                             loro_ari_median=float(np.median(list(r["loro"].values()))),
                             loro_ari_min=float(min(r["loro"].values())),
                             loro_flagged_risks="; ".join(flagged), verdict=verdict))
        # consensus: four sources, equal weight
        states = grid[ks[0]]["states"]
        src_grid = np.mean([coassign(L[c]) for c in cids], axis=0)
        bco = sum(res[k]["boot_co"] for k in ks)
        bcnt = sum(res[k]["boot_cnt"] for k in ks)
        src_boot = np.divide(bco, bcnt, out=np.zeros_like(bco), where=bcnt > 0)
        src_unc = np.mean([res[k]["unc_co"] for k in ks], axis=0)
        src_loro = np.mean([res[k]["loro_co"] for k in ks], axis=0)
        M = (src_grid + src_boot + src_unc + src_loro) / 4
        order, cores, floaters = cores_and_floaters(M, states)
        consensus[u] = dict(states=states, M=M, order=order, sources=dict(grid=src_grid, bootstrap=src_boot, uncertainty=src_unc, loro=src_loro),
                            cores=cores, floaters=floaters)
        save_table(pd.DataFrame(M, index=states, columns=states).reset_index(names="state"), f"rq4_consensus_matrix_{u}")
        summary[u] = dict(median_cross_config_ari=med_all, median_cross_config_ari_k3=med_all3, cores=cores, floaters=floaters)

    t = pd.DataFrame(rows)
    save_table(t, "rq4_decision_table")
    for u in data:
        s = t[t.units == u]
        vc = Counter(s.verdict)
        summary[u]["verdict_counts"] = dict(vc)
        summary[u]["overall_verdict"] = vc.most_common(1)[0][0]
        summary[u]["gate1_pass"] = int(s.gate1_existence.sum())
        summary[u]["gate2_pass"] = int(s.gate2_stability.sum())
        summary[u]["unc_ari_median_over_configs"] = float(s.unc_ari_median.median())
        summary[u]["loro_ari_median_over_configs"] = float(s.loro_ari_median.median())
        summary[u]["core_F1_z"] = s[s.config == "core-F1-z"].iloc[0].to_dict()
    STAB.write_bytes(pickle.dumps(dict(results=res, consensus=consensus)))
    (C.OUT / "summary" / "rq4_stability.json").write_text(json.dumps(summary, indent=2, default=lambda o: o.item() if hasattr(o, "item") else str(o)))
    print(t[t.units == "all31"][["config", "k_star", "gate1_existence", "boot_jaccard_min", "boot_jaccard_max", "median_ari_vs_other_configs",
                                  "unc_ari_median", "loro_ari_median", "verdict"]].to_string(index=False))
    for u in data:
        print(f"  [{u}] verdict counts {summary[u]['verdict_counts']} -> {summary[u]['overall_verdict']}; "
              f"median cross-config ARI {summary[u]['median_cross_config_ari']:.2f}")
        for c in summary[u]["cores"]:
            print(f"     core ({c['mean_coassignment']:.2f}): {', '.join(c['states'])}")
        print(f"     floaters: {', '.join(summary[u]['floaters']) or 'none'}")


if __name__ == "__main__":
    main()
