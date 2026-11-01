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

## Phase 2-3: data rules and analysis

| # | Decision | Why |
|---|----------|-----|
| 2.1 | **Delivered orders only** for revenue, customer and delivery metrics | The 2,963 orders in other statuses are not completed sales. Details in `docs/data_quality.md`. |
| 2.2 | **Revenue = `SUM(order_items.price)`**, freight excluded | It splits cleanly by category and seller, and every analysis reconciles to one total (13,221,498.11 BRL). `payment_value` includes freight and installment interest, so it is only used in the payment-mix analysis. |
| 2.3 | **Customer = `customer_unique_id`** | `customer_id` changes with every order. Using it would hide all repeat behaviour. |
| 2.4 | **Trend window Jan 2017 to Aug 2018** | 2016 is near-empty (and Nov 2016 has no orders), and Sept/Oct 2018 have no delivered orders. MoM and YoY figures on those months would be noise. |
| 2.5 | Late = delivered on a later **calendar date** than the estimate | The estimate is a date with no time of day, so comparing timestamps would mark same-day deliveries as late. |
| 3.1 | RFM F score uses fixed bands (1 / 2 / 3+ orders mapped to 1 / 3 / 5), not NTILE | 97% of customers have one order, so NTILE would split identical customers at random. R and M use NTILE(5) with `customer_unique_id` as a deterministic tie-breaker. |
| 3.2 | Seller rating rank needs at least 30 delivered orders | Keeps sellers with a handful of reviews off the top of the ranking. |
| 3.3 | Each SQL file marks its saved results with `-- @output: name` comments | One small runner (`scripts/common.py`) executes any file and saves the marked results, so the SQL files stay readable on their own. |

## Phase 4: star schema

| # | Decision | Why |
|---|----------|-----|
| 4.1 | Facts keep all order statuses with an `is_delivered` flag | Status analysis stays possible. DAX measures filter `is_delivered = 1`. |
| 4.2 | `fact_order_items` carries `customer_unique_id` and `purchase_date` | Lets it relate directly to `dim_customer` and `dim_date`, avoiding a fact-to-fact relationship and ambiguous filter paths. |
| 4.3 | RFM attributes live on `dim_customer` (helper view `customer_rfm`) | Segments can be used as slicers in Power BI. Segment counts were checked against `outputs/q4_rfm_segments.csv`. |
| 4.4 | `dim_date` covers whole years 2016 to 2018 | Power BI time intelligence needs a contiguous date table. |
| 4.5 | `powerbi/data/*.csv` (about 50 MB) is committed | The `.pbip` opens and refreshes from a fresh clone without running the pipeline. Each file is under 20 MB. |
