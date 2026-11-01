"""Download the Olist dataset into data/raw/ with a 3-step fallback chain.

(a) kagglehub.dataset_download("olistbr/brazilian-ecommerce")
(b) Kaggle CLI (needs ~/.kaggle/kaggle.json)
(c) A public mirror of the same files. Set OLIST_MIRROR_URL to a base URL
    that serves the 9 CSVs by their original names.

Whatever the source, the files are checked by name and row count before use.
Skips the download when data/raw/ already holds a verified copy.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

import pandas as pd

from common import RAW_DIR

DATASET = "olistbr/brazilian-ecommerce"
# Row counts (excluding header) of the official Kaggle release, version 2.
EXPECTED_ROWS = {
    "olist_customers_dataset.csv": 99_441,
    "olist_geolocation_dataset.csv": 1_000_163,
    "olist_order_items_dataset.csv": 112_650,
    "olist_order_payments_dataset.csv": 103_886,
    "olist_order_reviews_dataset.csv": 99_224,
    "olist_orders_dataset.csv": 99_441,
    "olist_products_dataset.csv": 32_951,
    "olist_sellers_dataset.csv": 3_095,
    "product_category_name_translation.csv": 71,
}


def verify(folder: Path) -> bool:
    for name, rows in EXPECTED_ROWS.items():
        f = folder / name
        if not f.exists():
            print(f"  missing {name}")
            return False
        got = len(pd.read_csv(f, dtype=str))
        if got != rows:
            print(f"  {name}: expected {rows:,} rows, found {got:,}")
            return False
    return True


def copy_into_raw(src: Path) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for name in EXPECTED_ROWS:
        shutil.copy2(src / name, RAW_DIR / name)


def via_kagglehub() -> Path:
    import kagglehub
    return Path(kagglehub.dataset_download(DATASET))


def via_kaggle_cli() -> Path:
    if not (Path.home() / ".kaggle" / "kaggle.json").exists():
        raise RuntimeError("~/.kaggle/kaggle.json not found")
    out = Path(tempfile.mkdtemp(prefix="olist_kaggle_"))
    subprocess.run(["kaggle", "datasets", "download", "-d", DATASET, "-p", str(out), "--unzip"],
                   check=True)
    return out


def via_mirror() -> Path:
    base = os.environ.get("OLIST_MIRROR_URL")
    if not base:
        raise RuntimeError("OLIST_MIRROR_URL not set")
    out = Path(tempfile.mkdtemp(prefix="olist_mirror_"))
    for name in EXPECTED_ROWS:
        urllib.request.urlretrieve(f"{base.rstrip('/')}/{name}", out / name)
    return out


def main() -> int:
    if RAW_DIR.exists() and verify(RAW_DIR):
        print("data/raw/ already holds a verified copy, skipping download.")
        return 0
    for label, fn in [("kagglehub", via_kagglehub), ("kaggle CLI", via_kaggle_cli),
                      ("public mirror", via_mirror)]:
        print(f"Trying {label} ...")
        try:
            src = fn()
        except Exception as exc:  # noqa: BLE001 - try the next source
            print(f"  {label} failed: {exc}")
            continue
        if verify(src):
            copy_into_raw(src)
            print(f"Downloaded and verified via {label}.")
            return 0
        print(f"  {label} files failed verification")
    print("All download methods failed.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
