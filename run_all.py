"""Run the full RiskShift-India pipeline in order (fixed seeds; ~5 minutes on a laptop).

    python run_all.py            # re-extract from the raw XLSX
    python run_all.py --reuse    # reuse data/interim/s14b_india_extract.csv if present
"""
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STEPS = ["01_extract.py", "02_annotate.py", "03_sets.py", "04_features.py",
         "rq1_watchlist.py", "rq2_prioritise.py", "rq3_stability.py",
         "rq4_features.py", "rq4_cluster_grid.py", "rq4_null.py", "rq4_stability.py",
         "rq4_migration.py", "rq4_figures.py", "make_report.py"]

if __name__ == "__main__":
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONWARNINGS="ignore")
    t0 = time.time()
    for s in STEPS:
        args = [sys.executable, str(ROOT / "src" / s)]
        if s == "01_extract.py" and "--reuse" in sys.argv:
            args.append("--reuse")
        r = subprocess.run(args, env=env, cwd=ROOT)
        if r.returncode:
            sys.exit(f"step {s} failed")
    print(f"\nAll steps finished in {time.time() - t0:.0f}s")
