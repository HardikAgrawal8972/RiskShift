"""04_features - one tidy table, one row per state unit x risk (risk totals only).

Columns: ASR 1990/2010/2023 with bounds; deaths and PAF 2023 with bounds; absolute and
% change 2010-23 (with GBD's own % change interval); India's change for the same risk;
divergence (state minus India) in % points and in absolute rate; flags worse_point,
worse_clear, small_base; 1990 direction check.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from riskshift import config as C  # noqa: E402
from riskshift.common import banner  # noqa: E402

KEEP = ["block", "location", "zone", "is_aggregate", "sdi_group", "risk", "risk_level",
        "parent_risk", "level2_risk", "order"]


def build(tot: pd.DataFrame) -> pd.DataFrame:
    f = tot[KEEP].copy()
    for y in C.YEARS:
        for s in C.STATS:
            f[f"asr_{y}_{s}"] = tot[f"asr_{y}_{s}"]
    for m in ("deaths", "paf"):
        for s in C.STATS:
            f[f"{m}_2023_{s}"] = tot[f"{m}_2023_{s}"]
    f["deaths_2010_mean"] = tot["deaths_2010_mean"]
    for s in C.STATS:
        f[f"pct_2010_23_{s}"] = tot[f"pct_asr_2010_23_{s}"]
    f["abs_2010_23"] = f.asr_2023_mean - f.asr_2010_mean
    f["abs_1990_2010"] = f.asr_2010_mean - f.asr_1990_mean
    f["abs_1990_2023"] = f.asr_2023_mean - f.asr_1990_mean
    f["pct_1990_2023"] = 100 * f.abs_1990_2023 / f.asr_1990_mean.replace(0, np.nan)
    return f


def main():
    banner("04_features")
    df = pd.read_parquet(C.ANNOTATED)
    tot = df[~df.is_outcome].reset_index(drop=True)
    f = build(tot)
    india = f[f.block == C.INDIA_BLOCK].drop(columns=["zone", "is_aggregate", "sdi_group"]).reset_index(drop=True)
    st = f[f.block != C.INDIA_BLOCK].reset_index(drop=True)

    ind = india.set_index("risk")
    st["india_asr_2010"] = st.risk.map(ind.asr_2010_mean)
    st["india_asr_2023"] = st.risk.map(ind.asr_2023_mean)
    st["india_pct_2010_23"] = st.risk.map(ind.pct_2010_23_mean)
    st["india_abs_2010_23"] = st.risk.map(ind.abs_2010_23)
    st["divergence_pct"] = st.pct_2010_23_mean - st.india_pct_2010_23     # % points
    st["divergence_abs"] = st.abs_2010_23 - st.india_abs_2010_23          # per 100,000
    st["worse_point"] = st.pct_2010_23_mean > 0
    st["worse_clear"] = st.pct_2010_23_lo > 0
    st["small_base"] = st.asr_2010_mean < C.SMALL_BASE_ASR
    st["dir_1990_2010"] = np.sign(st.abs_1990_2010).astype(int)
    st["dir_1990_2023"] = np.sign(st.abs_1990_2023).astype(int)
    # one cell (Sikkim, high temperature) has ASR 0.0 in both years, so GBD gives no % change
    st["dir_2010_2023"] = np.sign(st.pct_2010_23_mean.fillna(0)).astype(int)
    # recent reversal: the 2010-23 direction runs against the long-run 1990-2023 direction
    st["recent_reversal"] = (st.dir_2010_2023 != 0) & (st.dir_1990_2023 != 0) & (st.dir_2010_2023 != st.dir_1990_2023)
    st["neg_lower_bound"] = (st[[c for c in st.columns if c.endswith("_lo") and not c.startswith("pct")]] < 0).any(axis=1)

    assert st.groupby("risk").size().eq(31).all()
    st.to_parquet(C.FEATURES, index=False)
    india.to_parquet(C.FEATURES_INDIA, index=False)
    st.to_csv(C.PROCESSED / "features_state_risk.csv", index=False)
    india.to_csv(C.PROCESSED / "features_india_risk.csv", index=False)
    print(f"  state x risk rows: {len(st):,} ({st.risk.nunique()} risks x {st.location.nunique()} units)")
    print(f"  wrote {C.FEATURES.relative_to(C.ROOT)} and {C.FEATURES_INDIA.relative_to(C.ROOT)}")


if __name__ == "__main__":
    main()
