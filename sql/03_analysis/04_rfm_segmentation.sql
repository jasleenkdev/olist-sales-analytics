-- =============================================================================
-- Q4. RFM segmentation (Recency, Frequency, Monetary).
--
--   Recency   = days from last delivered order to the reference date
--               (day after the last delivered purchase in the data)
--   Frequency = number of delivered orders
--   Monetary  = total item revenue
--
-- Scoring:
--   R and M: NTILE(5) quintiles, 5 = best.
--   F: fixed bands, NOT NTILE. About 97% of customers have exactly one order,
--      so quintiles would split identical customers at random. 1 order = 1,
--      2 orders = 3, 3+ orders = 5.
-- Techniques: CTEs, NTILE window function, CASE segment rules,
--             date subtraction, window share-of-total.
-- =============================================================================

-- @output: q4_rfm_segments
WITH customer_orders AS (
    SELECT c.customer_unique_id,
           o.order_id,
           o.order_purchase_timestamp,
           SUM(i.price) AS order_revenue
    FROM orders o
    JOIN customers c   ON c.customer_id = o.customer_id
    JOIN order_items i ON i.order_id = o.order_id
    WHERE o.order_status = 'delivered'
    GROUP BY c.customer_unique_id, o.order_id, o.order_purchase_timestamp
),
reference AS (
    SELECT CAST(MAX(order_purchase_timestamp) AS DATE) + 1 AS ref_date
    FROM customer_orders
),
rfm_raw AS (
    SELECT co.customer_unique_id,
           r.ref_date - CAST(MAX(co.order_purchase_timestamp) AS DATE) AS recency_days,
           COUNT(*)                                                   AS frequency,
           SUM(co.order_revenue)                                      AS monetary
    FROM customer_orders co
    CROSS JOIN reference r
    GROUP BY co.customer_unique_id, r.ref_date
),
rfm_scored AS (
    SELECT *,
           -- Most recent customers (smallest recency) land in tile 5.
           NTILE(5) OVER (ORDER BY recency_days DESC, customer_unique_id) AS r_score,
           CASE WHEN frequency >= 3 THEN 5
                WHEN frequency = 2  THEN 3
                ELSE 1 END                                                 AS f_score,
           NTILE(5) OVER (ORDER BY monetary ASC, customer_unique_id)      AS m_score
    FROM rfm_raw
),
rfm_segmented AS (
    SELECT *,
           CASE
               WHEN f_score >= 3 AND r_score >= 4 THEN 'Champions'
               WHEN f_score >= 3                  THEN 'Loyal Customers'
               WHEN r_score >= 4 AND m_score >= 4 THEN 'Promising'
               WHEN r_score >= 4                  THEN 'New Customers'
               WHEN r_score >= 2 AND m_score >= 4 THEN 'At Risk'
               WHEN r_score >= 2                  THEN 'About to Sleep'
               WHEN m_score >= 4                  THEN 'Cannot Lose Them'
               ELSE 'Hibernating'
           END AS segment
    FROM rfm_scored
)
SELECT segment,
       COUNT(*)                                                  AS customers,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2)        AS customer_share_pct,
       ROUND(AVG(recency_days), 1)                               AS avg_recency_days,
       ROUND(AVG(frequency), 2)                                  AS avg_frequency,
       ROUND(AVG(monetary), 2)                                   AS avg_monetary,
       ROUND(SUM(monetary), 2)                                   AS total_revenue,
       ROUND(100.0 * SUM(monetary) / SUM(SUM(monetary)) OVER (), 2) AS revenue_share_pct
FROM rfm_segmented
GROUP BY segment
ORDER BY total_revenue DESC;


-- @output: q4_rfm_score_grid
-- Customers by R score and M score: a heatmap of the base.
WITH customer_orders AS (
    SELECT c.customer_unique_id, o.order_id, o.order_purchase_timestamp,
           SUM(i.price) AS order_revenue
    FROM orders o
    JOIN customers c   ON c.customer_id = o.customer_id
    JOIN order_items i ON i.order_id = o.order_id
    WHERE o.order_status = 'delivered'
    GROUP BY c.customer_unique_id, o.order_id, o.order_purchase_timestamp
),
reference AS (
    SELECT CAST(MAX(order_purchase_timestamp) AS DATE) + 1 AS ref_date FROM customer_orders
),
rfm_raw AS (
    SELECT co.customer_unique_id,
           r.ref_date - CAST(MAX(co.order_purchase_timestamp) AS DATE) AS recency_days,
           SUM(co.order_revenue) AS monetary
    FROM customer_orders co CROSS JOIN reference r
    GROUP BY co.customer_unique_id, r.ref_date
),
scored AS (
    SELECT NTILE(5) OVER (ORDER BY recency_days DESC, customer_unique_id) AS r_score,
           NTILE(5) OVER (ORDER BY monetary ASC, customer_unique_id)      AS m_score,
           recency_days, monetary
    FROM rfm_raw
)
SELECT r_score, m_score,
       COUNT(*)                      AS customers,
       MIN(recency_days)             AS min_recency_days,
       MAX(recency_days)             AS max_recency_days,
       ROUND(MIN(monetary), 2)       AS min_monetary,
       ROUND(MAX(monetary), 2)       AS max_monetary
FROM scored
GROUP BY r_score, m_score
ORDER BY r_score, m_score;
