-- =============================================================================
-- Q3. Monthly cohort retention.
--
-- A cohort = customers (customer_unique_id) whose FIRST delivered order fell
-- in a given month. Retention at month N = share of the cohort that ordered
-- again N months after their first month.
-- Window: cohorts Jan 2017 to Aug 2018, activity up to Aug 2018.
-- Techniques: CTEs, MIN() OVER (PARTITION BY), EXTRACT date arithmetic,
--             conditional aggregation with FILTER to pivot into a matrix.
-- =============================================================================

-- @output: q3_cohort_retention_long
WITH customer_orders AS (
    SELECT c.customer_unique_id,
           CAST(DATE_TRUNC('month', o.order_purchase_timestamp) AS DATE) AS order_month
    FROM orders o
    JOIN customers c ON c.customer_id = o.customer_id
    WHERE o.order_status = 'delivered'
      AND o.order_purchase_timestamp < TIMESTAMP '2018-09-01'
),
with_cohort AS (
    SELECT DISTINCT
           customer_unique_id,
           order_month,
           -- First month this person ever ordered = their cohort.
           MIN(order_month) OVER (PARTITION BY customer_unique_id) AS cohort_month
    FROM customer_orders
),
with_offset AS (
    SELECT customer_unique_id,
           cohort_month,
           CAST((EXTRACT(YEAR FROM order_month) - EXTRACT(YEAR FROM cohort_month)) * 12
              + (EXTRACT(MONTH FROM order_month) - EXTRACT(MONTH FROM cohort_month))
                AS INTEGER) AS month_number
    FROM with_cohort
    WHERE cohort_month >= DATE '2017-01-01'
),
cohort_size AS (
    SELECT cohort_month, COUNT(*) AS cohort_customers
    FROM with_offset WHERE month_number = 0
    GROUP BY cohort_month
)
SELECT w.cohort_month,
       s.cohort_customers,
       w.month_number,
       COUNT(DISTINCT w.customer_unique_id)                                   AS active_customers,
       ROUND(100.0 * COUNT(DISTINCT w.customer_unique_id) / s.cohort_customers, 2) AS retention_pct
FROM with_offset w
JOIN cohort_size s ON s.cohort_month = w.cohort_month
GROUP BY w.cohort_month, s.cohort_customers, w.month_number
ORDER BY w.cohort_month, w.month_number;


-- @output: q3_cohort_retention_matrix
-- Same data pivoted: one row per cohort, columns m1..m12 = retention %.
-- (m0 is always 100%.) Empty cells = month has not happened yet.
WITH customer_orders AS (
    SELECT c.customer_unique_id,
           CAST(DATE_TRUNC('month', o.order_purchase_timestamp) AS DATE) AS order_month
    FROM orders o
    JOIN customers c ON c.customer_id = o.customer_id
    WHERE o.order_status = 'delivered'
      AND o.order_purchase_timestamp < TIMESTAMP '2018-09-01'
),
with_cohort AS (
    SELECT DISTINCT customer_unique_id, order_month,
           MIN(order_month) OVER (PARTITION BY customer_unique_id) AS cohort_month
    FROM customer_orders
),
with_offset AS (
    SELECT customer_unique_id, cohort_month,
           CAST((EXTRACT(YEAR FROM order_month) - EXTRACT(YEAR FROM cohort_month)) * 12
              + (EXTRACT(MONTH FROM order_month) - EXTRACT(MONTH FROM cohort_month))
                AS INTEGER) AS month_number
    FROM with_cohort
    WHERE cohort_month >= DATE '2017-01-01'
),
counts AS (
    SELECT cohort_month,
           COUNT(*) FILTER (WHERE month_number = 0) AS cohort_customers,
           -- How many months of follow-up exist for this cohort (to Aug 2018)?
           CAST((2018 - EXTRACT(YEAR FROM cohort_month)) * 12
              + (8 - EXTRACT(MONTH FROM cohort_month)) AS INTEGER) AS months_observed,
           COUNT(*) FILTER (WHERE month_number = 1)  AS m1,
           COUNT(*) FILTER (WHERE month_number = 2)  AS m2,
           COUNT(*) FILTER (WHERE month_number = 3)  AS m3,
           COUNT(*) FILTER (WHERE month_number = 4)  AS m4,
           COUNT(*) FILTER (WHERE month_number = 5)  AS m5,
           COUNT(*) FILTER (WHERE month_number = 6)  AS m6,
           COUNT(*) FILTER (WHERE month_number = 7)  AS m7,
           COUNT(*) FILTER (WHERE month_number = 8)  AS m8,
           COUNT(*) FILTER (WHERE month_number = 9)  AS m9,
           COUNT(*) FILTER (WHERE month_number = 10) AS m10,
           COUNT(*) FILTER (WHERE month_number = 11) AS m11,
           COUNT(*) FILTER (WHERE month_number = 12) AS m12
    FROM with_offset
    GROUP BY cohort_month
)
SELECT cohort_month,
       cohort_customers,
       CASE WHEN months_observed >= 1  THEN ROUND(100.0 * m1  / cohort_customers, 2) END AS m1,
       CASE WHEN months_observed >= 2  THEN ROUND(100.0 * m2  / cohort_customers, 2) END AS m2,
       CASE WHEN months_observed >= 3  THEN ROUND(100.0 * m3  / cohort_customers, 2) END AS m3,
       CASE WHEN months_observed >= 4  THEN ROUND(100.0 * m4  / cohort_customers, 2) END AS m4,
       CASE WHEN months_observed >= 5  THEN ROUND(100.0 * m5  / cohort_customers, 2) END AS m5,
       CASE WHEN months_observed >= 6  THEN ROUND(100.0 * m6  / cohort_customers, 2) END AS m6,
       CASE WHEN months_observed >= 7  THEN ROUND(100.0 * m7  / cohort_customers, 2) END AS m7,
       CASE WHEN months_observed >= 8  THEN ROUND(100.0 * m8  / cohort_customers, 2) END AS m8,
       CASE WHEN months_observed >= 9  THEN ROUND(100.0 * m9  / cohort_customers, 2) END AS m9,
       CASE WHEN months_observed >= 10 THEN ROUND(100.0 * m10 / cohort_customers, 2) END AS m10,
       CASE WHEN months_observed >= 11 THEN ROUND(100.0 * m11 / cohort_customers, 2) END AS m11,
       CASE WHEN months_observed >= 12 THEN ROUND(100.0 * m12 / cohort_customers, 2) END AS m12
FROM counts
ORDER BY cohort_month;


-- @output: q3_retention_curve
-- Average retention by month number, weighted by cohort size. Only cohorts
-- old enough to have reached month N are included at N.
WITH customer_orders AS (
    SELECT c.customer_unique_id,
           CAST(DATE_TRUNC('month', o.order_purchase_timestamp) AS DATE) AS order_month
    FROM orders o
    JOIN customers c ON c.customer_id = o.customer_id
    WHERE o.order_status = 'delivered'
      AND o.order_purchase_timestamp < TIMESTAMP '2018-09-01'
),
with_cohort AS (
    SELECT DISTINCT customer_unique_id, order_month,
           MIN(order_month) OVER (PARTITION BY customer_unique_id) AS cohort_month
    FROM customer_orders
),
with_offset AS (
    SELECT customer_unique_id, cohort_month,
           CAST((EXTRACT(YEAR FROM order_month) - EXTRACT(YEAR FROM cohort_month)) * 12
              + (EXTRACT(MONTH FROM order_month) - EXTRACT(MONTH FROM cohort_month))
                AS INTEGER) AS month_number
    FROM with_cohort
    WHERE cohort_month >= DATE '2017-01-01'
),
cohorts AS (
    SELECT cohort_month,
           COUNT(*) AS cohort_customers,
           CAST((2018 - EXTRACT(YEAR FROM cohort_month)) * 12
              + (8 - EXTRACT(MONTH FROM cohort_month)) AS INTEGER) AS months_observed
    FROM with_offset WHERE month_number = 0
    GROUP BY cohort_month
),
months AS (
    SELECT CAST(generate_series AS INTEGER) AS month_number
    FROM generate_series(1, 12)
)
SELECT m.month_number,
       COUNT(DISTINCT c.cohort_month)                         AS cohorts_included,
       ROUND(100.0 * (SELECT COUNT(*) FROM with_offset w
                      JOIN cohorts c2 ON c2.cohort_month = w.cohort_month
                      WHERE w.month_number = m.month_number
                        AND c2.months_observed >= m.month_number)
             / SUM(c.cohort_customers), 3)                    AS weighted_retention_pct
FROM months m
JOIN cohorts c ON c.months_observed >= m.month_number
GROUP BY m.month_number
ORDER BY m.month_number;
