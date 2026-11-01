-- =============================================================================
-- Helper view: one RFM row per customer_unique_id. Same scoring and segment
-- rules as sql/03_analysis/04_rfm_segmentation.sql. dim_customer uses it.
-- =============================================================================
CREATE OR REPLACE VIEW customer_rfm AS
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
    SELECT CAST(MAX(order_purchase_timestamp) AS DATE) + 1 AS ref_date FROM customer_orders
),
rfm_raw AS (
    SELECT co.customer_unique_id,
           r.ref_date - CAST(MAX(co.order_purchase_timestamp) AS DATE) AS recency_days,
           COUNT(*)              AS frequency,
           SUM(co.order_revenue) AS monetary
    FROM customer_orders co CROSS JOIN reference r
    GROUP BY co.customer_unique_id, r.ref_date
),
scored AS (
    SELECT *,
           NTILE(5) OVER (ORDER BY recency_days DESC, customer_unique_id) AS r_score,
           CASE WHEN frequency >= 3 THEN 5 WHEN frequency = 2 THEN 3 ELSE 1 END AS f_score,
           NTILE(5) OVER (ORDER BY monetary ASC, customer_unique_id)      AS m_score
    FROM rfm_raw
)
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
       END AS rfm_segment
FROM scored;
