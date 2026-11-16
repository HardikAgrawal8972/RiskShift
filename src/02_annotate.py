"""02_annotate - parse numbers, attach the risk hierarchy, tag geography.

* numbers: strip thousands separators, cast to float; '-' -> missing (not zero)
* risk level: from the GBD 2023 risk hierarchy (Appendix 2, Table S1), frozen in
  data/reference/risk_hierarchy.csv; four S14B names are mapped by hand
* parent risk: derived from the published row order (S14B lists risks depth-first)
* split "All causes" rows (risk totals) from risk -> cause sub-rows
* tag national vs state, the "Other Union Territories" aggregate, and Zonal Council
* drop the four risks with no mortality estimated anywhere in India
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from riskshift import config as C  # noqa: E402
from riskshift.common import banner, parse_num  # noqa: E402

HIER = C.REFERENCE / "risk_hierarchy.csv"


def build_hierarchy(ext: pd.DataFrame) -> pd.DataFrame:
    """Risk -> level -> parent. Levels come from the hierarchy table as carried in the pilot
    extract (column risk_level); the 4 names that differ are mapped manually."""
    india = ext[(ext.block == C.INDIA_BLOCK) & (~ext.is_outcome)].sort_values("row_idx")
    levels = {}
    if C.PROTOTYPE_EXTRACT.exists():
        p = pd.read_csv(C.PROTOTYPE_EXTRACT, usecols=["risk", "is_outcome", "risk_level", "block"])
        p = p[(p.block == C.INDIA_BLOCK) & (~p.is_outcome)].dropna(subset=["risk_level"])
        levels = dict(zip(p.risk, p.risk_level.astype(int)))
    rows, stack = [], {}
    for order, risk in enumerate(india["risk"]):
        if risk in C.MANUAL_RISK_LEVELS:
            lvl, src = C.MANUAL_RISK_LEVELS[risk], "manual map (name differs from hierarchy table)"
        elif risk in levels:
            lvl, src = levels[risk], "GBD 2023 Appendix 2 Table S1"
        else:
            raise KeyError(f"no hierarchy level for {risk!r}")
        stack[lvl] = risk
        for deeper in [k for k in stack if k > lvl]:
            del stack[deeper]
        parent = stack.get(lvl - 1) if lvl > 0 else None
        rows.append(dict(order=order, risk=risk, risk_level=lvl, parent_risk=parent, level_source=src))
    h = pd.DataFrame(rows)
    # ancestors at level 1 and 2
    by = h.set_index("risk")
    def ancestor(r, target):
        while r is not None and by.loc[r, "risk_level"] > target:
            r = by.loc[r, "parent_risk"]
        return r if r is not None and by.loc[r, "risk_level"] == target else None
    h["level1_risk"] = [ancestor(r, 1) for r in h.risk]
    h["level2_risk"] = [ancestor(r, 2) for r in h.risk]
    counts = h.risk_level.value_counts().sort_index().to_dict()
    assert counts == {0: 1, 1: 3, 2: 20, 3: 42, 4: 22}, counts
    return h


def main():
    banner("02_annotate")
    ext = pd.read_csv(C.EXTRACT_CSV, dtype=str)
    for c in ["row_idx", "block", "row_in_block"]:
        ext[c] = ext[c].astype(int)
    ext["is_outcome"] = ext["is_outcome"].map({"True": True, "False": False})

    if HIER.exists():
        h = pd.read_csv(HIER)
    else:
        h = build_hierarchy(ext)
        h.to_csv(HIER, index=False)
        print(f"  froze {HIER.relative_to(C.ROOT)} ({len(h)} risks)")

    val_cols = [c for c in ext.columns if c.endswith(("_mean", "_lo", "_hi"))]
    n_dash = int((ext.loc[~ext.is_outcome, val_cols] == "-").any(axis=1).sum())
    for c in val_cols:
        ext[c] = parse_num(ext[c])

    df = ext.merge(h[["risk", "risk_level", "parent_risk", "level1_risk", "level2_risk", "order"]],
                   on="risk", how="left", validate="many_to_one")
    assert df["risk_level"].notna().all()
    df["geo"] = np.where(df.block == C.INDIA_BLOCK, "national", "state")
    df["is_aggregate"] = df["location"].isin(C.AGGREGATE_UNITS)
    df["zone"] = df["location"].map(C.ZONE).where(df.geo == "state")
    df["sdi_group"] = pd.NA   # Appendix 1 Table S12 not in this upload
    assert df.loc[df.geo == "state", "zone"].notna().all()

    # risks with no mortality anywhere in India
    risk_rows = df[~df.is_outcome]
    empty = risk_rows.groupby("risk")["asr_2023_mean"].apply(lambda s: s.isna().all())
    empty = sorted(empty[empty].index)
    assert empty == sorted(C.NO_MORTALITY_RISKS), empty
    partial = risk_rows[~risk_rows.risk.isin(empty)]["asr_2023_mean"].isna().sum()
    assert partial == 0, "unexpected partial missingness"
    df = df[~df.risk.isin(empty)].copy()

    neg_lo = int((df.loc[~df.is_outcome, [c for c in val_cols if c.startswith(("asr", "deaths", "paf")) and c.endswith("_lo")]] < 0).any(axis=1).sum())

    df.to_parquet(C.ANNOTATED, index=False)
    print(f"  risk rows with '-' before drop: {n_dash} of {int((~ext.is_outcome).sum())} "
          f"({n_dash / (~ext.is_outcome).sum():.1%}); dropped {len(empty)} risks: {empty}")
    print(f"  risk rows with a negative lower bound (deaths/PAF/ASR): {neg_lo}")
    print(f"  wrote {C.ANNOTATED.relative_to(C.ROOT)}  {df.shape}")


if __name__ == "__main__":
    main()
