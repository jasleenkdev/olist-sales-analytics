# SQL concepts used in this project

Each technique gets a plain-language explanation, a short example from this repo, and the files where it appears.
All SQL runs on DuckDB and is written to also run on PostgreSQL.

---

## 1. Constraints: PRIMARY KEY, FOREIGN KEY, CHECK, NOT NULL

**What it is:** rules the database enforces on every insert. A primary key says "no two rows share this value". A
foreign key says "this value must exist in that other table". A CHECK limits allowed values.

**Why here:** the load fails loudly if the data breaks a rule, so the quality checks don't need to look for
duplicate keys or orphan rows: they can't exist.

```sql
review_score SMALLINT NOT NULL CHECK (review_score BETWEEN 1 AND 5),
PRIMARY KEY (review_id, order_id)          -- composite key: review_id alone repeats
```

**Where:** `sql/01_schema.sql`

## 2. JOIN types (INNER, LEFT)

**What it is:** `JOIN` keeps rows that match on both sides. `LEFT JOIN` keeps every row from the left table and fills
NULLs where the right side has no match.

**Why here:** reviews are LEFT JOINed onto orders, because 646 delivered orders have no review and must not disappear
from delivery counts. Category translations are LEFT JOINed so untranslated categories survive.

**Where:** every file in `sql/03_analysis/`; `sql/04_views/01_fact_orders.sql` (four joins with pre-aggregated CTEs)

## 3. CTEs (`WITH ... AS`)

**What it is:** a named, temporary result you define at the top of a query and use below it, like a variable
holding a table.

**Why here:** each step of the logic gets a readable name: `delivered_orders`, then `order_revenue`, then
`monthly`, then the final SELECT. Every analysis file uses this pattern.

**Where:** all of `sql/03_analysis/`, `sql/04_views/`

## 4. Aggregation, GROUP BY, HAVING

**What it is:** collapse many rows into one per group (`SUM`, `COUNT`, `AVG`). `HAVING` filters groups after
aggregation (`WHERE` filters rows before).

```sql
SELECT order_id FROM order_reviews GROUP BY order_id HAVING COUNT(*) > 1   -- orders with 2+ reviews
```

**Where:** `sql/02_data_quality.sql` (duplicate checks), everywhere else

## 5. Conditional aggregation: `FILTER (WHERE ...)` and CASE inside aggregates

**What it is:** count or average only the rows that meet a condition, inside the same GROUP BY. It's the standard
SQL way to pivot rows into columns.

```sql
AVG(review_score) FILTER (WHERE is_late = 0) AS avg_review_on_time,
AVG(review_score) FILTER (WHERE is_late = 1) AS avg_review_late
```

**Where:** `05_delivery_reviews.sql`, `08_repeat_purchase.sql`, `02_data_quality.sql`, and
`03_cohort_retention.sql`, where `COUNT(*) FILTER (WHERE month_number = 1) AS m1` builds the retention matrix
columns.

## 6. CASE expressions

**What it is:** if / else-if / else inside SQL.

**Why here:** business labels such as RFM segments, lateness buckets, installment bands and the "late" flag.

```sql
CASE WHEN f_score >= 3 AND r_score >= 4 THEN 'Champions'
     WHEN f_score >= 3                  THEN 'Loyal Customers'
     ...
     ELSE 'Hibernating' END
```

**Where:** `04_rfm_segmentation.sql`, `05_delivery_reviews.sql`, `07_payment_mix.sql`, `04_views/*`

## 7. Window functions (general idea)

**What it is:** a calculation across related rows **without collapsing them**. `GROUP BY` turns 20 months into 1 row;
a window function keeps all 20 and adds a column computed over the "window". `PARTITION BY` sets the groups and
`ORDER BY` sets the order inside each group.

### 7a. `LAG` / `LEAD`: look at the previous or next row

```sql
LAG(revenue)     OVER (ORDER BY order_month)   -- last month's revenue  -> MoM growth
LAG(revenue, 12) OVER (ORDER BY order_month)   -- same month last year -> YoY growth
LEAD(order_purchase_timestamp) OVER (PARTITION BY customer_unique_id ORDER BY order_purchase_timestamp)
                                               -- this customer's next order -> days to 2nd order
```

**Where:** `01_monthly_revenue.sql` (LAG), `08_repeat_purchase.sql` (LEAD)

### 7b. `ROW_NUMBER`: number the rows, 1, 2, 3...

Picks "the first" or "the latest" row per group. **Where:** `08_repeat_purchase.sql` (1st order per customer),
`04_views/03_dim_customer.sql` (latest address), `04_views/01_fact_orders.sql` (main payment method).

### 7c. `RANK` vs `DENSE_RANK`

Both give ties the same rank. After a tie, `RANK` skips numbers (1, 1, 3) and `DENSE_RANK` doesn't (1, 1, 2).
Seller rating ranks use `DENSE_RANK`, so a block of sellers tied on the same average score doesn't push the
next seller down by the size of the tie.
**Where:** `06_seller_ranking.sql` (DENSE_RANK), `02_top_categories.sql` (RANK)

### 7d. `NTILE(n)`: split rows into n equal-size buckets

`NTILE(5) OVER (ORDER BY monetary)` gives quintiles 1 to 5. **Where:** `04_rfm_segmentation.sql` (R and M scores),
`06_seller_ranking.sql` (`NTILE(10)` revenue deciles).
Watch out: with heavy ties (97% of customers have frequency = 1), NTILE splits identical rows at random. That's
why F uses fixed CASE bands instead.

### 7e. Aggregate as a window: share of total and running totals

```sql
100.0 * revenue / SUM(revenue) OVER ()                        -- % of grand total (empty window = all rows)
SUM(revenue_share_pct) OVER (ORDER BY revenue_rank)           -- running (cumulative) share
MIN(order_month) OVER (PARTITION BY customer_unique_id)       -- each customer's cohort month
SUM(SUM(monetary)) OVER ()                                    -- window over an aggregate
```

**Where:** `02_top_categories.sql`, `03_cohort_retention.sql`, `04_rfm_segmentation.sql`, `06_seller_ranking.sql`,
`07_payment_mix.sql`

## 8. Date functions and date arithmetic

| Expression | Meaning | File |
|---|---|---|
| `DATE_TRUNC('month', ts)` | first day of the month, used to group by month | `01`, `03`, `02_data_quality` |
| `EXTRACT(YEAR / MONTH / DOW / QUARTER FROM d)` | pull out a date part | `03` (month offsets), `06_dim_date.sql` |
| `CAST(ts AS DATE)` | drop the time of day | `05` (late = later *calendar* date) |
| `date_a - date_b` | difference in days (integer) | `04`, `05`, `08` |
| `(y2 - y1) * 12 + (m2 - m1)` | whole months between two months | `03_cohort_retention.sql` |
| `generate_series(start, end, INTERVAL 1 DAY)` | one row per day, so the calendar has no gaps | `04_views/06_dim_date.sql`, `03` |

## 9. `PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY x)`: the median

**What it is:** the ordered-set aggregate for percentiles. The median is the 50th percentile.

**Why here:** days to second order is very skewed (mean 81.2, median 29), so the median describes the typical
customer better than the mean.

**Where:** `08_repeat_purchase.sql`

## 10. NULL handling: `COALESCE`, `NULLIF`, `COUNT(col)` vs `COUNT(*)`

* `COALESCE(a, b, 'unknown')` returns the first non-NULL value. Used for category names with a fallback chain.
* `x / NULLIF(y, 0)` avoids divide-by-zero by returning NULL instead of an error. Used for MoM %.
* `COUNT(*) - COUNT(col)` = number of NULLs in `col`. This is the whole null-profile check.

**Where:** `02_top_categories.sql`, `01_monthly_revenue.sql`, `02_data_quality.sql`, `04_views/04_dim_product.sql`

## 11. `EXISTS` / `NOT EXISTS`: anti-joins

**What it is:** "rows in A with no matching row in B". It's faster and clearer than `NOT IN` when NULLs are involved.

```sql
SELECT COUNT(*) FROM orders o
WHERE NOT EXISTS (SELECT 1 FROM order_items i WHERE i.order_id = o.order_id)   -- 775 orders with no items
```

**Where:** `02_data_quality.sql`

## 12. Set operations: `UNION ALL`

Stacks results with the same columns. It builds a single checklist table from many one-number checks.
**Where:** `02_data_quality.sql`

## 13. Views

**What it is:** a saved query that behaves like a table. The star schema is six views, so it is always in
sync with the base tables and is exported to CSV for Power BI.

**Where:** `sql/04_views/`

## 14. Grain control: aggregate before you join

Joining orders (1 row) to items (n rows) and payments (m rows) at the same time multiplies rows (n x m) and inflates
sums. `fact_orders` aggregates items, payments and reviews **each in its own CTE, to one row per order**, before
joining. This is the most common source of wrong revenue numbers in SQL.

**Where:** `04_views/01_fact_orders.sql`, `01_monthly_revenue.sql` (`order_revenue` CTE), `06_seller_ranking.sql`
(`seller_orders` CTE)
