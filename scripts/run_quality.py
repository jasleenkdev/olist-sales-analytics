"""Run sql/02_data_quality.sql and save each check to outputs/data_quality/."""
from common import OUTPUT_DIR, SQL_DIR, connect, run_sql_file

if __name__ == "__main__":
    con = connect(read_only=True)
    for path in run_sql_file(con, SQL_DIR / "02_data_quality.sql"):
        print(f"wrote {path.relative_to(OUTPUT_DIR.parent)}")
