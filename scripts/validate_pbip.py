"""Validate the generated Power BI Project.

1. JSON: every .json/.pbip/.pbir/.pbism file parses. Files that declare a
   Microsoft "$schema" are validated against it (draft-07). Schemas are
   downloaded from developer.microsoft.com once and cached in .cache/schemas/.
   Offline, schema validation is skipped with a warning and syntax checks
   still run.
2. TMDL: a structural lint, since there is no official TMDL parser outside
   Power BI / Tabular Editor:
     - tab-only indentation, no indentation jumps outside expressions
     - every line starts with a known TMDL keyword at its level
     - relationships, sortByColumn and DAX table[column] / [measure]
       references point at objects that exist
     - each partition's M column list equals its CSV header
     - dim_date is marked as a date table (dataCategory: Time + isKey)
3. Report: every field a visual uses exists in the model.
Exit code 1 on any error.
"""
import json
import re
import sys
import urllib.request
from pathlib import Path

from jsonschema import Draft7Validator
from referencing import Registry, Resource

from common import PBI_DATA_DIR, ROOT

PBIP = ROOT / "powerbi" / "OlistSalesAnalytics"
CACHE = ROOT / ".cache" / "schemas"
errors: list[str] = []


def err(msg: str) -> None:
    errors.append(msg)


# ------------------------------------------------------------------ JSON
def fetch_schema(uri: str) -> dict:
    local = CACHE / re.sub(r"^https?://", "", uri.split("#")[0])
    if not local.exists():
        local.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(uri, timeout=30) as r:
            local.write_bytes(r.read())
    return json.loads(local.read_text())


def retrieve(uri: str) -> Resource:
    return Resource.from_contents(fetch_schema(uri))


def check_json() -> int:
    registry = Registry(retrieve=retrieve)
    files = [p for p in PBIP.rglob("*") if p.suffix in {".json", ".pbip", ".pbir", ".pbism"}]
    files.append(ROOT / "powerbi" / "theme" / "OlistTheme.json")
    online = True
    validated = 0
    for f in files:
        try:
            doc = json.loads(f.read_text())
        except json.JSONDecodeError as e:
            err(f"JSON syntax {f.relative_to(ROOT)}: {e}")
            continue
        uri = doc.get("$schema") if isinstance(doc, dict) else None
        if not uri or not online:
            continue
        try:
            schema = fetch_schema(uri)
        except Exception as e:  # noqa: BLE001
            print(f"WARNING: cannot download schemas ({e}); JSON syntax checked only")
            online = False
            continue
        v = Draft7Validator(schema, registry=registry)
        for e in sorted(v.iter_errors(doc), key=lambda e: list(e.path)):
            err(f"schema {f.relative_to(ROOT)} at /{'/'.join(map(str, e.path))}: {e.message[:300]}")
        validated += 1
    print(f"JSON: {len(files)} files parsed, {validated} validated against Microsoft schemas")
    return len(files)


# ------------------------------------------------------------------ TMDL
TOP = {"table", "relationship", "expression", "model", "database", "annotation", "ref", "///",
       "cultureInfo"}
OBJ = {"column", "measure", "partition", "hierarchy", "annotation", "lineageTag", "dataCategory",
       "isHidden", "description", "///", "fromColumn", "toColumn", "crossFilteringBehavior",
       "isActive", "culture", "defaultPowerBIDataSourceVersion", "discourageImplicitMeasures",
       "sourceQueryCulture", "dataAccessOptions", "compatibilityLevel", "queryGroup"}
PROP = {"dataType", "isKey", "formatString", "isHidden", "lineageTag", "summarizeBy",
        "sourceColumn", "sortByColumn", "annotation", "displayFolder", "mode", "source",
        "description", "dataCategory", "legacyRedirects", "returnErrorValuesAsNull", "///"}


def lint_tmdl(path: Path) -> None:
    rel = path.relative_to(ROOT)
    in_expr_at = None  # indentation level of the property that opened a multi-line expression
    prev_level = 0
    for n, raw in enumerate(path.read_text().splitlines(), 1):
        if not raw.strip():
            continue
        if raw.startswith(" "):
            err(f"{rel}:{n} indented with spaces")
            continue
        level = len(raw) - len(raw.lstrip("\t"))
        word = raw.strip().split(" ")[0].rstrip(":")
        if in_expr_at is not None:
            if level > in_expr_at:
                continue  # inside an M or DAX block
            in_expr_at = None
        if level > prev_level + 1:
            err(f"{rel}:{n} indentation jumps from {prev_level} to {level}")
        allowed = TOP if level == 0 else OBJ if level == 1 else PROP
        if word not in allowed:
            err(f"{rel}:{n} unexpected keyword '{word}' at level {level}")
        if raw.rstrip().endswith("="):
            in_expr_at = level
        prev_level = level


def parse_model(defn: Path) -> tuple[dict, set]:
    tables: dict[str, set] = {}
    measures: set[str] = set()
    for f in (defn / "tables").glob("*.tmdl"):
        text = f.read_text()
        t = re.search(r"^table (\S+)", text, re.M).group(1)
        tables[t] = {x.strip("'") for x in re.findall(r"^\tcolumn ('[^']+'|\S+)", text, re.M)}
        measures |= {x.strip("'") for x in re.findall(r"^\tmeasure ('[^']+'|\S+)", text, re.M)}
    return tables, measures


def check_tmdl() -> tuple[dict, set]:
    defn = PBIP / "OlistSalesAnalytics.SemanticModel" / "definition"
    files = sorted(defn.rglob("*.tmdl"))
    for f in files:
        lint_tmdl(f)
    tables, measures = parse_model(defn)

    for ft, fc, tt, tc in re.findall(r"fromColumn: (\w+)\.(\w+)\n\ttoColumn: (\w+)\.(\w+)",
                                      (defn / "relationships.tmdl").read_text()):
        for t, col in ((ft, fc), (tt, tc)):
            if col not in tables.get(t, set()):
                err(f"relationship references missing column {t}.{col}")

    for f in (defn / "tables").glob("*.tmdl"):
        text = f.read_text()
        table = f.stem
        for col in re.findall(r"sortByColumn: (\w+)", text):
            if col not in tables[table]:
                err(f"{table}: sortByColumn {col} missing")
        # DAX references inside measures
        for block in re.findall(r"^\tmeasure .*?(?=^\t\t[a-zA-Z]+:)", text, re.M | re.S):
            body = block.split("=", 1)[1]
            for t, col in re.findall(r"\b(\w+)\[([^\]]+)\]", body):
                if col not in tables.get(t, set()):
                    err(f"DAX references missing column {t}[{col}]")
            for ref in re.findall(r"(?<![\w\]])\[([^\]]+)\]", body):
                if ref not in measures and not ref.startswith("@"):
                    err(f"DAX references missing measure [{ref}]")
        # M column list must match the CSV header
        csv_name = re.search(r'DataFolder & "([^"]+)"', text)
        if csv_name:
            header = (PBI_DATA_DIR / csv_name.group(1)).open().readline().strip().split(",")
            typed = re.findall(r'\{"([^"]+)", [\w. ]+\}', text)
            if typed != header:
                err(f"{table}: M typed columns differ from {csv_name.group(1)} header")
            if set(header) != tables[table]:
                err(f"{table}: TMDL columns differ from CSV header")
    dd = (defn / "tables" / "dim_date.tmdl").read_text()
    if "dataCategory: Time" not in dd or not re.search(r"column date\n\t\tdataType: dateTime\n\t\tisKey", dd):
        err("dim_date is not marked as a date table")
    print(f"TMDL: {len(files)} files linted, {len(tables)} tables, {len(measures)} measures")
    return tables, measures


def check_report_fields(tables: dict, measures: set) -> None:
    n = 0
    for f in PBIP.rglob("visual.json"):
        doc = json.loads(f.read_text())
        text = json.dumps(doc)
        for kind, ent, prop in re.findall(
                r'"(Measure|Column)": \{"Expression": \{"SourceRef": \{"Entity": "([^"]+)"\}\}, '
                r'"Property": "([^"]+)"', text):
            n += 1
            ok = prop in measures if kind == "Measure" else prop in tables.get(ent, set())
            if not ok:
                err(f"{f.relative_to(ROOT)}: {kind} {ent}.{prop} not in model")
    print(f"Report: {n} field references checked")


def main() -> int:
    check_json()
    tables, measures = check_tmdl()
    check_report_fields(tables, measures)
    if errors:
        print(f"\n{len(errors)} problem(s):")
        for e in errors[:60]:
            print("  -", e)
        return 1
    print("PBIP validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
