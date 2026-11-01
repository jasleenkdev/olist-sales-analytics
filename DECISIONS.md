# Decisions log

Choices made while building the project, with the reason for each.

## Phase 1: environment and data

| # | Decision | Why |
|---|----------|-----|
| 1.1 | **Database: DuckDB** (embedded file at `data/olist.duckdb`), not PostgreSQL | The Docker CLI is installed but the Docker daemon was not running on the build machine, so the brief's fallback applied. DuckDB needs no server, and the SQL is written to be PostgreSQL-compatible (standard DDL, `CAST`, `DATE_TRUNC`, `EXTRACT`, `FILTER`, `PERCENTILE_CONT ... WITHIN GROUP`, `generate_series`). No `docker-compose.yml` is shipped because it could not be tested. |
| 1.2 | **Data source: `kagglehub`** (option a) worked first time | `scripts/download_data.py` still implements the full chain (kagglehub, then Kaggle CLI, then a mirror set by `OLIST_MIRROR_URL`) and checks every file by name and row count. |
| 1.3 | Columns `product_name_lenght` / `product_description_lenght` renamed to `..._length` | Fixes a typo in the source. The loader maps the columns explicitly. |
| 1.4 | Zip code prefixes stored as text | Keeps leading zeros (for example `01037`). |
| 1.5 | `order_reviews` primary key is `(review_id, order_id)` | `review_id` alone is not unique: 99,224 rows but only 98,410 distinct ids. The pair is unique. |
| 1.6 | No FK from `products.product_category_name` to `category_translation` | Two categories (`pc_gamer`, `portateis_cozinha_e_preparadores_de_alimentos`) are missing from the translation file. |
| 1.7 | `geolocation` has no primary key and is not used downstream | The 1,000,163 rows cover only 19,015 distinct zip prefixes, so there is no natural key, and none of the 8 questions needs coordinates. |
| 1.8 | Loader reads every CSV as text and lets the table's declared types do the casting | Typing is defined in one place (`01_schema.sql`), and FK and CHECK constraints are enforced during the load. |
