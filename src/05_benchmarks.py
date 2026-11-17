"""05_benchmarks - India and its states against the world and South Asia.

The proposal planned to use S14A as the global benchmark; S14B carries the same Global
rows, plus the South Asia region, so both benchmarks come from the main data file.
For every risk in the analysis sets: Global, South Asia and India ASR 2010 -> 2023 with
GBD's change interval; how many states sit above the global rate; and which states are
rising where the world is falling.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from riskshift import config as C  # noqa: E402
from riskshift.common import banner, load_features, load_india, load_sets, parse_num, save_table, setup_plotting, short  # noqa: E402


def direction(lo, mean):
    return np.where(lo > 0, "clearly rising", np.where(mean > 0, "rising (uncertain)", "falling"))


def main():
    banner("05_benchmarks")
    if not C.BENCH_CSV.exists():
        print("  benchmark extract missing (raw XLSX not available) - skipping")
        return
    plt = setup_plotting()
    b = pd.read_csv(C.BENCH_CSV, dtype=str)
    b = b[b.is_outcome == "False"].copy()
    num = [c for c in b.columns if c.endswith(("_mean", "_lo", "_hi"))]
    for c in num:
        b[c] = parse_num(b[c])
    b["block"] = b.block.astype(int)
    b["bench"] = b.block.map(C.BENCHMARK_BLOCKS)
    b.to_parquet(C.BENCH_FEATURES, index=False)

    sets = load_sets()
    india, f = load_india().set_index("risk"), load_features()
    g = b[b.bench == "Global"].set_index("risk")
    sa = b[b.bench == "South Asia"].set_index("risk")

    rows = []
    for setname in ("core", "detail"):
        for r in sets[setname]:
            st = f[f.risk == r]
            gl23, gl_pct = g.loc[r, "asr_2023_mean"], g.loc[r, "pct_asr_2010_23_mean"]
            rows.append(dict(
                set=setname, risk=r,
                global_2010=g.loc[r, "asr_2010_mean"], global_2023=gl23, global_pct=gl_pct,
                global_lo=g.loc[r, "pct_asr_2010_23_lo"], global_hi=g.loc[r, "pct_asr_2010_23_hi"],
                south_asia_2010=sa.loc[r, "asr_2010_mean"], south_asia_2023=sa.loc[r, "asr_2023_mean"], south_asia_pct=sa.loc[r, "pct_asr_2010_23_mean"],
                india_2010=india.loc[r, "asr_2010_mean"], india_2023=india.loc[r, "asr_2023_mean"], india_pct=india.loc[r, "pct_2010_23_mean"],
                india_lo=india.loc[r, "pct_2010_23_lo"], india_hi=india.loc[r, "pct_2010_23_hi"],
                india_vs_global_ratio_2023=india.loc[r, "asr_2023_mean"] / gl23 if gl23 > 0 else np.nan,
                states_above_global_2023=int((st.asr_2023_mean > gl23).sum()),
                states_rising=int((st.pct_2010_23_mean > 0).sum()),
                states_rising_while_world_falls=int(((st.pct_2010_23_mean > 0) & (gl_pct <= 0)).sum()),
                states_clearly_rising_while_world_falls=int(((st.pct_2010_23_lo > 0) & (gl_pct <= 0)).sum()),
            ))
    t = pd.DataFrame(rows)
    t["global_direction"] = direction(t.global_lo, t.global_pct)
    t["india_direction"] = direction(t.india_lo, t.india_pct)
    t["india_worse_trend_than_world"] = t.india_pct > t.global_pct
    save_table(t, "bench_india_vs_world")

    # state level: pairs where the state's rate is rising but the world's is falling
    gl = g[["asr_2023_mean", "pct_asr_2010_23_mean"]].rename(columns={"asr_2023_mean": "global_2023", "pct_asr_2010_23_mean": "global_pct"})
    s = f[f.risk.isin(sets["core"])].merge(gl, left_on="risk", right_index=True)
    s["ratio_to_global_2023"] = s.asr_2023_mean / s.global_2023
    opp = s[(s.pct_2010_23_lo > 0) & (s.global_pct <= 0)][["location", "risk", "asr_2010_mean", "asr_2023_mean", "pct_2010_23_mean", "pct_2010_23_lo", "global_pct", "ratio_to_global_2023"]]
    save_table(opp.sort_values("pct_2010_23_mean", ascending=False), "bench_states_rising_while_world_falls")
    save_table(s[["location", "risk", "asr_2023_mean", "global_2023", "ratio_to_global_2023"]].sort_values("ratio_to_global_2023", ascending=False), "bench_state_vs_global_ratio")

    # figure: Core risks, Global / South Asia / India 2010 -> 2023
    core = t[t.set == "core"].sort_values("india_2023")
    fig, ax = plt.subplots(figsize=(10, 9))
    cols = {"Global": "#7f7f7f", "South Asia": "#1b9e77", "India": "#d95f02"}
    for i, r in enumerate(core.itertuples()):
        for j, (lab, a, z) in enumerate([("Global", r.global_2010, r.global_2023), ("South Asia", r.south_asia_2010, r.south_asia_2023), ("India", r.india_2010, r.india_2023)]):
            y = i + (j - 1) * 0.25
            ax.annotate("", xy=(max(z, 0.05), y), xytext=(max(a, 0.05), y), arrowprops=dict(arrowstyle="->", color=cols[lab], lw=1.6))
            ax.scatter(max(a, 0.05), y, color=cols[lab], s=10)
    ax.set_yticks(range(len(core)), [short(r, 30) for r in core.risk])
    ax.set_xscale("log")
    ax.set_xlabel("Age-standardised death rate per 100,000 (log scale); arrow = 2010 -> 2023")
    for lab, c in cols.items():
        ax.plot([], [], color=c, lw=2, label=lab)
    ax.legend(loc="lower right")
    ax.set_title("India compared with South Asia and the world, 2010 -> 2023 (20 level-2 risks)\n" + C.DISCLAIMER, fontsize=10)
    fig.savefig(C.FIGURES / "bench_india_vs_world.png")
    plt.close(fig)

    c = t[t.set == "core"]
    summary = dict(
        india_higher_than_world=c[c.india_vs_global_ratio_2023 > 1].sort_values("india_vs_global_ratio_2023", ascending=False)[["risk", "india_vs_global_ratio_2023"]].to_dict("records"),
        india_lower_than_world=c[c.india_vs_global_ratio_2023 < 1].sort_values("india_vs_global_ratio_2023")[["risk", "india_vs_global_ratio_2023"]].to_dict("records"),
        india_worse_trend=c[c.india_worse_trend_than_world][["risk", "india_pct", "global_pct"]].to_dict("records"),
        global_clearly_rising=c[c.global_direction == "clearly rising"].risk.tolist(),
        n_state_pairs_clear_rise_world_falls=int(len(opp)),
        detail_india_up_world_down=t[(t.set == "detail") & (t.india_pct > 0) & (t.global_pct <= 0)][["risk", "india_pct", "global_pct"]].to_dict("records"),
    )
    (C.OUT / "summary").mkdir(exist_ok=True)
    (C.OUT / "summary" / "bench.json").write_text(json.dumps(summary, indent=2, default=float))
    print(c[["risk", "global_2023", "south_asia_2023", "india_2023", "global_pct", "india_pct", "states_above_global_2023"]].round(1).to_string(index=False))
    print(f"  state x risk pairs clearly rising while the world rate fell: {len(opp)}")


if __name__ == "__main__":
    main()
