"""Tier rules (RQ1) and priority scores (RQ2) - shared with the RQ3 stress tests."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import rankdata

from . import config as C

TIERS = ["Clear worsening", "Possible worsening", "Adverse divergence", "None"]


def tiers(pct_mean, pct_lo, divergence_pct, threshold=C.DIVERGENCE_PP):
    """Tier from GBD's 2010-23 % change interval and the gap to India's % change."""
    pct_mean, pct_lo, divergence_pct = (np.asarray(x, dtype=float) for x in (pct_mean, pct_lo, divergence_pct))
    out = np.full(pct_mean.shape, "None", dtype=object)
    fell = ~(pct_mean > 0)
    out[fell & (divergence_pct >= threshold)] = "Adverse divergence"
    out[(pct_mean > 0)] = "Possible worsening"
    out[(pct_lo > 0)] = "Clear worsening"
    return out


def pct_rank(x) -> np.ndarray:
    """Percentile in (0, 1]: average rank / n (ties share a rank)."""
    x = np.asarray(x, dtype=float)
    return rankdata(x, method="average") / len(x)


def minmax(x) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    rng = np.nanmax(x) - np.nanmin(x)
    return np.zeros_like(x) if rng == 0 else (x - np.nanmin(x)) / rng


def components_cross(asr_2023, abs_change, india_abs_change):
    """Cross-risk components, each a percentile across all pairs being ranked.
    rate = percentile of log ASR 2023; worsening = absolute ASR change (per 100,000, so
    size counts); divergence = absolute-change gap vs India."""
    asr_2023 = np.asarray(asr_2023, float)
    rate = pct_rank(np.log(np.clip(asr_2023, C.LOG_FLOOR, None)))
    wors = pct_rank(abs_change)
    div = pct_rank(np.asarray(abs_change, float) - np.asarray(india_abs_change, float))
    return rate, wors, div


def score_cross(asr_2023, abs_change, india_abs_change, w=None):
    w = w or C.WEIGHTS
    rate, wors, div = components_cross(asr_2023, abs_change, india_abs_change)
    return w["rate"] * rate + w["worsening"] * wors + w["divergence"] * div


def score_within(f: pd.DataFrame, w=None) -> pd.DataFrame:
    """Within-risk score as proposed: min-max per risk of ASR 2023, % change and % divergence."""
    w = w or C.WEIGHTS
    out = f[["location", "risk"]].copy()
    g = f.groupby("risk")
    out["c_rate"] = g["asr_2023_mean"].transform(lambda s: minmax(s))
    out["c_worsening"] = g["pct_2010_23_mean"].transform(lambda s: minmax(s))
    out["c_divergence"] = g["divergence_pct"].transform(lambda s: minmax(s))
    out["score"] = w["rate"] * out.c_rate + w["worsening"] * out.c_worsening + w["divergence"] * out.c_divergence
    return out


def rank_with_floor(score, asr_2023, floor=C.MATERIALITY_ASR) -> np.ndarray:
    """Rank 1 = highest priority. Pairs below the materiality floor are ranked after every
    eligible pair (they cannot enter a top N)."""
    score = np.asarray(score, float)
    eligible = np.asarray(asr_2023, float) >= floor
    key = np.where(eligible, score, score - 10.0)     # scores live in [0,1]
    return rankdata(-key, method="ordinal").astype(int)   # ties broken by row order -> exactly N


def top_n(rank, n) -> np.ndarray:
    return np.asarray(rank) <= n
