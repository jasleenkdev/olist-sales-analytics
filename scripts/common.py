"""Shared paths and helpers for the pipeline scripts."""
from pathlib import Path
import re

import duckdb

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
DB_PATH = ROOT / "data" / "olist.duckdb"
SQL_DIR = ROOT / "sql"
OUTPUT_DIR = ROOT / "outputs"
PBI_DATA_DIR = ROOT / "powerbi" / "data"
IMAGES_DIR = ROOT / "images"

# A line like "-- @output: monthly_revenue" marks the start of a block whose
# LAST statement's result is saved to outputs/<name>.csv.
OUTPUT_MARKER = re.compile(r"^--\s*@output:\s*([\w/]+)\s*$", re.MULTILINE)


def connect(read_only: bool = False) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(DB_PATH), read_only=read_only)


def run_sql_file(con, path: Path, out_dir: Path = OUTPUT_DIR) -> list[Path]:
    """Execute a .sql file. Every '-- @output: name' block is run and its final
    result written to out_dir/name.csv. Text before the first marker (setup
    statements such as CREATE VIEW) is executed without saving anything."""
    text = path.read_text()
    parts = OUTPUT_MARKER.split(text)
    preamble, blocks = parts[0], parts[1:]
    if preamble.strip() and _has_sql(preamble):
        con.execute(preamble)
    written = []
    for name, body in zip(blocks[0::2], blocks[1::2]):
        df = con.execute(body).df()
        target = out_dir / f"{name}.csv"
        target.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(target, index=False)
        written.append(target)
    return written


def _has_sql(text: str) -> bool:
    lines = [l for l in text.splitlines() if l.strip() and not l.strip().startswith("--")]
    return bool(lines)
