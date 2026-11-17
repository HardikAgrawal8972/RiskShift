"""03_sets - define the three pre-registered, non-overlapping risk sets.

Core           the 20 level-2 risks (siblings; all have mortality).
Detail         level-3 risks with ASR >= DETAIL_MIN_ASR in every state unit in 2010 and 2023;
               "Particulate matter pollution" is replaced by its two level-4 components
               (ambient PM, household air pollution) so the set separates them.
Policy-salient pool = Detail + level-2 risks that have no level-3 children (a non-overlapping
               "most detailed up to level 3" list). Select the POLICY_TOP_N risks with the
               highest national 2023 ASR, plus every pool risk whose national 2010-23 ASR
               change interval lies wholly above zero AND whose national 2023 ASR is at least
               the materiality floor.
All rules are fixed here, in writing, before any RQ result is computed.
"""
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from riskshift import config as C  # noqa: E402
from riskshift.common import banner  # noqa: E402


def main():
    banner("03_sets")
    df = pd.read_parquet(C.ANNOTATED)
    tot = df[~df.is_outcome]
    h = tot.drop_duplicates("risk").sort_values("order")[["risk", "risk_level", "parent_risk", "level2_risk", "order"]]
    states = tot[tot.geo == "state"]
    india = tot[tot.geo == "national"].set_index("risk")

    core = h.loc[h.risk_level == 2, "risk"].tolist()
    assert len(core) == 20

    def passes(r):
        s = states[states.risk == r]
        return bool((s.asr_2010_mean >= C.DETAIL_MIN_ASR).all() and (s.asr_2023_mean >= C.DETAIL_MIN_ASR).all())

    detail, excluded = [], []
    for r in h.loc[h.risk_level == 3, "risk"]:
        members = C.DETAIL_SPLIT.get(r, [r])
        for m in members:
            (detail if passes(m) else excluded).append(m)
    has_l3_child = set(h.loc[h.risk_level == 3, "parent_risk"])
    leaf_l2 = [r for r in core if r not in has_l3_child]
    pool = sorted(set(detail) | set(leaf_l2), key=lambda r: h.set_index("risk").loc[r, "order"])

    nat = india.loc[pool, ["asr_2023_mean", "pct_asr_2010_23_lo"]]
    top = nat.sort_values("asr_2023_mean", ascending=False).head(C.POLICY_TOP_N).index.tolist()
    rising = nat[(nat.pct_asr_2010_23_lo > 0) & (nat.asr_2023_mean >= C.MATERIALITY_ASR)].index.tolist()
    rising_small = nat[(nat.pct_asr_2010_23_lo > 0) & (nat.asr_2023_mean < C.MATERIALITY_ASR)].index.tolist()
    policy = [r for r in pool if r in set(top) | set(rising)]

    lvl2 = h.set_index("risk")["level2_risk"].to_dict()
    sets = {
        "core": core,
        "detail": detail,
        "policy": policy,
        "detail_excluded": excluded,
        "policy_pool": pool,
        "policy_reason": {r: ("top national ASR" if r in top else "") +
                          (" + " if r in top and r in rising else "") +
                          ("clearly rising nationally" if r in rising else "") for r in policy},
        "policy_rising_below_floor": rising_small,
        "level2_parent": {r: lvl2[r] for r in sorted(set(detail) | set(policy))},
        "rules": __doc__,
    }
    C.SETS_JSON.write_text(json.dumps(sets, indent=2))
    print(f"  Core {len(core)} | Detail {len(detail)} (excluded {len(excluded)}: {excluded})")
    print(f"  Policy-salient {len(policy)}: {policy}")
    print(f"  clearly rising but below floor (not selected): {rising_small}")


if __name__ == "__main__":
    main()
