"""Create the star-schema views (sql/04_views/) and export each one to
powerbi/data/<view>.csv so the Power BI model needs no database connection."""
from common import PBI_DATA_DIR, SQL_DIR, connect

EXPORT = ["fact_orders", "fact_order_items", "dim_customer",
          "dim_product", "dim_seller", "dim_date"]

if __name__ == "__main__":
    con = connect()
    for sql_file in sorted((SQL_DIR / "04_views").glob("*.sql")):
        con.execute(sql_file.read_text())
        print(f"created view from {sql_file.name}")
    PBI_DATA_DIR.mkdir(parents=True, exist_ok=True)
    for view in EXPORT:
        target = PBI_DATA_DIR / f"{view}.csv"
        con.execute(f"COPY (SELECT * FROM {view}) TO '{target.as_posix()}' (HEADER, DELIMITER ',')")
        rows = con.execute(f"SELECT COUNT(*) FROM {view}").fetchone()[0]
        print(f"exported {view:<18} {rows:>9,} rows -> powerbi/data/{target.name}")
    con.close()
