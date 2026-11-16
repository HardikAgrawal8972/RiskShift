"""RQ4 features - the pre-declared grid: 4 families x 3 risk sets x 2 scalings = 24
configurations, for 31 state units and again for 30 (without "Other Union Territories").
Any configuration wider than 20 raw features (and every F4) is PCA-reduced to 80% variance.
"""
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from riskshift import config as C  # noqa: E402
from riskshift.clustering import FAMILY_DESC, build_X, configs  # noqa: E402
from riskshift.common import banner, load_features, load_sets, save_table, subset, wide  # noqa: E402

INPUTS = C.PROCESSED / "rq4_inputs.pkl"
UNITS = {"all31": True, "no_other_uts30": False}


def load_inputs():
    return pickle.loads(INPUTS.read_bytes())


def matrices(f, risks):
    a23 = wide(f, "asr_2023_mean", risks)
    a10 = wide(f, "asr_2010_mean", risks)
    a90 = wide(f, "asr_1990_mean", risks)
    return dict(states=list(a23.index), risks=list(a23.columns), asr2023=a23.values, asr2010=a10.values, asr1990=a90.values)


def main():
    banner("RQ4 features")
    sets = load_sets()
    data = {}
    rows = []
    for u, inc in UNITS.items():
        f = load_features(include_aggregate=inc)
        data[u] = {s: matrices(subset(f, sets[s]), sets[s]) for s in ("core", "detail", "policy")}
        for cfg in configs():
            m = data[u][cfg["rset"]]
            X, meta = build_X(m["asr2023"], m["asr2010"], cfg["family"], cfg["scaling"], return_meta=True)
            rows.append(dict(units=u, config=cfg["cid"], risk_set=cfg["rset"], family=cfg["family"],
                             family_desc=FAMILY_DESC[cfg["family"]], scaling=cfg["scaling"], n_units=X.shape[0], **meta))
    INPUTS.write_bytes(pickle.dumps(data))
    t = pd.DataFrame(rows)
    save_table(t, "rq4_feature_configs")
    # PCA of the primary level matrix: how much is "overall burden"?
    from sklearn.decomposition import PCA
    from riskshift.clustering import _scale
    m = data["all31"]["core"]
    Z = _scale(np.log(np.clip(m["asr2023"], C.LOG_FLOOR, None)), "z")
    p = PCA().fit(Z)
    corr = np.corrcoef(p.transform(Z)[:, 0], Z.mean(1))[0, 1]
    print(f"  {len(t)} configurations built; core F1 PC1 = {p.explained_variance_ratio_[0]:.1%} of variance, "
          f"|corr(PC1, state mean z)| = {abs(corr):.2f}")
    print(t[t.units == "all31"][["config", "p_raw", "p_final", "var_explained"]].to_string(index=False))


if __name__ == "__main__":
    main()
