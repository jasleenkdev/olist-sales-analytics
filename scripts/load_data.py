"""Load the 9 Olist CSVs from data/raw/ into a fresh DuckDB database.

Steps
1. Delete and recreate data/olist.duckdb.
2. Run sql/01_schema.sql (tables, primary keys, foreign keys).
3. INSERT each CSV in foreign-key order with explicit column mapping.
4. Verify every table's row count equals the CSV's row count (parsed with
   pandas, which handles multi-line quoted review comments correctly).
"""
import sys

import pandas as pd

from common import DB_PATH, RAW_DIR, SQL_DIR, connect

# table -> (csv file, SELECT list mapping CSV columns to table columns)
TABLES = {
    "category_translation": ("product_category_name_translation.csv",
        "product_category_name, product_category_name_english"),
    "customers": ("olist_customers_dataset.csv",
        "customer_id, customer_unique_id, customer_zip_code_prefix, customer_city, customer_state"),
    "sellers": ("olist_sellers_dataset.csv",
        "seller_id, seller_zip_code_prefix, seller_city, seller_state"),
    "products": ("olist_products_dataset.csv",
        "product_id, product_category_name, product_name_lenght, product_description_lenght, "
        "product_photos_qty, product_weight_g, product_length_cm, product_height_cm, product_width_cm"),
    "geolocation": ("olist_geolocation_dataset.csv",
        "geolocation_zip_code_prefix, geolocation_lat, geolocation_lng, geolocation_city, geolocation_state"),
    "orders": ("olist_orders_dataset.csv",
        "order_id, customer_id, order_status, order_purchase_timestamp, order_approved_at, "
        "order_delivered_carrier_date, order_delivered_customer_date, order_estimated_delivery_date"),
    "order_items": ("olist_order_items_dataset.csv",
        "order_id, order_item_id, product_id, seller_id, shipping_limit_date, price, freight_value"),
    "order_payments": ("olist_order_payments_dataset.csv",
        "order_id, payment_sequential, payment_type, payment_installments, payment_value"),
    "order_reviews": ("olist_order_reviews_dataset.csv",
        "review_id, order_id, review_score, review_comment_title, review_comment_message, "
        "review_creation_date, review_answer_timestamp"),
}


def main() -> int:
    missing = [f for f, _ in TABLES.values() if not (RAW_DIR / f).exists()]
    if missing:
        print(f"Missing raw files in {RAW_DIR}: {missing}. Run scripts/download_data.py first.")
        return 1

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    DB_PATH.unlink(missing_ok=True)
    con = connect()
    con.execute((SQL_DIR / "01_schema.sql").read_text())

    ok = True
    print(f"{'table':<22}{'csv rows':>12}{'db rows':>12}  status")
    for table, (fname, cols) in TABLES.items():
        path = RAW_DIR / fname
        # all_varchar=true: let the table's declared types do the casting, so
        # zip codes keep leading zeros and nothing is silently re-typed.
        con.execute(
            f"INSERT INTO {table} SELECT {cols} "
            f"FROM read_csv('{path.as_posix()}', header=true, all_varchar=true)"
        )
        db_rows = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        csv_rows = len(pd.read_csv(path, dtype=str))
        status = "OK" if db_rows == csv_rows else "MISMATCH"
        ok &= status == "OK"
        print(f"{table:<22}{csv_rows:>12,}{db_rows:>12,}  {status}")
    con.close()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
