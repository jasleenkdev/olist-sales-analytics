-- =============================================================================
-- Q5. Late vs on-time delivery by customer state, and the effect of lateness
--     on review score.
--
-- Late = delivered to the customer on a later calendar date than the
-- estimated delivery date. Delivered orders with a known delivery date only.
-- Orders with several reviews are averaged first (one score per order).
-- Techniques: CTEs, LEFT JOIN, CASE flags, AVG with FILTER, date subtraction,
--             window share-of-total.
-- =============================================================================

-- @output: q5_delivery_by_state
WITH order_review AS (
    SELECT order_id, AVG(review_score) AS review_score
    FROM order_reviews GROUP BY order_id
),
deliveries AS (
    SELECT o.order_id,
           c.customer_state,
           CAST(o.order_delivered_customer_date AS DATE)
             - CAST(o.order_purchase_timestamp AS DATE)              AS delivery_days,
           CASE WHEN CAST(o.order_delivered_customer_date AS DATE)
                   > CAST(o.order_estimated_delivery_date AS DATE)
                THEN 1 ELSE 0 END                                     AS is_late,
           r.review_score
    FROM orders o
    JOIN customers c        ON c.customer_id = o.customer_id
    LEFT JOIN order_review r ON r.order_id = o.order_id
    WHERE o.order_status = 'delivered'
      AND o.order_delivered_customer_date IS NOT NULL
)
SELECT customer_state,
       COUNT(*)                                                AS delivered_orders,
       CAST(SUM(is_late) AS INTEGER)                           AS late_orders,
       ROUND(100.0 * SUM(is_late) / COUNT(*), 2)               AS late_pct,
       ROUND(AVG(delivery_days), 1)                            AS avg_delivery_days,
       ROUND(AVG(review_score), 3)                             AS avg_review,
       ROUND(AVG(review_score) FILTER (WHERE is_late = 0), 3)  AS avg_review_on_time,
       ROUND(AVG(review_score) FILTER (WHERE is_late = 1), 3)  AS avg_review_late,
       ROUND(AVG(review_score) FILTER (WHERE is_late = 0)
           - AVG(review_score) FILTER (WHERE is_late = 1), 3)  AS review_gap
FROM deliveries
GROUP BY customer_state
ORDER BY late_pct DESC;


-- @output: q5_review_by_lateness
-- How review score falls as delivery slips further past the estimate.
WITH order_review AS (
    SELECT order_id, AVG(review_score) AS review_score
    FROM order_reviews GROUP BY order_id
),
deliveries AS (
    SELECT CAST(o.order_delivered_customer_date AS DATE)
             - CAST(o.order_estimated_delivery_date AS DATE) AS days_vs_estimate,
           r.review_score
    FROM orders o
    LEFT JOIN order_review r ON r.order_id = o.order_id
    WHERE o.order_status = 'delivered'
      AND o.order_delivered_customer_date IS NOT NULL
),
bucketed AS (
    SELECT CASE
               WHEN days_vs_estimate <= 0  THEN '1. On time or early'
               WHEN days_vs_estimate <= 3  THEN '2. 1-3 days late'
               WHEN days_vs_estimate <= 7  THEN '3. 4-7 days late'
               WHEN days_vs_estimate <= 14 THEN '4. 8-14 days late'
               ELSE                             '5. 15+ days late'
           END AS lateness_bucket,
           review_score
    FROM deliveries
)
SELECT lateness_bucket,
       COUNT(*)                                                   AS delivered_orders,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2)         AS order_share_pct,
       ROUND(AVG(review_score), 3)                                AS avg_review,
       ROUND(100.0 * COUNT(*) FILTER (WHERE review_score <= 2)
             / NULLIF(COUNT(review_score), 0), 2)                 AS pct_low_reviews_1_2,
       ROUND(100.0 * COUNT(*) FILTER (WHERE review_score = 5)
             / NULLIF(COUNT(review_score), 0), 2)                 AS pct_five_star
FROM bucketed
GROUP BY lateness_bucket
ORDER BY lateness_bucket;


-- @output: q5_delivery_overall
-- One-row headline: overall late % and the on-time vs late review gap.
WITH order_review AS (
    SELECT order_id, AVG(review_score) AS review_score
    FROM order_reviews GROUP BY order_id
),
deliveries AS (
    SELECT CASE WHEN CAST(o.order_delivered_customer_date AS DATE)
                   > CAST(o.order_estimated_delivery_date AS DATE)
                THEN 1 ELSE 0 END AS is_late,
           CAST(o.order_delivered_customer_date AS DATE)
             - CAST(o.order_purchase_timestamp AS DATE) AS delivery_days,
           r.review_score
    FROM orders o
    LEFT JOIN order_review r ON r.order_id = o.order_id
    WHERE o.order_status = 'delivered'
      AND o.order_delivered_customer_date IS NOT NULL
)
SELECT COUNT(*)                                                AS delivered_orders,
       CAST(SUM(is_late) AS INTEGER)                           AS late_orders,
       ROUND(100.0 * SUM(is_late) / COUNT(*), 2)               AS late_pct,
       ROUND(AVG(delivery_days), 2)                            AS avg_delivery_days,
       ROUND(AVG(review_score), 3)                             AS avg_review,
       ROUND(AVG(review_score) FILTER (WHERE is_late = 0), 3)  AS avg_review_on_time,
       ROUND(AVG(review_score) FILTER (WHERE is_late = 1), 3)  AS avg_review_late
FROM deliveries;
