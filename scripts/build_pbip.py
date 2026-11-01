"""Generate the Power BI Project (PBIP) in powerbi/OlistSalesAnalytics/.

Output
  OlistSalesAnalytics.pbip
  OlistSalesAnalytics.SemanticModel/   TMDL semantic model (tables, measures,
                                        relationships, DataFolder parameter)
  OlistSalesAnalytics.Report/          PBIR report (4 pages) + custom theme

Everything is generated from the CSV headers in powerbi/data/ plus the specs
below, so the model always matches the exported views. Lineage tags are
deterministic (uuid5) so re-running the script gives a clean git diff.

Usage
  python scripts/build_pbip.py
  python scripts/build_pbip.py --data-folder "C:\\path\\to\\repo\\powerbi\\data\\"
"""
import argparse
import csv
import json
import shutil
import uuid
from pathlib import Path

from common import PBI_DATA_DIR, ROOT

NAME = "OlistSalesAnalytics"
PBIP_DIR = ROOT / "powerbi" / NAME
SM_DIR = PBIP_DIR / f"{NAME}.SemanticModel"
RPT_DIR = PBIP_DIR / f"{NAME}.Report"
THEME_FILE = ROOT / "powerbi" / "theme" / "OlistTheme.json"
DEFAULT_DATA_FOLDER = "C:\\olist-sales-analytics\\powerbi\\data\\"

SCHEMA = "https://developer.microsoft.com/json-schemas/fabric"
S_PBIP = f"{SCHEMA}/pbip/pbipProperties/1.0.0/schema.json"
S_PBISM = f"{SCHEMA}/item/semanticModel/definitionProperties/1.0.0/schema.json"
S_PBIR = f"{SCHEMA}/item/report/definitionProperties/2.0.0/schema.json"
S_VERSION = f"{SCHEMA}/item/report/definition/versionMetadata/1.0.0/schema.json"
S_REPORT = f"{SCHEMA}/item/report/definition/report/3.0.0/schema.json"
S_PAGES = f"{SCHEMA}/item/report/definition/pagesMetadata/1.0.0/schema.json"
S_PAGE = f"{SCHEMA}/item/report/definition/page/2.0.0/schema.json"
S_VISUAL = f"{SCHEMA}/item/report/definition/visualContainer/2.0.0/schema.json"

TABLES = ["fact_orders", "fact_order_items", "dim_customer", "dim_product", "dim_seller", "dim_date"]

# ---------------------------------------------------------------- column types
DATE_COLS = {"purchase_date", "delivered_date", "estimated_date", "first_order_date",
             "last_order_date", "date", "month_start"}
DATETIME_COLS = {"purchase_ts"}
INT_COLS = {"is_delivered", "is_late", "item_count", "delivery_days", "days_vs_estimate",
            "max_installments", "order_item_id", "delivered_orders", "is_repeat_customer",
            "recency_days", "r_score", "f_score", "m_score", "year", "quarter",
            "month_number", "year_month_key", "day_of_week", "is_weekend",
            "in_analysis_window", "product_photos_qty", "product_weight_g",
            "product_length_cm", "product_height_cm", "product_width_cm"}
MONEY_COLS = {"price", "freight_value", "order_revenue", "order_freight", "payment_value",
              "lifetime_revenue"}
DOUBLE_COLS = {"review_score"}
# Keys and technical columns hidden from report authors.
HIDDEN = {
    "fact_orders": {"customer_unique_id", "purchase_date", "purchase_ts"},
    "fact_order_items": {"customer_unique_id", "purchase_date", "product_id", "seller_id"},
}
SORT_BY = {("dim_date", "month_name"): "month_number", ("dim_date", "day_name"): "day_of_week"}

# ------------------------------------------------------------------ measures
# (name, DAX, format string, display folder)
MEASURES = [
    ("Total Revenue",
     "CALCULATE ( SUM ( fact_order_items[price] ), fact_order_items[is_delivered] = 1 )",
     '\\R\\$ #,0', "Sales"),
    ("Total Orders",
     "CALCULATE ( DISTINCTCOUNT ( fact_order_items[order_id] ), fact_order_items[is_delivered] = 1 )",
     "#,0", "Sales"),
    ("AOV", "DIVIDE ( [Total Revenue], [Total Orders] )", '\\R\\$ #,0.00', "Sales"),
    ("Total Freight",
     "CALCULATE ( SUM ( fact_order_items[freight_value] ), fact_order_items[is_delivered] = 1 )",
     '\\R\\$ #,0', "Sales"),
    ("Revenue PY",
     "CALCULATE ( [Total Revenue], SAMEPERIODLASTYEAR ( dim_date[date] ) )",
     '\\R\\$ #,0', "Time Intelligence"),
    ("Revenue YoY %",
     "VAR _py = [Revenue PY]\nRETURN\n    IF ( NOT ISBLANK ( _py ), DIVIDE ( [Total Revenue] - _py, _py ) )",
     "0.0%", "Time Intelligence"),
    ("Revenue PM",
     "CALCULATE ( [Total Revenue], DATEADD ( dim_date[date], -1, MONTH ) )",
     '\\R\\$ #,0', "Time Intelligence"),
    ("Revenue MoM %",
     "VAR _pm = [Revenue PM]\nRETURN\n    IF ( NOT ISBLANK ( _pm ), DIVIDE ( [Total Revenue] - _pm, _pm ) )",
     "0.0%", "Time Intelligence"),
    ("Running Total Revenue",
     "VAR _maxDate = MAX ( dim_date[date] )\nRETURN\n"
     "    CALCULATE ( [Total Revenue], REMOVEFILTERS ( dim_date ), dim_date[date] <= _maxDate )",
     '\\R\\$ #,0', "Time Intelligence"),
    ("Delivered Orders With Date",
     "CALCULATE ( COUNTROWS ( fact_orders ), NOT ISBLANK ( fact_orders[is_late] ) )",
     "#,0", "Delivery"),
    ("Late Orders",
     "CALCULATE ( COUNTROWS ( fact_orders ), fact_orders[is_late] = 1 )",
     "#,0", "Delivery"),
    ("Late Delivery %", "DIVIDE ( [Late Orders], [Delivered Orders With Date] )", "0.0%", "Delivery"),
    ("Avg Delivery Days",
     "CALCULATE ( AVERAGE ( fact_orders[delivery_days] ), fact_orders[is_delivered] = 1 )",
     "0.0", "Delivery"),
    ("Avg Review Score",
     "CALCULATE ( AVERAGE ( fact_orders[review_score] ), fact_orders[is_delivered] = 1 )",
     "0.00", "Reviews"),
    ("Avg Review On Time",
     "CALCULATE ( [Avg Review Score], fact_orders[is_late] = 0 )", "0.00", "Reviews"),
    ("Avg Review Late",
     "CALCULATE ( [Avg Review Score], fact_orders[is_late] = 1 )", "0.00", "Reviews"),
    ("Active Customers",
     "CALCULATE ( DISTINCTCOUNT ( fact_orders[customer_unique_id] ), fact_orders[is_delivered] = 1 )",
     "#,0", "Customers"),
    ("Repeat Customer %",
     "VAR _customers =\n"
     "    ADDCOLUMNS (\n"
     "        CALCULATETABLE ( VALUES ( fact_orders[customer_unique_id] ), fact_orders[is_delivered] = 1 ),\n"
     "        \"@orders\", CALCULATE ( DISTINCTCOUNT ( fact_orders[order_id] ), fact_orders[is_delivered] = 1 )\n"
     "    )\n"
     "RETURN\n"
     "    DIVIDE ( COUNTROWS ( FILTER ( _customers, [@orders] >= 2 ) ), COUNTROWS ( _customers ) )",
     "0.00%", "Customers"),
    ("RFM Customers",
     "CALCULATE ( COUNTROWS ( dim_customer ), dim_customer[rfm_segment] <> \"No Delivered Order\" )",
     "#,0", "Customers"),
    ("RFM Revenue", "SUM ( dim_customer[lifetime_revenue] )", '\\R\\$ #,0', "Customers"),
    ("Avg Customer Value", "DIVIDE ( [RFM Revenue], [RFM Customers] )", '\\R\\$ #,0.00', "Customers"),
    ("Avg Recency Days", "AVERAGE ( dim_customer[recency_days] )", "0", "Customers"),
]

# relationships: (from table, from column, to table, to column)  many -> one
RELATIONSHIPS = [
    ("fact_orders", "customer_unique_id", "dim_customer", "customer_unique_id"),
    ("fact_orders", "purchase_date", "dim_date", "date"),
    ("fact_order_items", "customer_unique_id", "dim_customer", "customer_unique_id"),
    ("fact_order_items", "purchase_date", "dim_date", "date"),
    ("fact_order_items", "product_id", "dim_product", "product_id"),
    ("fact_order_items", "seller_id", "dim_seller", "seller_id"),
]


def tag(*parts: str) -> str:
    """Deterministic lineage tag."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "olist-pbip/" + "/".join(parts)))


def tmdl_name(name: str) -> str:
    """Quote a TMDL object name when it is not a plain identifier."""
    if name.replace("_", "").isalnum() and not name[0].isdigit():
        return name
    return "'" + name.replace("'", "''") + "'"


def col_meta(col: str):
    """-> (tmdl dataType, M type, formatString or None, summarizeBy)"""
    if col in DATE_COLS:
        return "dateTime", "type date", "yyyy-mm-dd", "none"
    if col in DATETIME_COLS:
        return "dateTime", "type datetime", "yyyy-mm-dd hh:nn:ss", "none"
    if col in INT_COLS:
        return "int64", "Int64.Type", "0", "none"
    if col in MONEY_COLS:
        return "decimal", "Currency.Type", '\\R\\$ #,0.00', "sum"
    if col in DOUBLE_COLS:
        return "double", "type number", "0.00", "none"
    return "string", "type text", None, "none"


def headers(table: str) -> list[str]:
    with open(PBI_DATA_DIR / f"{table}.csv", newline="") as f:
        return next(csv.reader(f))


# --------------------------------------------------------------- semantic model
def table_tmdl(table: str) -> str:
    cols = headers(table)
    out = [f"table {table}", f"\tlineageTag: {tag(table)}"]
    if table == "dim_date":
        out.append("\tdataCategory: Time")  # with isKey on [date] = "Mark as date table"
    out.append("")
    for c in cols:
        dtype, _, fmt, summ = col_meta(c)
        out.append(f"\tcolumn {tmdl_name(c)}")
        out.append(f"\t\tdataType: {dtype}")
        if table == "dim_date" and c == "date":
            out.append("\t\tisKey")
        if fmt:
            out.append(f"\t\tformatString: {fmt}")
        if c in HIDDEN.get(table, set()):
            out.append("\t\tisHidden")
        out.append(f"\t\tlineageTag: {tag(table, c)}")
        out.append(f"\t\tsummarizeBy: {summ}")
        out.append(f"\t\tsourceColumn: {c}")
        if (table, c) in SORT_BY:
            out.append(f"\t\tsortByColumn: {SORT_BY[(table, c)]}")
        out.append("")
        if c in DATE_COLS:
            out.append("\t\tannotation UnderlyingDateTimeDataType = Date")
            out.append("")
        out.append("\t\tannotation SummarizationSetBy = Automatic")
        out.append("")
    type_pairs = ",\n".join(
        f'\t\t\t\t\t\t{{"{c}", {col_meta(c)[1]}}}' for c in cols)
    out += [
        f"\tpartition {table} = m",
        "\t\tmode: import",
        "\t\tsource =",
        "\t\t\t\tlet",
        f'\t\t\t\t    Source = Csv.Document(File.Contents(DataFolder & "{table}.csv"), '
        f'[Delimiter = ",", Columns = {len(cols)}, Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),',
        "\t\t\t\t    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),",
        "\t\t\t\t    Typed = Table.TransformColumnTypes(",
        "\t\t\t\t        Promoted,",
        "\t\t\t\t        {",
        type_pairs.replace("\t\t\t\t\t\t", "\t\t\t\t            "),
        "\t\t\t\t        },",
        '\t\t\t\t        "en-US"',
        "\t\t\t\t    )",
        "\t\t\t\tin",
        "\t\t\t\t    Typed",
        "",
        "\tannotation PBI_ResultType = Table",
        "",
    ]
    return "\n".join(out)


def measures_tmdl() -> str:
    out = ["table _Measures", f"\tlineageTag: {tag('_Measures')}", ""]
    for name, dax, fmt, folder in MEASURES:
        lines = dax.split("\n")
        if len(lines) == 1:
            out.append(f"\tmeasure {tmdl_name(name)} = {dax}")
        else:
            out.append(f"\tmeasure {tmdl_name(name)} =")
            out += [f"\t\t\t{l}" for l in lines]
        out.append(f"\t\tformatString: {fmt}")
        out.append(f"\t\tdisplayFolder: {folder}")
        out.append(f"\t\tlineageTag: {tag('_Measures', name)}")
        out.append("")
    out += [
        "\tcolumn Placeholder",
        "\t\tdataType: string",
        "\t\tisHidden",
        f"\t\tlineageTag: {tag('_Measures', 'Placeholder')}",
        "\t\tsummarizeBy: none",
        "\t\tsourceColumn: Placeholder",
        "",
        "\t\tannotation SummarizationSetBy = Automatic",
        "",
        "\tpartition _Measures = m",
        "\t\tmode: import",
        "\t\tsource =",
        "\t\t\t\tlet",
        "\t\t\t\t    Source = #table(type table [Placeholder = text], {})",
        "\t\t\t\tin",
        "\t\t\t\t    Source",
        "",
        "\tannotation PBI_ResultType = Table",
        "",
    ]
    return "\n".join(out)


def write_semantic_model(data_folder: str) -> None:
    d = SM_DIR / "definition"
    (d / "tables").mkdir(parents=True, exist_ok=True)
    write_json(SM_DIR / "definition.pbism", {"$schema": S_PBISM, "version": "4.0", "settings": {}})
    (d / "database.tmdl").write_text("database\n\tcompatibilityLevel: 1567\n\n")
    order = ["DataFolder", "_Measures"] + TABLES
    model = [
        "model Model",
        "\tculture: en-US",
        "\tdefaultPowerBIDataSourceVersion: powerBI_V3",
        "\tdiscourageImplicitMeasures",
        "\tsourceQueryCulture: en-US",
        "\tdataAccessOptions",
        "\t\tlegacyRedirects",
        "\t\treturnErrorValuesAsNull",
        "",
        f"annotation PBI_QueryOrder = {json.dumps(order)}",
        "",
        "annotation __PBI_TimeIntelligenceEnabled = 0",
        "",
        "annotation PBIDesktopVersion = 2.140.0",
        "",
    ] + [f"ref table {t}" for t in ["_Measures"] + TABLES] + [""]
    (d / "model.tmdl").write_text("\n".join(model))
    esc = data_folder.replace('"', '""')
    (d / "expressions.tmdl").write_text(
        f'/// Folder holding the exported CSVs (powerbi/data/ in this repo). Must end with a slash.\n'
        f'expression DataFolder = "{esc}" meta [IsParameterQuery = true, Type = "Text", '
        f'IsParameterQueryRequired = true]\n'
        f"\tlineageTag: {tag('DataFolder')}\n\n"
        "\tannotation PBI_ResultType = Text\n\n")
    rel = []
    for ft, fc, tt, tc in RELATIONSHIPS:
        rel += [f"relationship {tag('rel', ft, fc, tt, tc)}",
                f"\tfromColumn: {ft}.{fc}",
                f"\ttoColumn: {tt}.{tc}", ""]
    (d / "relationships.tmdl").write_text("\n".join(rel))
    (d / "tables" / "_Measures.tmdl").write_text(measures_tmdl())
    for t in TABLES:
        (d / "tables" / f"{t}.tmdl").write_text(table_tmdl(t))


# ------------------------------------------------------------------- report
def m(name: str) -> dict:
    return {"Measure": {"Expression": {"SourceRef": {"Entity": "_Measures"}}, "Property": name}}


def c(table: str, col: str) -> dict:
    return {"Column": {"Expression": {"SourceRef": {"Entity": table}}, "Property": col}}


def proj(field: dict, display: str | None = None) -> dict:
    kind = "Measure" if "Measure" in field else "Column"
    ent = field[kind]["Expression"]["SourceRef"]["Entity"]
    prop = field[kind]["Property"]
    p = {"field": field, "queryRef": f"{ent}.{prop}", "nativeQueryRef": prop}
    if display:
        p["displayName"] = display
    return p


def lit(v: str) -> dict:
    return {"expr": {"Literal": {"Value": v}}}


# A filter that keeps only the 20 complete months (dim_date[in_analysis_window] = 1).
WINDOW_FILTER = {
    "filters": [{
        "name": "AnalysisWindow",
        "field": c("dim_date", "in_analysis_window"),
        "type": "Categorical",
        "filter": {
            "Version": 2,
            "From": [{"Name": "d", "Entity": "dim_date", "Type": 0}],
            "Where": [{"Condition": {"In": {
                "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "d"}},
                                            "Property": "in_analysis_window"}}],
                "Values": [[{"Literal": {"Value": "1L"}}]]}}}],
        },
    }]
}

# page spec: (page id, display name, [visual specs])
# visual spec: dict(name, type, title, x, y, w, h, roles={role: [fields]}, sort=(field, dir), window=bool)
CARD_W, CARD_H = 196, 100


def cards(prefix: str, measures: list[str], y: int = 16) -> list[dict]:
    gap = (1280 - 32 - CARD_W * 6) / 5 if len(measures) == 6 else 16
    w = CARD_W if len(measures) == 6 else int((1280 - 32 - gap * (len(measures) - 1)) / len(measures))
    return [dict(name=f"{prefix}Card{i + 1}", type="card", title=meas, x=16 + i * (w + gap), y=y,
                 w=w, h=CARD_H, roles={"Values": [m(meas)]}) for i, meas in enumerate(measures)]


PAGES = [
    ("ExecutiveOverview", "Executive Overview",
     cards("exec", ["Total Revenue", "Total Orders", "AOV", "Active Customers",
                    "Avg Review Score", "Late Delivery %"]) + [
        dict(name="execRevenueTrend", type="lineChart",
             title="Monthly revenue (Jan 2017 to Aug 2018)", x=16, y=132, w=808, h=572,
             roles={"Category": [c("dim_date", "year_month")], "Y": [m("Total Revenue")]},
             sort=(c("dim_date", "year_month"), "Ascending"), window=True),
        dict(name="execMonthlyTable", type="tableEx", title="Monthly growth",
             x=840, y=132, w=424, h=572,
             roles={"Values": [c("dim_date", "year_month"), m("Total Revenue"),
                               m("Revenue MoM %"), m("Revenue YoY %")]},
             sort=(c("dim_date", "year_month"), "Ascending"), window=True),
    ]),
    ("SalesTrends", "Sales Trends", [
        dict(name="salesYearSlicer", type="slicer", title="Year", x=16, y=16, w=300, h=84,
             roles={"Values": [c("dim_date", "year")]}),
        # Revenue and orders get separate charts: one y-axis each, no dual axis.
        dict(name="salesRevenueByMonth", type="clusteredColumnChart", title="Revenue by month",
             x=16, y=112, w=408, h=292,
             roles={"Category": [c("dim_date", "year_month")], "Y": [m("Total Revenue")]},
             sort=(c("dim_date", "year_month"), "Ascending"), window=True),
        dict(name="salesOrdersByMonth", type="lineChart", title="Orders by month",
             x=436, y=112, w=408, h=292,
             roles={"Category": [c("dim_date", "year_month")], "Y": [m("Total Orders")]},
             sort=(c("dim_date", "year_month"), "Ascending"), window=True),
        dict(name="salesRunningTotal", type="lineChart", title="Running total revenue",
             x=856, y=112, w=408, h=292,
             roles={"Category": [c("dim_date", "year_month")], "Y": [m("Running Total Revenue")]},
             sort=(c("dim_date", "year_month"), "Ascending"), window=True),
        dict(name="salesByCategory", type="clusteredBarChart", title="Revenue by category",
             x=16, y=420, w=624, h=284,
             roles={"Category": [c("dim_product", "category")], "Y": [m("Total Revenue")]},
             sort=(m("Total Revenue"), "Descending")),
        dict(name="salesByState", type="clusteredBarChart", title="Revenue by customer state",
             x=656, y=420, w=608, h=284,
             roles={"Category": [c("dim_customer", "customer_state")], "Y": [m("Total Revenue")]},
             sort=(m("Total Revenue"), "Descending")),
    ]),
    ("CustomersRFM", "Customers & RFM",
     cards("cust", ["Active Customers", "Repeat Customer %", "Avg Customer Value", "Avg Recency Days"]) + [
        dict(name="custSegmentSize", type="clusteredBarChart", title="Customers by RFM segment",
             x=16, y=132, w=408, h=572,
             roles={"Category": [c("dim_customer", "rfm_segment")], "Y": [m("RFM Customers")]},
             sort=(m("RFM Customers"), "Descending")),
        dict(name="custSegmentValue", type="clusteredBarChart", title="Revenue by RFM segment",
             x=440, y=132, w=408, h=572,
             roles={"Category": [c("dim_customer", "rfm_segment")], "Y": [m("RFM Revenue")]},
             sort=(m("RFM Revenue"), "Descending")),
        dict(name="custSegmentTable", type="tableEx", title="Segment profile",
             x=864, y=132, w=400, h=572,
             roles={"Values": [c("dim_customer", "rfm_segment"), m("RFM Customers"),
                               m("Avg Recency Days"), m("Avg Customer Value"), m("RFM Revenue")]},
             sort=(m("RFM Revenue"), "Descending")),
    ]),
    ("DeliveryReviews", "Delivery & Reviews",
     cards("dlv", ["Late Delivery %", "Avg Delivery Days", "Avg Review On Time", "Avg Review Late"]) + [
        dict(name="dlvLateByState", type="clusteredBarChart", title="Late delivery % by customer state",
             x=16, y=132, w=408, h=572,
             roles={"Category": [c("dim_customer", "customer_state")], "Y": [m("Late Delivery %")]},
             sort=(m("Late Delivery %"), "Descending")),
        dict(name="dlvReviewByLateness", type="clusteredColumnChart",
             title="Average review score by days past the estimate", x=440, y=132, w=824, h=284,
             roles={"Category": [c("fact_orders", "lateness_bucket")], "Y": [m("Avg Review Score")]},
             sort=(c("fact_orders", "lateness_bucket"), "Ascending")),
        dict(name="dlvLateTrend", type="lineChart", title="Late delivery % by month",
             x=440, y=432, w=824, h=272,
             roles={"Category": [c("dim_date", "year_month")], "Y": [m("Late Delivery %")]},
             sort=(c("dim_date", "year_month"), "Ascending"), window=True),
    ]),
]


def visual_json(v: dict, z: int) -> dict:
    query = {"queryState": {role: {"projections": [proj(f) for f in fields]}
                            for role, fields in v["roles"].items()}}
    if v.get("sort"):
        field, direction = v["sort"]
        query["sortDefinition"] = {"sort": [{"field": field, "direction": direction}],
                                   "isDefaultSort": False}
    body = {
        "$schema": S_VISUAL,
        "name": v["name"],
        "position": {"x": round(v["x"], 2), "y": v["y"], "z": z, "width": v["w"],
                     "height": v["h"], "tabOrder": z},
        "visual": {
            "visualType": v["type"],
            "query": query,
            "visualContainerObjects": {
                "title": [{"properties": {"show": lit("true"),
                                          "text": lit("'" + v["title"].replace("'", "''") + "'")}}]
            },
            "drillFilterOtherVisuals": True,
        },
    }
    if v.get("window"):
        body["filterConfig"] = WINDOW_FILTER
    return body


def write_report() -> None:
    d = RPT_DIR / "definition"
    if d.exists():
        shutil.rmtree(d)  # pages are regenerated from the spec
    (d / "pages").mkdir(parents=True)
    write_json(RPT_DIR / "definition.pbir", {
        "$schema": S_PBIR, "version": "4.0",
        "datasetReference": {"byPath": {"path": f"../{NAME}.SemanticModel"}}})
    write_json(d / "version.json", {"$schema": S_VERSION, "version": "2.0.0"})
    res = RPT_DIR / "StaticResources" / "RegisteredResources"
    res.mkdir(parents=True, exist_ok=True)
    shutil.copy2(THEME_FILE, res / THEME_FILE.name)
    write_json(d / "report.json", {
        "$schema": S_REPORT,
        "themeCollection": {"customTheme": {
            "name": THEME_FILE.name,
            "reportVersionAtImport": {"visual": "2.0.0", "report": "3.0.0", "page": "2.0.0"},
            "type": "RegisteredResources"}},
        "resourcePackages": [{
            "name": "RegisteredResources", "type": "RegisteredResources",
            "items": [{"name": THEME_FILE.name, "path": THEME_FILE.name, "type": "CustomTheme"}]}],
        "settings": {"useStylableVisualContainerHeader": True, "defaultDrillFilterOtherVisuals": True,
                     "allowChangeFilterTypes": True, "useEnhancedTooltips": True},
    })
    write_json(d / "pages" / "pages.json", {
        "$schema": S_PAGES, "pageOrder": [p[0] for p in PAGES], "activePageName": PAGES[0][0]})
    for page_id, display, visuals in PAGES:
        pd_ = d / "pages" / page_id
        write_json(pd_ / "page.json", {"$schema": S_PAGE, "name": page_id, "displayName": display,
                                       "displayOption": "FitToPage", "height": 720, "width": 1280})
        for z, v in enumerate(visuals):
            write_json(pd_ / "visuals" / v["name"] / "visual.json", visual_json(v, z * 1000))


def write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n")


# --------------------------------------------------------------- build guide
VISUAL_LABEL = {"card": "Card", "lineChart": "Line chart", "tableEx": "Table",
                "clusteredBarChart": "Clustered bar chart", "clusteredColumnChart": "Clustered column chart",
                "slicer": "Slicer"}


def field_label(f: dict) -> str:
    if "Measure" in f:
        return f"[{f['Measure']['Property']}]"
    return f"{f['Column']['Expression']['SourceRef']['Entity']}[{f['Column']['Property']}]"


def expected_kpis() -> list[str]:
    """Card values the report should show after refresh (no slicers), computed
    from the same CSVs with plain SQL. Used to sanity-check the DAX."""
    import duckdb
    d = PBI_DATA_DIR.as_posix()
    q = f"""
    WITH i AS (SELECT * FROM read_csv('{d}/fact_order_items.csv') WHERE is_delivered = 1),
         o AS (SELECT * FROM read_csv('{d}/fact_orders.csv') WHERE is_delivered = 1),
         per_c AS (SELECT customer_unique_id, COUNT(*) AS n FROM o GROUP BY 1)
    SELECT (SELECT SUM(price) FROM i),
           (SELECT COUNT(DISTINCT order_id) FROM i),
           (SELECT COUNT(DISTINCT customer_unique_id) FROM o),
           (SELECT AVG(review_score) FROM o),
           (SELECT AVG(is_late) FROM o WHERE is_late IS NOT NULL),
           (SELECT AVG(delivery_days) FROM o),
           (SELECT AVG(CASE WHEN n >= 2 THEN 1.0 ELSE 0 END) FROM per_c)
    """
    rev, orders, cust, review, late, days, repeat = duckdb.sql(q).fetchone()
    rev = float(rev)
    return [
        "| Card | Expected value |", "|---|---:|",
        f"| Total Revenue | R$ {rev:,.0f} |",
        f"| Total Orders | {orders:,} |",
        f"| AOV | R$ {rev / orders:,.2f} |",
        f"| Active Customers | {cust:,} |",
        f"| Avg Review Score | {review:.2f} |",
        f"| Late Delivery % | {late:.1%} |",
        f"| Avg Delivery Days | {days:.1f} |",
        f"| Repeat Customer % | {repeat:.2%} |",
    ]


def write_guide() -> None:
    out = [
        "# Power BI build guide",
        "",
        "`scripts/build_pbip.py` generates this file from the same spec it uses to write the PBIR report,",
        "so the guide and `powerbi/OlistSalesAnalytics/` always match. Use it to check the generated",
        "report, or to rebuild any page by hand in Power BI Desktop.",
        "",
        "## 1. Open the project",
        "",
        "1. Power BI Desktop (Windows), version from 2024 or later. Under *File > Options > Preview features*,",
        "   turn on **Power BI Project (.pbip) save option** and **Store semantic model using TMDL format**.",
        "   In newer releases, also turn on **Store reports using enhanced metadata format (PBIR)** if it is listed.",
        "2. Point the `DataFolder` parameter at your copy of `powerbi/data/`. Either:",
        "   * regenerate the project with the path baked in:",
        "     `python scripts/build_pbip.py --data-folder \"C:\\\\path\\\\to\\\\olist-sales-analytics\\\\powerbi\\\\data\\\\\"`, or",
        "   * open the file, then *Transform data > Edit parameters > DataFolder*.",
        "   The value must end with a backslash.",
        "3. Open `powerbi/OlistSalesAnalytics/OlistSalesAnalytics.pbip` and click **Refresh**.",
        "",
        "## 2. Model",
        "",
        "| Table | Grain | Role |",
        "|---|---|---|",
        "| fact_orders | one row per order (all statuses) | order-level facts: delivery, review, payment |",
        "| fact_order_items | one row per order line | revenue facts: price, freight |",
        "| dim_customer | one row per customer_unique_id | location + RFM segment |",
        "| dim_product | one row per product | English category |",
        "| dim_seller | one row per seller | seller location |",
        "| dim_date | one row per day, 2016-01-01 to 2018-12-31 | **marked as date table** (`dataCategory: Time`, `isKey` on `date`) |",
        "| _Measures | none | holds all DAX measures (hidden placeholder column) |",
        "",
        "Relationships (all many-to-one, single direction):",
        "",
    ]
    out += [f"* `{ft}[{fc}]` -> `{tt}[{tc}]`" for ft, fc, tt, tc in RELATIONSHIPS]
    out += ["", "Auto date/time is off. Implicit measures are discouraged, so use the measures below.", "",
            "## 3. Measures", "", "| Measure | Folder | Format | DAX |", "|---|---|---|---|"]
    for name, dax, fmt, folder in MEASURES:
        out.append(f"| {name} | {folder} | `{fmt}` | `{' '.join(dax.split())}` |".replace("\\\\", "\\\\"))
    out += ["", "## 4. Theme", "",
            "`powerbi/theme/OlistTheme.json` (copied into the report's `StaticResources/RegisteredResources/`).",
            "To apply it by hand: *View > Themes > Browse for themes*. It uses an 8-colour categorical palette",
            "checked for colour-blind separation, a light page background (`#f9f9f7`), white-ish cards",
            "(`#fcfcfb`) with a hairline border, and recessive grey axes.", "",
            "## 5. Pages", "",
            "Canvas 1280 x 720, *Fit to page*. Positions are x, y, width, height in pixels.",
            "\"Window filter\" = visual-level filter `dim_date[in_analysis_window] = 1`, which keeps only",
            "the 20 complete months (Jan 2017 to Aug 2018).", ""]
    for i, (pid, display, visuals) in enumerate(PAGES, 1):
        out += [f"### 5.{i} {display}", "", "| Visual | Title | Fields | Sort | Position | Filter |",
                "|---|---|---|---|---|---|"]
        for v in visuals:
            fields = "<br>".join(f"**{role}**: " + ", ".join(field_label(f) for f in fs)
                                 for role, fs in v["roles"].items())
            sort = f"{field_label(v['sort'][0])} {v['sort'][1].lower()}" if v.get("sort") else ""
            pos = f"{round(v['x'])}, {v['y']}, {v['w']}, {v['h']}"
            out.append(f"| {VISUAL_LABEL[v['type']]} | {v['title']} | {fields} | {sort} | {pos} | "
                       f"{'Window filter' if v.get('window') else ''} |")
        out.append("")
    out += ["## 6. Expected values", "",
            "With no slicers applied, the cards should show these values (computed from the same CSVs",
            "with SQL). A mismatch means a relationship or measure is wrong.", ""] + expected_kpis() + [""]
    out += ["## 7. Screenshots", "",
            "After refreshing, export each page (*File > Export > PDF*, or a screen capture) to",
            "`images/powerbi_<page>.png`. The matplotlib versions in `images/` show the same metrics",
            "until those exist.", ""]
    (ROOT / "docs" / "powerbi_build_guide.md").write_text("\n".join(out))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-folder", default=DEFAULT_DATA_FOLDER,
                    help="absolute path of powerbi/data/ on the machine running Power BI Desktop")
    args = ap.parse_args()
    folder = args.data_folder if args.data_folder.endswith(("\\", "/")) else args.data_folder + "\\"
    write_json(PBIP_DIR / f"{NAME}.pbip", {
        "$schema": S_PBIP, "version": "1.0",
        "artifacts": [{"report": {"path": f"{NAME}.Report"}}],
        "settings": {"enableAutoRecovery": True}})
    write_semantic_model(folder)
    write_report()
    write_guide()
    n_vis = sum(len(p[2]) for p in PAGES)
    print(f"PBIP written to {PBIP_DIR.relative_to(ROOT)}: {len(TABLES) + 1} tables, "
          f"{len(MEASURES)} measures, {len(RELATIONSHIPS)} relationships, "
          f"{len(PAGES)} pages, {n_vis} visuals (DataFolder = {folder})")


if __name__ == "__main__":
    main()
