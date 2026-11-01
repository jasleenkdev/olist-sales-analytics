-- =============================================================================
-- dim_customer: one row per real customer (customer_unique_id).
-- Location = the customer's most recent order address. RFM attributes come
-- from the customer_rfm helper view. Customers without a delivered order
-- get segment 'No Delivered Order'.
-- =============================================================================
CREATE OR REPLACE VIEW dim_customer AS
WITH latest_address AS (
    SELECT customer_unique_id, customer_city, customer_state, customer_zip_code_prefix
    FROM (
        SELECT c.*,
               ROW_NUMBER() OVER (PARTITION BY c.customer_unique_id
                                  ORDER BY o.order_purchase_timestamp DESC, o.order_id) AS rn
        FROM customers c
        JOIN orders o ON o.customer_id = c.customer_id
    ) x
    WHERE rn = 1
),
activity AS (
    SELECT c.customer_unique_id,
           CAST(MIN(o.order_purchase_timestamp) AS DATE)                      AS first_order_date,
           CAST(MAX(o.order_purchase_timestamp) AS DATE)                      AS last_order_date,
           COUNT(*) FILTER (WHERE o.order_status = 'delivered')               AS delivered_orders
    FROM customers c
    JOIN orders o ON o.customer_id = c.customer_id
    GROUP BY c.customer_unique_id
)
SELECT a.customer_unique_id,
       a.customer_city,
       a.customer_state,
       a.customer_zip_code_prefix,
       act.first_order_date,
       act.last_order_date,
       act.delivered_orders,
       CASE WHEN act.delivered_orders >= 2 THEN 1 ELSE 0 END  AS is_repeat_customer,
       r.recency_days,
       ROUND(r.monetary, 2)                                    AS lifetime_revenue,
       r.r_score,
       r.f_score,
       r.m_score,
       COALESCE(r.rfm_segment, 'No Delivered Order')           AS rfm_segment
FROM latest_address a
JOIN activity act      ON act.customer_unique_id = a.customer_unique_id
LEFT JOIN customer_rfm r ON r.customer_unique_id = a.customer_unique_id;
