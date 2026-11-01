"""Run every sql/03_analysis/*.sql file and save results to outputs/."""
from common import OUTPUT_DIR, SQL_DIR, connect, run_sql_file

if __name__ == "__main__":
    con = connect(read_only=True)
    for sql_file in sorted((SQL_DIR / "03_analysis").glob("*.sql")):
        for path in run_sql_file(con, sql_file):
            print(f"{sql_file.name:<28} -> {path.relative_to(OUTPUT_DIR.parent)}")
