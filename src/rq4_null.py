"""RQ4 existence test (4a) - is there more grouping than a correlated cloud would show?

For every configuration: 500 null datasets from a multivariate normal with the observed
mean and covariance (same correlations, no clusters), plus 500 column-shuffled datasets.
Each is clustered the same way (K-means, k = 2..6, best silhouette kept). Real structure is
claimed only if the observed best silhouette exceeds the null 95th percentile AND is >= 0.25.
"""
import os

os.environ.setdefault("OMP_NUM_THREADS", "1")
import pickle  # noqa: E402
import sys  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from joblib import Parallel, delayed  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from riskshift import config as C  # noqa: E402
from riskshift.clustering import best_sil, null_best_sil  # noqa: E402
from riskshift.common import banner, save_table  # noqa: E402

GRID = C.PROCESSED / "rq4_grid.pkl"
NULLS = C.PROCESSED / "rq4_nulls.pkl"


def main():
    banner("RQ4 null existence test")
    grid = pickle.loads(GRID.read_bytes())
    keys = list(grid)
    chunks = 4   # split each null run so all cores stay busy
    per = C.N_NULL // chunks
    jobs = [(key, kind, c) for key in keys for kind in ("mvn", "shuffle") for c in range(chunks)]
    res = Parallel(n_jobs=C.N_JOBS, verbose=0)(
        delayed(null_best_sil)(grid[key]["X"], kind, per, C.SEED + 1000 * c + (0 if kind == "mvn" else 7))
        for key, kind, c in jobs)
    nulls = {}
    for (key, kind, c), r in zip(jobs, res):
        nulls.setdefault((key, kind), []).append(r)
    nulls = {k: np.concatenate(v) for k, v in nulls.items()}
    obs = dict(zip(keys, Parallel(n_jobs=C.N_JOBS)(delayed(best_sil)(grid[k]["X"]) for k in keys)))
    rows = []
    for key in keys:
        u, cid = key
        o = obs[key]
        mv, sh = nulls[(key, "mvn")], nulls[(key, "shuffle")]
        rows.append(dict(units=u, config=cid, k_star=grid[key]["k_star"], observed_best_sil=o,
                         null_mvn_median=np.median(mv), null_mvn_p95=np.percentile(mv, 95), p_mvn=(1 + (mv >= o).sum()) / (1 + len(mv)),
                         null_shuffle_median=np.median(sh), null_shuffle_p95=np.percentile(sh, 95), p_shuffle=(1 + (sh >= o).sum()) / (1 + len(sh)),
                         sil_ge_025=o >= C.SIL_MIN, beats_mvn=o > np.percentile(mv, 95), beats_shuffle=o > np.percentile(sh, 95)))
    t = pd.DataFrame(rows)
    t["gate1_existence"] = t.sil_ge_025 & t.beats_mvn
    NULLS.write_bytes(pickle.dumps(dict(nulls=nulls, observed=obs)))
    save_table(t, "rq4_existence_null_test")
    print(t[t.units == "all31"][["config", "observed_best_sil", "null_mvn_p95", "p_mvn", "null_shuffle_p95", "p_shuffle", "gate1_existence"]].to_string(index=False))
    print(f"  gate 1 passed: {int(t[t.units=='all31'].gate1_existence.sum())}/24 (31 units), "
          f"{int(t[t.units=='no_other_uts30'].gate1_existence.sum())}/24 (30 units)")


if __name__ == "__main__":
    main()
