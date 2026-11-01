-- =============================================================================
-- Q8. Repeat-purchase rate and median days between first and second order.
--
-- Customer = customer_unique_id. Delivered orders only.
-- Techniques: ROW_NUMBER, LEAD, PERCENTILE_CONT ... WITHIN GROUP (median),
--             FILTER, CASE bucketing.
-- =============================================================================

-- @output: q8_repeat_summary
WITH customer_orders AS (
    SELECT c.customer_unique_id,
           o.order_id,
           o.order_purchase_timestamp,
           ROW_NUMBER() OVER (PARTITION BY c.customer_unique_id
                              ORDER BY o.order_purchase_timestamp, o.order_id) AS order_seq,
           -- LEAD = the next order's timestamp for the same customer.
           LEAD(o.order_purchase_timestamp) OVER (PARTITION BY c.customer_unique_id
                              ORDER BY o.order_purchase_timestamp, o.order_id) AS next_order_ts
    FROM orders o
    JOIN customers c ON c.customer_id = o.customer_id
    WHERE o.order_status = 'delivered'
),
per_customer AS (
    SELECT customer_unique_id,
           COUNT(*) AS orders,
           -- Gap between order 1 and order 2 (NULL for one-time buyers).
           MAX(CASE WHEN order_seq = 1 AND next_order_ts IS NOT NULL
                    THEN CAST(next_order_ts AS DATE) - CAST(order_purchase_timestamp AS DATE)
               END) AS days_to_second
    FROM customer_orders
    GROUP BY customer_unique_id
)
SELECT COUNT(*)                                                    AS customers,
       COUNT(*) FILTER (WHERE orders >= 2)                         AS repeat_customers,
       ROUND(100.0 * COUNT(*) FILTER (WHERE orders >= 2) / COUNT(*), 2) AS repeat_rate_pct,
       PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY days_to_second) AS median_days_to_second,
       ROUND(AVG(days_to_second), 1)                               AS avg_days_to_second,
       COUNT(*) FILTER (WHERE days_to_second = 0)                  AS same_day_second_orders,
       -- Same-day second orders are mostly one basket split into two orders.
       -- Median excluding them shows the gap for a real return visit.
       PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY days_to_second)
           FILTER (WHERE days_to_second > 0)                       AS median_days_to_second_excl_same_day
FROM per_customer;


-- @output: q8_orders_per_customer
-- Distribution of customers by number of delivered orders, and their revenue.
WITH per_customer AS (
    SELECT c.customer_unique_id,
           COUNT(DISTINCT o.order_id) AS orders,
           SUM(i.price)               AS revenue
    FROM orders o
    JOIN customers c   ON c.customer_id = o.customer_id
    JOIN order_items i ON i.order_id = o.order_id
    WHERE o.order_status = 'delivered'
    GROUP BY c.customer_unique_id
)
SELECT CASE WHEN orders >= 4 THEN '4+' ELSE CAST(orders AS VARCHAR) END AS orders_per_customer,
       COUNT(*)                                                     AS customers,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2)           AS customer_share_pct,
       ROUND(SUM(revenue), 2)                                       AS revenue,
       ROUND(100.0 * SUM(revenue) / SUM(SUM(revenue)) OVER (), 2)   AS revenue_share_pct,
       ROUND(SUM(revenue) / COUNT(*), 2)                            AS revenue_per_customer
FROM per_customer
GROUP BY 1
ORDER BY 1;
