-- =============================================================================
-- Q7. Payment method mix and installment behaviour (delivered orders).
--
-- Payments are split rows: one order can use a voucher plus a card, so a
-- row = one payment, and an order can appear under several methods.
-- Techniques: CTEs, window share-of-total, CASE bucketing, COUNT DISTINCT,
--             conditional aggregation.
-- =============================================================================

-- @output: q7_payment_mix
WITH delivered_payments AS (
    SELECT p.*
    FROM order_payments p
    JOIN orders o ON o.order_id = p.order_id
    WHERE o.order_status = 'delivered'
)
SELECT payment_type,
       COUNT(DISTINCT order_id)                                        AS orders_using,
       COUNT(*)                                                        AS payments,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2)              AS payment_share_pct,
       ROUND(SUM(payment_value), 2)                                    AS payment_value,
       ROUND(100.0 * SUM(payment_value) / SUM(SUM(payment_value)) OVER (), 2) AS value_share_pct,
       ROUND(AVG(payment_value), 2)                                    AS avg_payment_value,
       ROUND(AVG(payment_installments), 2)                             AS avg_installments
FROM delivered_payments
GROUP BY payment_type
ORDER BY payment_value DESC;


-- @output: q7_installments
-- Credit card payments only: how many installments do customers choose,
-- and do bigger baskets get split into more installments?
WITH card AS (
    SELECT p.payment_installments, p.payment_value
    FROM order_payments p
    JOIN orders o ON o.order_id = p.order_id
    WHERE o.order_status = 'delivered'
      AND p.payment_type = 'credit_card'
),
bucketed AS (
    SELECT CASE
               WHEN payment_installments <= 1 THEN '01 (single payment)'
               WHEN payment_installments <= 3 THEN '02-03'
               WHEN payment_installments <= 6 THEN '04-06'
               WHEN payment_installments <= 9 THEN '07-09'
               ELSE '10+'
           END AS installment_band,
           payment_installments,
           payment_value
    FROM card
)
SELECT installment_band,
       COUNT(*)                                                    AS payments,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2)          AS payment_share_pct,
       ROUND(AVG(payment_value), 2)                                AS avg_payment_value,
       ROUND(SUM(payment_value), 2)                                AS payment_value,
       ROUND(100.0 * SUM(payment_value) / SUM(SUM(payment_value)) OVER (), 2) AS value_share_pct
FROM bucketed
GROUP BY installment_band
ORDER BY installment_band;
