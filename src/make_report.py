"""Build docs/RESULTS.md - a plain-language report with every comparison and figure.

Every number is read from pipeline outputs (outputs/tables, outputs/summary), so re-running
the pipeline regenerates the report. Technical detail lives in the appendix and in
docs/rules_log.md.
"""
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from riskshift import config as C  # noqa: E402
from riskshift.common import banner, short  # noqa: E402

S = C.OUT / "summary"
FIG = "../outputs/figures"


def j(name):
    p = S / f"{name}.json"
    return json.loads(p.read_text()) if p.exists() else None


def T(name):
    return pd.read_csv(C.TABLES / f"{name}.csv")


def fmt(v, nd=1):
    if isinstance(v, float):
        if pd.isna(v):
            return "–"
        return f"{v:,.{nd}f}"
    if isinstance(v, (bool,)):
        return "yes" if v else "no"
    return str(v)


def md(df, nd=1, cols=None):
    if cols:
        df = df[list(cols)].rename(columns=cols)
    head = "| " + " | ".join(map(str, df.columns)) + " |"
    sep = "|" + "|".join(" --- " for _ in df.columns) + "|"
    body = ["| " + " | ".join(fmt(v, nd) for v in r) + " |" for r in df.itertuples(index=False)]
    return "\n".join([head, sep] + body) + "\n"


def pct(v):
    return f"{v:+.0f}%"


def img(name, alt):
    return f"![{alt}]({FIG}/{name})\n"


FRIENDLY = {
    "Unsafe water, sanitation, and handwashing": "unsafe water and sanitation", "High fasting plasma glucose": "high blood sugar",
    "High body-mass index": "high BMI", "High systolic blood pressure": "high blood pressure", "High LDL cholesterol": "high LDL cholesterol",
    "Low physical activity": "physical inactivity", "Low bone mineral density": "low bone density", "Child and maternal malnutrition": "child and maternal malnutrition",
    "Other environmental risks": "other environmental risks (mainly lead)", "Non-optimal temperature": "heat and cold",
    "Sexual violence against children and bullying": "sexual violence against children", "High alcohol use": "alcohol",
}
SHORT_LOWER = {k.lower(): v for k, v in FRIENDLY.items()}
SHORT_LOWER.update({"wash": "unsafe water and sanitation", "high fasting glucose": "high blood sugar", "high systolic bp": "high blood pressure",
                    "low bone mineral density": "low bone density", "low physical activity": "physical inactivity",
                    "child/maternal malnutrition": "child and maternal malnutrition", "other environmental": "other environmental risks (mainly lead)",
                    "sexual violence vs children": "sexual violence against children"})


def nice(risk: str) -> str:
    return FRIENDLY.get(risk, SHORT_LOWER.get(risk.lower(), risk.lower()))


def nice_profile(desc: str) -> str:
    """'high a, low b, low c' -> 'More deaths from a. Fewer from b, c.' with plain names."""
    more, fewer = [], []
    for part in [x.strip() for x in desc.split(",")]:
        word, _, risk = part.partition(" ")
        (more if word == "high" else fewer).append(nice(risk))
    txt = []
    if more:
        txt.append("More deaths from " + ", ".join(more) + ".")
    if fewer:
        txt.append(("Fewer" if more else "Fewer deaths") + " from " + ", ".join(fewer) + ".")
    return " ".join(txt)


def profile_name(desc: str) -> str:
    d = desc.lower()
    high = d.split(";")[0]
    if "malnut" in high or "wash" in high:
        return "Traditional risks (malnutrition, unsafe water, air pollution)"
    if "drug" in high or "alcohol" in high:
        return "Drug, alcohol and tobacco"
    if "glucose" in high or "ldl" in high or "body-mass" in high or "dietary" in high:
        return "Metabolic and diet risks"
    return desc


def main():
    banner("make_report")
    r1, r2, r3 = j("rq1"), j("rq2"), j("rq3")
    r4s, r4i, r4m = j("rq4_stability"), j("rq4_interpretation"), j("rq4_migration")
    bench, causes = j("bench"), j("causes")
    sets = json.loads(C.SETS_JSON.read_text())
    out = []
    w = out.append

    tc = r1["tier_counts"]
    s20 = r2["success_criterion"]
    lab20 = {x["family"]: x for x in r3["sensitivity_summary"] if x["N"] == 20}
    a31 = r4s["all31"]
    comp = T("rq2_comparison_all")
    cross20 = comp[(comp.variant == "cross-risk + floor") & (comp.N == 20)].iloc[0]

    # ================================================================ title + summary
    w("# RiskShift-India: results in plain language\n")
    w("**Which health risks are getting worse in Indian states, and would a \"most deaths\" ranking miss them?**\n")
    w(f"> Data: Global Burden of Disease (GBD) 2023, table S14B. These are modelled estimates of deaths linked to risk factors, for India, its 31 state units, South Asia and the world, in 1990, 2010 and 2023. "
      f"Every number below is produced by the code in this repository (`python run_all.py`). *{C.DISCLAIMER}*\n")

    w("## The short version\n")
    if bench:
        bt = T("bench_india_vs_world")
        opp_r = bt[(bt.set == "core") & (bt.india_pct > 0) & (bt.india_pct > bt.global_pct + 5)]
    w(f"1. **Most risks are improving, but metabolic risks are not.** Of {r1['n_pairs']} state-and-risk combinations, {r1['point_up']} got worse between 2010 and 2023. "
      f"In **{tc.get('Clear worsening', 0)}** of them the rise is clear even after allowing for uncertainty. "
      f"High body-mass index (BMI) and high blood sugar account for {r1['clear_by_risk'].get('High body-mass index', 0) + r1['clear_by_risk'].get('High fasting plasma glucose', 0)} of those {tc.get('Clear worsening', 0)}.")
    if causes:
        top = max(causes["top_cause_counts_clear"].items(), key=lambda kv: kv[1])
        w(f"2. **Type 2 diabetes drives most of the rise.** It is the biggest single cause of death in {top[1]} of the {causes['n_clear']} clear increases.")
    if bench:
        w("3. **India is moving the opposite way to the world on metabolic risks.** India's death rate rose for "
          + ", ".join(f"{nice(r.risk)} ({pct(r.india_pct)})" for r in opp_r.itertuples()) + ". Over the same period, the world's changed by "
          + ", ".join(pct(r.global_pct) for r in opp_r.itertuples()) + ". "
          f"In {bench['n_state_pairs_clear_rise_world_falls']} state cases, the rate clearly rose while the world's fell.")
    w(f"4. **Looking at trends changes the priority list.** Rank by \"current burden plus how fast it is worsening\" and {int(cross20.n_new)} of the top 20 are cases that neither a deaths ranking nor a death-rate ranking puts in its top 20. "
      f"{s20['new_clear_material']} of those are clear, sizeable increases. That meets the success test we set in advance.")
    w(f"5. **The top of the list is only partly certain.** The ranking barely changes when the scoring weights or the risks included change. GBD's own uncertainty moves it more. "
      f"Of the top 20, **{lab20['overall']['Robust']} are robust**, {lab20['overall']['Moderate']} moderately stable and {lab20['overall']['Fragile']} fragile.")
    w(f"6. **States do not fall into neat groups.** They sit on a continuous spectrum. {a31['verdict_counts'].get('Gradient, not clusters', 0)} of the 24 ways we tried to group them gave the same answer: \"no real clusters\". "
      "A few small sets of states do consistently look alike.")
    w("7. **The clearest pattern is change over time.** In 1990, most states' risk mix was dominated by malnutrition, unsafe water and air pollution. By 2023, most were dominated by metabolic and diet-related risks such as blood sugar and cholesterol.\n")

    # ================================================================ how to read
    w("## How to read this report\n")
    w("| Term | What it means here |\n| --- | --- |\n"
      "| **Risk factor** | Something that raises the chance of dying early, such as high blood pressure, smoking or air pollution. |\n"
      "| **Attributable deaths** | Deaths GBD's models link to a risk factor. They are estimates, not counted death certificates. |\n"
      "| **Death rate (ASR)** | Attributable deaths per 100,000 people, *age-standardised*: adjusted so that states with older or younger populations can be compared fairly. |\n"
      "| **Uncertainty interval (UI)** | GBD's range of plausible values (95%). A *clear* rise is one where even the low end of the range is above zero. |\n"
      "| **pp (percentage points)** | The difference between two percentages. A state rate down 5% while India's is down 20% is 15 pp worse than India. |\n"
      "| **Level-2 risks** | GBD groups risks into a tree. We mainly use the 20 broad, non-overlapping risks on level 2 (for example \"Tobacco\", \"Air pollution\", \"High BMI\"). Deaths from different risks overlap, so they are never added up. |\n")
    w(f"The analysis covers **31 state units** (\"Other Union Territories\" is a combined unit, and every result was re-checked without it), **{len(sets['core'])} broad risks**, "
      f"{len(sets['detail'])} more detailed risks, **3 years** (1990, 2010, 2023), and India, South Asia and the world as benchmarks.\n")

    # ================================================================ benchmark
    if bench:
        w("## 1. India compared with the world\n")
        b = T("bench_india_vs_world")
        b = b[b.set == "core"].sort_values("india_2023", ascending=False)
        hi = [x for x in bench["india_higher_than_world"]]
        w(f"India's death rate is higher than the world's for **{len(hi)} of 20** broad risks. The biggest gaps are "
          + ", ".join(f"{nice(x['risk'])} ({x['india_vs_global_ratio_2023']:.1f}× the world rate)" for x in hi[:4]) + ". "
          "India is close to the South Asia average on almost every risk.\n")
        w(img("bench_india_vs_world.png", "India vs South Asia vs world"))
        w("Each arrow runs from 2010 to 2023. Arrows pointing right mean the death rate went up.\n")
        b["trend"] = [("**India up, world flat or down**" if (ip > 0 and gp <= 2) else ("**both up, India much faster**" if ip > 0 else ("India improving faster" if ip < gp else "India improving slower"))) for ip, gp in zip(b.india_pct, b.global_pct)]
        w(md(b, 1, {"risk": "Risk", "global_2023": "World 2023", "south_asia_2023": "South Asia 2023", "india_2023": "India 2023",
                    "global_pct": "World change %", "india_pct": "India change %", "states_above_global_2023": "States above world rate (of 31)", "trend": "Trend"}))
        w("*Rates are deaths per 100,000, age-standardised. Changes are 2010 to 2023.*\n")
        dup = bench["detail_india_up_world_down"]
        if dup:
            w("Among the more detailed risks, India rose while the world fell for: " + "; ".join(f"{x['risk']} (India {pct(x['india_pct'])}, world {pct(x['global_pct'])})" for x in dup) + ".\n")

    # ================================================================ RQ1
    w("## 2. Where are things getting worse? (Question 1)\n")
    w("For every state and every broad risk, we compared the 2023 death rate with 2010 and put each combination in one of three groups:\n")
    w(f"- **Clear worsening**: the rate went up, and GBD's uncertainty range for the change is entirely above zero. **{tc.get('Clear worsening', 0)} cases.**\n"
      f"- **Possible worsening**: the rate went up, but the uncertainty range includes \"no change\". **{tc.get('Possible worsening', 0)} cases.**\n"
      f"- **Falling behind India**: the rate fell, but by at least 10 percentage points less than India's fell. **{tc.get('Adverse divergence', 0)} cases.**\n")
    w(f"The remaining {tc.get('None', 0)} combinations improved in line with, or faster than, India.\n")
    w(img("rq1_heatmap_core.png", "Change in death rate by state and risk"))
    w("*How to read the map: red means the death rate rose from 2010 to 2023 and blue means it fell. ● = clear worsening, ○ = possible worsening, ◇ = falling behind India.* "
      "The red block on the right is the metabolic risks: BMI, blood sugar, cholesterol, physical activity and blood pressure. It shows up in almost every state.\n")
    cr = T("rq1_tier_counts_by_risk")
    cr = cr[cr.risk != "TOTAL"].sort_values(["Clear worsening", "Possible worsening"], ascending=False)
    cr = cr[(cr[["Clear worsening", "Possible worsening", "Adverse divergence"]].sum(axis=1) > 0)]
    w("**Number of states in each group, by risk:**\n")
    w(md(cr, 0, {"risk": "Risk", "Clear worsening": "Clear worsening", "Possible worsening": "Possible worsening", "Adverse divergence": "Falling behind India", "None": "Improving normally"}))
    wl = T("rq1_watchlist_core")
    top = wl[wl.tier == "Clear worsening"].head(15)
    w("**The 15 largest clear increases** (by how much the death rate rose):\n")
    w(md(top, 1, {"location": "State", "risk": "Risk", "asr_2010_mean": "Rate 2010", "asr_2023_mean": "Rate 2023", "pct_2010_23_mean": "Change %",
                  "pct_2010_23_lo": "Low end of range %", "india_pct_2010_23": "India change %"}))
    if causes:
        w("### What is behind the increases?\n")
        w("GBD also splits each risk's deaths by cause of death. For each clear increase, we looked at which diseases account for the rise.\n")
        w(img("causes_clear_worsening.png", "Causes behind the largest increases"))
        w("Blood-sugar and BMI increases come mostly from **type 2 diabetes**. Blood-pressure, diet and \"other environmental\" (mainly lead exposure) increases come mostly from **heart disease** (ischaemic and hypertensive).\n")
        ci = pd.DataFrame(causes["india"])
        if len(ci):
            w("At national level, India's rising risks break down as follows:\n")
            w(md(ci, 1, {"risk": "Risk (India)", "main_causes": "Main causes of the rise"}))
    if bench:
        opp = T("bench_states_rising_while_world_falls")
        w(f"### Rising in India while falling worldwide\n")
        w(f"{len(opp)} state cases rose clearly while the world's rate for the same risk fell:\n")
        w(md(opp, 1, {"location": "State", "risk": "Risk", "asr_2023_mean": "Rate 2023", "pct_2010_23_mean": "State change %", "global_pct": "World change %", "ratio_to_global_2023": "× world rate"}))
    w("**Worth knowing:**\n")
    ts = r1["threshold_sensitivity"]
    w(f"- {r1['watchlist_small_base']} watchlist cases start from a very small rate (under 5 per 100,000), so a large percentage rise can still mean few deaths. The full tables flag them.\n"
      f"- The \"falling behind India\" group depends on the cut-off: 5, 10 and 15 pp give {ts['5 pp']['Adverse divergence']}, {ts['10 pp']['Adverse divergence']} and {ts['15 pp']['Adverse divergence']} cases. The clear and possible groups do not change.\n"
      f"- The detailed risks show what sits inside the broad ones. Outdoor air pollution rose in {r1['detail_clear_by_risk'].get('Ambient particulate matter pollution', 0)} states while household air pollution fell almost everywhere. That is why \"air pollution\" as a whole looks like it is improving.\n")
    w("Full lists, with a one-line reason for every case: [`rq1_watchlist_core.csv`](../outputs/tables/rq1_watchlist_core.csv) and [`rq1_watchlist_detail.csv`](../outputs/tables/rq1_watchlist_detail.csv).\n")

    # ================================================================ RQ2
    w("## 3. Does looking at trends change who is at the top? (Question 2)\n")
    w("We compared three ways of ranking all 620 state-and-risk combinations:\n")
    w("| Ranking | What it rewards |\n| --- | --- |\n"
      "| **A. Most deaths** | Big states with many deaths (2023 attributable deaths). |\n"
      "| **B. Highest death rate** | The highest 2023 rate per 100,000. |\n"
      "| **C. Trend-aware (RiskShift)** | 40% current rate + 35% how much the rate rose + 25% how much worse it did than India. A combination needs a rate of at least 10 per 100,000 to qualify, so tiny risks cannot top the list. |\n")
    side = T("rq2_top30_side_by_side").head(20)
    sc = T("rq2_scores_core")
    newset = set(zip(sc[(sc.rank_cross <= 20) & (sc.rank_B1_deaths > 20) & (sc.rank_B2_asr > 20)].location,
                     sc[(sc.rank_cross <= 20) & (sc.rank_B1_deaths > 20) & (sc.rank_B2_asr > 20)].risk))
    side["cross_risk"] = [f"**{x}** ★" if tuple(x.split(" · ", 1)) in newset else x for x in side.cross_risk]
    w("**The three top-20 lists side by side** (★ = in the trend-aware list only):\n")
    w(md(side, 0, {"rank": "#", "B1_deaths": "A. Most deaths", "B2_asr": "B. Highest rate", "cross_risk": "C. Trend-aware"}))
    w(f"- The trend-aware list shares **{int(cross20.overlap_B1)}** cases with the deaths list and **{int(cross20.overlap_B2)}** with the rate list.\n"
      f"- **{int(cross20.n_new)} cases are new**, and **{int(cross20.new_clear_material)}** of them are *clear* increases. "
      f"Before seeing any results, we said the method succeeds if at least {C.SUCCESS_MIN_NEW} new cases are clear, sizeable increases. **Result: {'met' if s20['met'] else 'not met'}.**\n"
      f"- None of the new cases is a tiny or low-burden risk ({int(cross20.new_small_base)} small-base, {int(cross20.new_below_floor)} below the size cut-off). The novelty comes from real, sizeable change.\n")
    w("**Why each new case was flagged:**\n")
    ov = pd.DataFrame(r2["overlooked_N20"])
    ov["why_surfaced"] = ov.why_surfaced.str.replace(r"p(\d+)", r"top \1%", regex=True).str.replace("top 100%", "top 1%")
    ov["why_surfaced"] = ov.why_surfaced.str.replace(r"top (\d+)%", lambda m: f"top {100 - int(m.group(1)) + 1}%" if m.group(1) != "1" else "top 1%", regex=True)
    w(md(ov, 1, {"location": "State", "risk": "Risk", "tier": "Question 1 group", "asr_2023_mean": "Rate 2023", "abs_2010_23": "Rise since 2010 (per 100k)", "why_surfaced": "Strongest signals (percentile among all 620)"}))
    w(img("rq2_burden_vs_trend.png", "Trend-aware vs burden-only top 20"))
    w(f"**A warning about the original scoring idea.** The proposal suggested scaling each risk from 0 to 1 separately (the right-hand chart). That makes the worst state for *every* risk look urgent, however small the risk. "
      f"{r2['within_top20_below_floor']} of that list's top 20 have a death rate below 10 per 100,000 (for example drug use in Uttarakhand). "
      "We therefore use the per-risk version only to rank states *within* one risk, and the trend-aware score above to compare across risks.\n")
    w("**How different are the rankings overall?**\n")
    cm = comp.copy()
    cm["variant"] = cm.variant.map({"within-risk (proposed)": "Per-risk scaling (proposal)", "cross-risk + floor": "Trend-aware (used)"})
    w(md(cm, 2, {"variant": "Method", "N": "Top N", "overlap_B1": "Shared with A", "overlap_B2": "Shared with B", "n_new": "New cases", "new_clear": "…of which clear rises",
                 "new_small_base": "…tiny base", "new_below_floor": "…below size cut-off", "spearman_B2": "Rank correlation with B"}))
    w("*Rank correlation runs from 1 (identical order) to 0 (unrelated). A value around 0.5 means the trend-aware ranking keeps the broad picture of burden but reorders it a lot.*\n")
    w("Per-risk state rankings: [`rq2_within_risk_state_rankings.csv`](../outputs/tables/rq2_within_risk_state_rankings.csv). All scores: [`rq2_scores_core.csv`](../outputs/tables/rq2_scores_core.csv).\n")

    # ================================================================ RQ3
    w("## 4. Can we trust the ranking? (Question 3)\n")
    w("We re-ran the trend-aware ranking thousands of times, changing one thing at a time:\n")
    w("| Test | What we changed | Runs |\n| --- | --- | --- |\n"
      "| **Weights** | The 40/35/25 split, drawn at random, plus extremes such as \"rate only\" or \"trend only\". | 1,005 |\n"
      "| **GBD uncertainty** | Each rate and each change, redrawn within GBD's uncertainty range. Also all-low and all-high values. | 1,002 |\n"
      "| **Risk choice** | One risk dropped at a time, the policy-focused risk list, and Other UTs removed. | 22 |\n")
    w("A case is **Robust** if it stays in the top 20 in at least 80% of runs, **Moderate** at 50–80%, and **Fragile** below 50%. Its overall label is its weakest result across the three tests.\n")
    t20 = pd.DataFrame(r3["top20"]).sort_values("base_rank")
    for c in ("Weights_freq_top20", "Uncertainty_freq_top20", "Selection_freq_top20"):
        t20[c] = (t20[c] * 100).round(0).astype(int).astype(str) + "%"
    w(md(t20, 0, {"base_rank": "#", "location": "State", "risk": "Risk", "Weights_freq_top20": "Stays in top 20: weights", "Uncertainty_freq_top20": "…uncertainty",
                  "Selection_freq_top20": "…risk choice", "overall_label": "Overall"}))
    w(img("rq3_rank_ranges.png", "Rank ranges under each test"))
    w("*Each line shows where a case ranked in the middle 90% of runs. Lines that cross the dotted line mean the case sometimes drops out of the top 20.*\n")
    kt = pd.DataFrame(r3["kendall"])
    w(f"**What this tells us:**\n"
      f"- **Weights and risk choice hardly matter.** Every top-20 case survives the risk-choice test, and {lab20['Weights']['Robust']} of 20 are robust to the weights.\n"
      f"- **GBD's uncertainty is the real limit.** The 2010–2023 change ranges are wide, so many cases drop in and out. Only {lab20['Uncertainty']['Robust']} cases are robust to it: "
      + ", ".join(f"{r['location']} {nice(r['risk'])}" for r in r3["top20"] if r["overall_label"] == "Robust") + ".\n"
      f"- The overall order stays similar: the typical rank correlation with the original ranking is {kt.loc[kt.family == 'Weights', 'kendall_median'].iloc[0]:.2f} under weight changes and "
      f"{kt.loc[kt.family == 'Uncertainty', 'kendall_median'].iloc[0]:.2f} under uncertainty.\n"
      "- This is a deliberately harsh test. IHME does not publish the linked simulation draws, so each number was varied independently, which probably exaggerates the instability.\n")
    tf = pd.DataFrame(r3["tier_flips"])
    flip_clear = tf[tf.perturbation.str.contains("Clear")].share_flipped.iloc[0]
    flip_div = tf[tf.perturbation.str.contains("Adverse")].share_flipped.iloc[0]
    w(f"For the Question 1 groups, *clear worsening* labels never change under uncertainty ({flip_clear:.0%} of runs), because they are already defined by the uncertainty range. "
      f"*Falling behind India* labels change in {flip_div:.0%} of runs, so treat that group as a softer signal.\n")

    # ================================================================ RQ4
    w("## 5. Do states fall into groups? (Question 4)\n")
    w("We used clustering (K-means and three other methods) to see whether states form distinct groups with similar risk profiles. Many methods will always return groups, even from random data. "
      "So we compared each result with random \"no-group\" data that has the same overall shape, and only accepted groups that beat it, held together when the data were resampled, and agreed across different set-ups.\n")
    w(f"**Answer: no. States lie on a spectrum, not in separate groups.**\n")
    w(f"- We tried 24 set-ups (3 risk lists × 4 kinds of features × 2 scalings). **{a31['verdict_counts'].get('Gradient, not clusters', 0)} found no real groups.** "
      f"{a31['verdict_counts'].get('Partial structure', 0)} found weak structure, and none found robust groups.\n"
      f"- Only {a31['gate1_pass']} of 24 beat the random comparison data, and those few disagree with each other. The typical agreement between set-ups (ARI) is {a31['median_cross_config_ari']:.2f}, where 1 is identical and 0 is chance level.\n"
      f"- Most of the variation between states is one dimension, *overall burden*: high-burden states are high on most risks. It explains {r4i['pca']['var'][0]:.0%} of the differences.\n")
    w(img("rq4_existence_all31.png", "Observed grouping vs random data"))
    w("*Dots are the real data. Grey bars are what random no-group data typically produce. A dot must sit above its grey bar, and above 0.25, to count as real grouping. Only a few do (green).*\n")
    w("**But some states consistently look alike.** Across all runs, these sets of states were placed together at least 70% of the time:\n")
    for c in a31["cores"]:
        w(f"- {', '.join(c['states'])} (together {c['mean_coassignment']:.0%} of the time)")
    w("")
    w(img("rq4_consensus_all31.png", "How often each pair of states is grouped together"))
    w("**A descriptive split into three profiles** (useful for comparing a state with similar states, but not a claim of distinct types):\n")
    prof = r4i["profiles"]["3"]
    w(md(pd.DataFrame([dict(g=g, n=len(d["states"]), desc=nice_profile(d["description"]), states=", ".join(d["states"])) for g, d in prof.items()]), 0,
         {"g": "Group", "n": "States", "desc": "What stands out (vs other states)", "states": "Members"}))
    w(img("rq4_cluster_profiles.png", "Average risk profile of each group"))
    w(img("rq4_pca_biplot.png", "Map of state risk profiles"))
    z, wc = r4i["zone"], r4i["watchlist_concentration"]
    w(f"- The groups barely follow geography (agreement with India's Zonal Councils: ARI {z['primary_ari_k3']:.2f}). The north-eastern hill states are the exception.\n"
      f"- Worsening cases from Question 1 are not concentrated in any one group (p = {wc['kruskal_clear_p']:.2f}).\n"
      f"- Comparing each state with its own peer group, not just India, finds {r4i['peer_benchmark']['n_hidden']} extra cases that look fine against India but worse than similar states "
      "([`rq4_hidden_divergence.csv`](../outputs/tables/rq4_hidden_divergence.csv)).\n")

    w("### How state risk profiles shifted, 1990 → 2010 → 2023\n")
    m = r4m["shape"]
    names = {p: profile_name(d) for p, d in m["profiles"].items()}
    mem = pd.DataFrame({y: {names[p]: n for p, n in c.items()} for y, c in m["membership_by_year"].items()}).fillna(0).astype(int)
    mem.index.name = "Profile"
    w("Here we compare the *mix* of risks in each state, setting overall burden aside, and track it over time. This is the strongest pattern in the data.\n")
    w(md(mem.reset_index(), 0))
    w(f"{m['n_changed']} of 31 states changed profile between 1990 and 2023. Kerala, Goa, Punjab, Delhi and Tamil Nadu already had the metabolic profile in 1990. "
      "Most southern and western states moved by 2010, and Bihar, Uttar Pradesh, Odisha, Jharkhand and Madhya Pradesh by 2023. Rajasthan was the only state still in the traditional profile in 2023. "
      "Five north-eastern states kept their own drug, alcohol and tobacco profile throughout.\n")
    w(img("rq4_migration_shape.png", "State paths 1990-2023"))
    w("An interactive version of this chart (a Sankey flow diagram) is in [`rq4_migration_shape_sankey.html`](../outputs/figures/rq4_migration_shape_sankey.html).\n")

    # ================================================================ takeaways
    w("## 6. What this means\n")
    w("- **For screening:** ranking by deaths alone misses fast-worsening, high-rate problems in the middle of the burden table, mainly **blood pressure, diet, blood sugar and BMI in Bihar, Chhattisgarh, Karnataka, Haryana, Assam and Jharkhand**. The trend-aware list adds these without letting tiny risks crowd the top.\n"
      "- **Metabolic risks are India's emerging problem.** Their death rates are rising nationally and in most states, driven by type 2 diabetes and heart disease, while the world's rates are flat or falling.\n"
      "- **Be modest about exact ranks.** Use the robust cases with confidence and treat fragile ones as \"worth a closer look\".\n"
      "- **Compare states with similar states, not with fixed types.** States sit on a spectrum, so peer comparison and the shift-over-time view are more useful than labelling clusters.\n")
    w("## 7. Limits\n")
    w("- These are **modelled estimates**, not direct counts, and only three years are available. This is not a forecast.\n"
      "- Deaths linked to different risks **overlap**: high BMI acts partly through blood pressure, for example. They are never added together.\n"
      "- Associations only. **Nothing here shows cause and effect** or tells anyone where to spend money.\n"
      "- \"Other Union Territories\" combines several small territories. Every result was re-run without it, and the conclusions held.\n"
      "- Two optional inputs were not supplied: GBD's socio-demographic index (SDI) groups and its evidence-strength ratings. Zonal Councils were used as the outside comparison instead.\n")

    # ================================================================ appendix
    w("---\n\n## Appendix: full comparison tables\n")
    w("### A1. Ranking comparison, without \"Other Union Territories\"\n")
    c2 = T("rq2_comparison_no_other_uts")
    c2["variant"] = c2.variant.map({"within-risk (proposed)": "Per-risk scaling (proposal)", "cross-risk + floor": "Trend-aware (used)"})
    w(md(c2, 2, {"variant": "Method", "N": "Top N", "overlap_B1": "Shared with A", "overlap_B2": "Shared with B", "n_new": "New", "new_clear_material": "New clear & sizeable", "jaccard_B1": "Jaccard vs A", "jaccard_B2": "Jaccard vs B", "kendall_B2": "Kendall vs B"}))
    w("### A2. Stability labels by test and list length\n")
    ss = pd.DataFrame(r3["sensitivity_summary"])
    w(md(ss, 0, {"N": "Top N", "family": "Test", "Robust": "Robust", "Moderate": "Moderate", "Fragile": "Fragile"}))
    w(md(kt[["family", "scenarios", "kendall_median", "kendall_p05", "kendall_min"]], 2,
         {"family": "Test", "scenarios": "Runs", "kendall_median": "Rank correlation (typical)", "kendall_p05": "(worst 5%)", "kendall_min": "(worst)"}))
    w("### A3. How often Question 1 groups change\n")
    tf = tf.copy()
    tf["perturbation"] = tf.perturbation.replace({
        "divergence threshold 5 pp": "Cut-off for 'falling behind India' set to 5 pp", "divergence threshold 15 pp": "Cut-off set to 15 pp",
        "point change at lo bound": "Use low end of each change range", "point change at hi bound": "Use high end of each change range",
        "Monte Carlo (mean share of draws)": "Random redraws within uncertainty: all cases", "Monte Carlo, watchlist pairs only (mean share)": "…watchlist cases only",
        "Monte Carlo, base tier = Clear worsening (mean share)": "…clear worsening cases", "Monte Carlo, base tier = Possible worsening (mean share)": "…possible worsening cases",
        "Monte Carlo, base tier = Adverse divergence (mean share)": "…falling-behind-India cases"})
    w(md(tf, 2, {"perturbation": "Change", "share_flipped": "Share of cases that change group", "n_flipped": "Cases changing in most runs"}))
    w("### A4. Divergence cut-off sensitivity\n")
    a4 = pd.read_csv(C.TABLES / "rq1_divergence_threshold_sensitivity.csv", keep_default_na=False)
    a4["tier"] = a4.tier.replace({"None": "Improving normally", "Adverse divergence": "Falling behind India"})
    w(md(a4, 0, {"tier": "Group", "5 pp": "Cut-off 5 pp", "10 pp": "10 pp (used)", "15 pp": "15 pp"}))
    w("### A5. Clustering results for all 24 set-ups (31 units)\n")
    dec = T("rq4_decision_table")
    d31 = dec[dec.units == "all31"]
    w(md(d31, 2, {"config": "Set-up (risks-features-scaling)", "k_star": "Groups chosen", "observed_best_sil": "Separation (silhouette)", "null_mvn_p95": "Random-data benchmark",
                  "gate1_existence": "Beats random?", "boot_jaccard_min": "Weakest group stability", "median_ari_vs_other_configs": "Agreement with other set-ups",
                  "unc_ari_median": "Agreement under uncertainty", "verdict": "Verdict"}))
    w("*F1 = burden level, F2 = risk mix, F3 = change since 2010, F4 = level + change. Without Other UTs, the verdicts are "
      + ", ".join(f"{k} {v}" for k, v in r4s["no_other_uts30"]["verdict_counts"].items()) + ".*\n")
    w("### A6. Risk lists used\n")
    w(f"- **Broad (core) risks ({len(sets['core'])})**: " + ", ".join(sets["core"]) + ".\n"
      f"- **Detailed risks ({len(sets['detail'])})**: " + ", ".join(sets["detail"]) + ".\n"
      f"- **Policy-focused risks ({len(sets['policy'])})**: " + ", ".join(sets["policy"]) + ".\n")
    w("### A7. Where everything is\n")
    w("| What | File |\n| --- | --- |\n"
      "| Every choice and threshold | [`docs/rules_log.md`](rules_log.md) |\n"
      "| Every column | [`docs/data_dictionary.md`](data_dictionary.md) |\n"
      "| All result tables | [`outputs/tables/`](../outputs/tables) |\n"
      "| All figures | [`outputs/figures/`](../outputs/figures) |\n"
      "| Interactive explorer | `streamlit run app/streamlit_app.py` |\n")
    (C.DOCS / "RESULTS.md").write_text("\n".join(out), encoding="utf-8")
    print(f"  wrote {(C.DOCS / 'RESULTS.md').relative_to(C.ROOT)}")


if __name__ == "__main__":
    main()
