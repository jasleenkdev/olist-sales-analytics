-- =============================================================================
-- fact_orders: one row per order (all statuses). Grain = order_id.
-- Measures filter on is_delivered = 1 where only completed sales count.
-- Keys: customer_unique_id -> dim_customer, purchase_date -> dim_date.
-- =============================================================================
CREATE OR REPLACE VIEW fact_orders AS
WITH items AS (
    SELECT order_id,
           COUNT(*)           AS item_count,
           SUM(price)         AS order_revenue,
           SUM(freight_value) AS order_freight
    FROM order_items GROUP BY order_id
),
payments AS (
    SELECT order_id,
           SUM(payment_value)        AS payment_value,
           MAX(payment_installments) AS max_installments,
           -- Main method = the method that paid the largest share.
           MAX(payment_type) FILTER (WHERE rn = 1) AS main_payment_type
    FROM (
        SELECT p.*,
               ROW_NUMBER() OVER (PARTITION BY order_id
                                  ORDER BY payment_value DESC, payment_sequential) AS rn
        FROM order_payments p
    ) ranked
    GROUP BY order_id
),
reviews AS (
    SELECT order_id, AVG(review_score) AS review_score
    FROM order_reviews GROUP BY order_id
)
SELECT o.order_id,
       c.customer_unique_id,
       c.customer_state,
       o.order_status,
       CASE WHEN o.order_status = 'delivered' THEN 1 ELSE 0 END          AS is_delivered,
       CAST(o.order_purchase_timestamp AS DATE)                          AS purchase_date,
       o.order_purchase_timestamp                                        AS purchase_ts,
       CAST(o.order_delivered_customer_date AS DATE)                     AS delivered_date,
       CAST(o.order_estimated_delivery_date AS DATE)                     AS estimated_date,
       CASE WHEN o.order_status = 'delivered'
             AND o.order_delivered_customer_date IS NOT NULL
            THEN CAST(o.order_delivered_customer_date AS DATE)
               - CAST(o.order_purchase_timestamp AS DATE) END            AS delivery_days,
       CASE WHEN o.order_status = 'delivered'
             AND o.order_delivered_customer_date IS NOT NULL
            THEN CAST(o.order_delivered_customer_date AS DATE)
               - CAST(o.order_estimated_delivery_date AS DATE) END       AS days_vs_estimate,
       -- NULL (not 0) when lateness cannot be judged, so averages skip it.
       CASE WHEN o.order_status <> 'delivered'
              OR o.order_delivered_customer_date IS NULL THEN NULL
            WHEN CAST(o.order_delivered_customer_date AS DATE)
               > CAST(o.order_estimated_delivery_date AS DATE) THEN 1
            ELSE 0 END                                                   AS is_late,
       COALESCE(i.item_count, 0)                                         AS item_count,
       COALESCE(i.order_revenue, 0)                                      AS order_revenue,
       COALESCE(i.order_freight, 0)                                      AS order_freight,
       p.payment_value,
       p.main_payment_type,
       p.max_installments,
       r.review_score
FROM orders o
JOIN customers c     ON c.customer_id = o.customer_id
LEFT JOIN items i    ON i.order_id = o.order_id
LEFT JOIN payments p ON p.order_id = o.order_id
LEFT JOIN reviews r  ON r.order_id = o.order_id;
