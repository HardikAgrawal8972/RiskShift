"""Shared helpers: loading frozen data, saving tables/figures, small utilities."""
from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd

from . import config as C


def parse_num(s: pd.Series) -> pd.Series:
    """S14B text numbers -> float. '-' means 'not estimated' -> NaN (never zero)."""
    if s.dtype.kind in "fi":
        return s.astype(float)
    t = s.astype(str).str.replace(",", "", regex=False).str.strip()
    t = t.replace({"-": np.nan, "": np.nan, "nan": np.nan, "None": np.nan})
    return pd.to_numeric(t, errors="raise")


def load_features(include_aggregate: bool = True) -> pd.DataFrame:
    f = pd.read_parquet(C.FEATURES)
    if not include_aggregate:
        f = f[~f["is_aggregate"]]
    return f


def load_india() -> pd.DataFrame:
    return pd.read_parquet(C.FEATURES_INDIA)


def load_sets() -> dict:
    return json.loads(C.SETS_JSON.read_text())


def subset(f: pd.DataFrame, risks: list[str]) -> pd.DataFrame:
    return f[f["risk"].isin(risks)].copy()


def save_table(df: pd.DataFrame, name: str, index: bool = False) -> None:
    df.round(4).to_csv(C.TABLES / f"{name}.csv", index=index)


def wide(f: pd.DataFrame, value: str, risks: list[str] | None = None) -> pd.DataFrame:
    """state x risk matrix (rows ordered by block position, columns in given risk order)."""
    w = f.pivot_table(index="location", columns="risk", values=value, aggfunc="first")
    order = f.drop_duplicates("location").sort_values("block")["location"]
    w = w.loc[[s for s in order if s in w.index]]
    if risks is not None:
        w = w[[r for r in risks if r in w.columns]]
    return w


def log_rate(x):
    return np.log(np.clip(x, C.LOG_FLOOR, None))


def short(risk: str, n: int = 28) -> str:
    rep = {
        "Unsafe water, sanitation, and handwashing": "WASH",
        "Child and maternal malnutrition": "Child/maternal malnutrition",
        "Sexual violence against children and bullying": "Sexual violence vs children",
        "High fasting plasma glucose": "High fasting glucose",
        "High systolic blood pressure": "High systolic BP",
        "Other environmental risks": "Other environmental",
        "Non-optimal temperature": "Non-optimal temperature",
        "Ambient particulate matter pollution": "Ambient PM",
        "Household air pollution from solid fuels": "Household air pollution",
        "Low birth weight and short gestation": "LBW & short gestation",
    }
    s = rep.get(risk, risk)
    return s if len(s) <= n else s[: n - 1] + "…"


def setup_plotting():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "figure.dpi": 110, "savefig.dpi": 150, "savefig.bbox": "tight",
        "font.size": 9, "axes.titlesize": 11, "axes.spines.top": False,
        "axes.spines.right": False,
    })
    return plt


def banner(msg: str) -> None:
    print(f"\n=== {msg} ===", flush=True)
    sys.stdout.flush()
