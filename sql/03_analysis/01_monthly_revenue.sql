-- =============================================================================
-- Q1. Monthly revenue, orders and average order value (AOV), with
--     month-over-month (MoM) and year-over-year (YoY) growth.
--
-- Rules (see docs/data_quality.md):
--   * delivered orders only
--   * revenue = SUM(order_items.price), freight excluded
--   * window = Jan 2017 to Aug 2018, the 20 complete months
-- Techniques: CTEs, JOIN, DATE_TRUNC, LAG window function, NULLIF.
-- =============================================================================

-- @output: q1_monthly_revenue
WITH delivered_orders AS (
    -- One row per delivered order inside the analysis window.
    SELECT order_id,
           CAST(DATE_TRUNC('month', order_purchase_timestamp) AS DATE) AS order_month
    FROM orders
    WHERE order_status = 'delivered'
      AND order_purchase_timestamp >= TIMESTAMP '2017-01-01'
      AND order_purchase_timestamp <  TIMESTAMP '2018-09-01'
),
order_revenue AS (
    -- Collapse items to one revenue figure per order, so orders are not
    -- double counted when we count them per month.
    SELECT d.order_month,
           d.order_id,
           SUM(i.price)         AS revenue,
           SUM(i.freight_value) AS freight
    FROM delivered_orders d
    JOIN order_items i ON i.order_id = d.order_id
    GROUP BY d.order_month, d.order_id
),
monthly AS (
    SELECT order_month,
           SUM(revenue)  AS revenue,
           COUNT(*)      AS orders,
           SUM(freight)  AS freight
    FROM order_revenue
    GROUP BY order_month
)
SELECT order_month,
       ROUND(revenue, 2)                                         AS revenue,
       orders,
       ROUND(revenue / orders, 2)                                AS aov,
       ROUND(freight, 2)                                         AS freight,
       -- LAG looks one row back in month order: the previous month's value.
       ROUND(LAG(revenue) OVER (ORDER BY order_month), 2)        AS prev_month_revenue,
       ROUND(100.0 * (revenue - LAG(revenue) OVER (ORDER BY order_month))
             / NULLIF(LAG(revenue) OVER (ORDER BY order_month), 0), 2) AS revenue_mom_pct,
       ROUND(100.0 * (orders - LAG(orders) OVER (ORDER BY order_month))
             / NULLIF(LAG(orders) OVER (ORDER BY order_month), 0), 2)  AS orders_mom_pct,
       -- LAG(..., 12) = same month last year. NULL for 2017 (no 2016 base).
       ROUND(100.0 * (revenue - LAG(revenue, 12) OVER (ORDER BY order_month))
             / NULLIF(LAG(revenue, 12) OVER (ORDER BY order_month), 0), 2) AS revenue_yoy_pct
FROM monthly
ORDER BY order_month;


-- @output: q1_yearly_summary
-- Jan-Aug 2017 vs Jan-Aug 2018: a like-for-like YoY comparison.
WITH base AS (
    SELECT EXTRACT(YEAR FROM o.order_purchase_timestamp) AS order_year,
           o.order_id,
           SUM(i.price) AS revenue
    FROM orders o
    JOIN order_items i ON i.order_id = o.order_id
    WHERE o.order_status = 'delivered'
      AND EXTRACT(MONTH FROM o.order_purchase_timestamp) BETWEEN 1 AND 8
      AND EXTRACT(YEAR  FROM o.order_purchase_timestamp) IN (2017, 2018)
    GROUP BY 1, 2
),
yearly AS (
    SELECT order_year, SUM(revenue) AS revenue, COUNT(*) AS orders
    FROM base GROUP BY order_year
)
SELECT CAST(order_year AS INTEGER)                              AS order_year,
       'Jan-Aug'                                                AS period,
       ROUND(revenue, 2)                                        AS revenue,
       orders,
       ROUND(revenue / orders, 2)                               AS aov,
       ROUND(100.0 * (revenue - LAG(revenue) OVER (ORDER BY order_year))
             / LAG(revenue) OVER (ORDER BY order_year), 2)      AS revenue_yoy_pct,
       ROUND(100.0 * (orders - LAG(orders) OVER (ORDER BY order_year))
             / LAG(orders) OVER (ORDER BY order_year), 2)       AS orders_yoy_pct
FROM yearly
ORDER BY order_year;


-- @output: q1_peak_days
-- Top 5 days by delivered orders, compared with the average day of their month.
WITH daily AS (
    SELECT CAST(order_purchase_timestamp AS DATE)                      AS order_date,
           CAST(DATE_TRUNC('month', order_purchase_timestamp) AS DATE) AS order_month,
           COUNT(*)                                                    AS orders
    FROM orders
    WHERE order_status = 'delivered'
    GROUP BY 1, 2
),
with_month_avg AS (
    SELECT order_date, orders,
           AVG(orders) OVER (PARTITION BY order_month) AS month_avg_daily_orders
    FROM daily
)
SELECT order_date,
       orders,
       ROUND(month_avg_daily_orders, 1)                 AS month_avg_daily_orders,
       ROUND(orders / month_avg_daily_orders, 1)        AS times_month_average
FROM with_month_avg
ORDER BY orders DESC
LIMIT 5;
