"""01_extract - stream S14B once and slice India + 31 state units by block position.

The sheet is ~950 MB of XML (595,020 data rows = 705 location blocks x 844 rows).
We stream it with iterparse, keep only blocks 353-384 (India and its 31 state units),
and stop as soon as the last India block has been read. Locations are keyed by block
position, never by name ("Punjab" exists for both India and Pakistan).

Output: data/interim/s14b_india_extract.csv and s14b_benchmarks_extract.csv (Global and
South Asia blocks, the external benchmarks) - text values exactly as published; parsing
happens in 02_annotate). If the supplied pilot extract is present, the new extract is
cross-checked against it cell by cell.

Usage:  python src/01_extract.py            (re-extract from the XLSX if present)
        python src/01_extract.py --reuse    (skip if the extract already exists)
"""
import sys
import time
import zipfile
from pathlib import Path
from xml.etree.ElementTree import iterparse

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from riskshift import config as C  # noqa: E402
from riskshift.common import banner, parse_num  # noqa: E402

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
VALUE_COLS = [f"{m}_{y}_{s}" for m in C.MEASURES for y in C.YEARS for s in C.STATS] + [
    f"pct_{m}_2010_23_{s}" for m in ("deaths", "asr") for s in C.STATS
]
COLS = ["risk_outcome", "location"] + VALUE_COLS  # sheet columns A..AI


def col_index(ref: str) -> int:
    letters = "".join(ch for ch in ref if ch.isalpha())
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def shared_strings(z: zipfile.ZipFile) -> list[str]:
    out = []
    for _, el in iterparse(z.open("xl/sharedStrings.xml")):
        if el.tag == NS + "si":
            out.append("".join(t.text or "" for t in el.iter(NS + "t")))
            el.clear()
    return out


def extract(xlsx: Path) -> pd.DataFrame:
    first = C.FIRST_DATA_ROW + C.INDIA_BLOCKS[0] * C.ROWS_PER_BLOCK
    last = C.FIRST_DATA_ROW + (C.INDIA_BLOCKS[-1] + 1) * C.ROWS_PER_BLOCK - 1
    z = zipfile.ZipFile(xlsx)
    ss = shared_strings(z)
    rows = []
    t0 = time.time()
    for _, el in iterparse(z.open("xl/worksheets/sheet1.xml")):
        if el.tag != NS + "row":
            continue
        r = int(el.get("r"))
        keep_bench = r >= C.FIRST_DATA_ROW and (r - C.FIRST_DATA_ROW) // C.ROWS_PER_BLOCK in C.BENCHMARK_BLOCKS
        if r >= first or keep_bench:
            vals = [None] * len(COLS)
            for c in el.iter(NS + "c"):
                j = col_index(c.get("r"))
                if j >= len(COLS):
                    continue
                t = c.get("t")
                if t == "inlineStr":
                    v = "".join(x.text or "" for x in c.iter(NS + "t"))
                else:
                    ve = c.find(NS + "v")
                    v = None if ve is None else ve.text
                    if v is not None and t == "s":
                        v = ss[int(v)]
                vals[j] = v
            vals.append(r - C.FIRST_DATA_ROW)  # row_idx (0-based data row)
            rows.append(vals)
        el.clear()
        if r % 50000 == 0:
            print(f"  row {r:,}  ({time.time() - t0:.0f}s)", flush=True)
        if r >= last:
            break
    df = pd.DataFrame(rows, columns=COLS + ["row_idx"])
    df["block"] = df["row_idx"] // C.ROWS_PER_BLOCK
    df["row_in_block"] = df["row_idx"] % C.ROWS_PER_BLOCK
    # Risk total rows read "<risk>: All causes"; the cause sub-rows beneath carry only the
    # cause name, so the risk is carried forward from the last total row.
    ro = df.pop("risk_outcome").str.strip()
    is_total = ro.str.endswith(": All causes")
    risk = ro.str.slice(0, -len(": All causes")).where(is_total).ffill()
    df.insert(0, "risk", risk.str.strip())
    df.insert(1, "outcome", ro.where(~is_total, "All causes").str.strip())
    df["is_outcome"] = ~is_total
    df["location"] = df["location"].str.strip()
    for c in VALUE_COLS:
        df[c] = df[c].astype(str).str.strip()
    print(f"  extracted {len(df):,} rows in {time.time() - t0:.0f}s")
    return df


def validate(df: pd.DataFrame) -> None:
    assert len(df) == len(C.INDIA_BLOCKS) * C.ROWS_PER_BLOCK, len(df)
    assert df.groupby("block")["location"].nunique().eq(1).all(), "location changes inside a block"
    assert df.loc[df.block == C.INDIA_BLOCK, "location"].iloc[0] == "India"
    if not C.PROTOTYPE_EXTRACT.exists():
        print("  (no pilot extract to cross-check)")
        return
    p = pd.read_csv(C.PROTOTYPE_EXTRACT).sort_values("row_idx").reset_index(drop=True)
    d = df.sort_values("row_idx").reset_index(drop=True)
    assert (p["row_idx"].values == d["row_idx"].values).all(), "row_idx mismatch vs pilot"
    for c in ["location", "risk", "outcome"]:
        bad = (p[c].astype(str) != d[c].astype(str)).sum()
        assert bad == 0, f"{c}: {bad} mismatches vs pilot"
    worst = 0.0
    for c in VALUE_COLS:
        a, b = parse_num(d[c]), parse_num(p[c])
        assert (a.isna() == b.isna()).all(), f"{c}: missingness differs vs pilot"
        worst = max(worst, float(np.nanmax(np.abs(a - b))))
    print(f"  cross-check vs pilot extract: identical keys, max |diff| = {worst:g}")


def main():
    banner("01_extract")
    if "--reuse" in sys.argv and C.EXTRACT_CSV.exists() and (C.BENCH_CSV.exists() or not C.RAW_XLSX.exists()):
        print(f"  reusing {C.EXTRACT_CSV.relative_to(C.ROOT)}")
        return
    if C.RAW_XLSX.exists():
        allrows = extract(C.RAW_XLSX)
        bench = allrows[allrows.block.isin(list(C.BENCHMARK_BLOCKS))].copy()
        for b, name in C.BENCHMARK_BLOCKS.items():
            got = bench.loc[bench.block == b, "location"].unique().tolist()
            assert got == [name] and (bench.block == b).sum() == C.ROWS_PER_BLOCK, (b, got)
        bench.to_csv(C.BENCH_CSV, index=False)
        print(f"  wrote {C.BENCH_CSV.relative_to(C.ROOT)}  {bench.shape}  (benchmarks: {', '.join(C.BENCHMARK_BLOCKS.values())})")
        df = allrows[allrows.block.isin(C.INDIA_BLOCKS)].reset_index(drop=True)
    else:
        print("  raw XLSX not found; falling back to the supplied pilot extract (no Global/South Asia benchmarks)")
        p = pd.read_csv(C.PROTOTYPE_EXTRACT)
        df = p[["risk", "outcome", "location"] + VALUE_COLS + ["row_idx", "block", "is_outcome"]].copy()
        df["row_in_block"] = df["row_idx"] % C.ROWS_PER_BLOCK
    validate(df)
    df.to_csv(C.EXTRACT_CSV, index=False)
    print(f"  wrote {C.EXTRACT_CSV.relative_to(C.ROOT)}  {df.shape}")


if __name__ == "__main__":
    main()
