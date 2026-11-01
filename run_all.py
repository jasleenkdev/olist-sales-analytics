"""Rebuild the whole project from raw data.

    python run_all.py           # download if needed, then rebuild everything
    python run_all.py --clean   # first delete every generated artifact
                                # (database, outputs, exports, PBIP, charts)

Steps: download -> load + row-count check -> data quality -> analysis ->
star schema views + CSV export -> Power BI project -> PBIP validation ->
charts -> README number verification. Stops at the first failing step.
"""
import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCRIPTS = ROOT / "scripts"

STEPS = [
    ("Download data", "download_data.py"),
    ("Load database", "load_data.py"),
    ("Data quality checks", "run_quality.py"),
    ("SQL analysis", "run_analysis.py"),
    ("Star schema views + exports", "build_views.py"),
    ("Power BI project", "build_pbip.py"),
    ("Validate Power BI project", "validate_pbip.py"),
    ("Charts", "make_charts.py"),
    ("Verify README figures", "verify_readme.py"),
]

GENERATED = [
    "data/olist.duckdb", "outputs", "powerbi/data",
    "powerbi/OlistSalesAnalytics/OlistSalesAnalytics.SemanticModel",
    "powerbi/OlistSalesAnalytics/OlistSalesAnalytics.Report",
    "powerbi/OlistSalesAnalytics/OlistSalesAnalytics.pbip",
    "images", "docs/powerbi_build_guide.md",
]


def clean() -> None:
    for rel in GENERATED:
        p = ROOT / rel
        if p.is_dir():
            shutil.rmtree(p)
        elif p.exists():
            p.unlink()
    print("Removed generated artifacts.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--clean", action="store_true", help="delete generated artifacts first")
    args = ap.parse_args()
    if args.clean:
        clean()
    start = time.time()
    for i, (label, script) in enumerate(STEPS, 1):
        print(f"\n=== [{i}/{len(STEPS)}] {label} ===", flush=True)
        t = time.time()
        result = subprocess.run([sys.executable, str(SCRIPTS / script)], cwd=SCRIPTS)
        if result.returncode != 0:
            print(f"\nFAILED at step {i}: {label} (exit code {result.returncode})")
            return result.returncode
        print(f"--- done in {time.time() - t:.1f}s")
    print(f"\nAll {len(STEPS)} steps completed in {time.time() - start:.0f}s.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
