-- =============================================================================
-- Q6. Seller ranking by revenue and by rating.
--
-- Revenue rank: DENSE_RANK over item revenue (delivered orders).
-- Rating rank: DENSE_RANK over average review score, only for sellers with
--   at least 30 delivered orders, so a seller with one 5-star review cannot
--   top the list. A review belongs to every seller whose item is in the order.
-- Techniques: CTEs, multiple JOINs, DENSE_RANK, CASE inside a window,
--             NTILE for revenue deciles.
-- =============================================================================

-- @output: q6_seller_ranking
WITH order_review AS (
    SELECT order_id, AVG(review_score) AS review_score
    FROM order_reviews GROUP BY order_id
),
seller_orders AS (
    -- One row per (seller, order) with that seller's revenue in the order.
    SELECT i.seller_id,
           i.order_id,
           SUM(i.price) AS revenue,
           COUNT(*)     AS items
    FROM order_items i
    JOIN orders o ON o.order_id = i.order_id
    WHERE o.order_status = 'delivered'
    GROUP BY i.seller_id, i.order_id
),
seller_stats AS (
    SELECT so.seller_id,
           SUM(so.revenue)          AS revenue,
           COUNT(*)                 AS orders,
           CAST(SUM(so.items) AS INTEGER) AS items,
           AVG(r.review_score)      AS avg_review,
           COUNT(r.review_score)    AS reviewed_orders
    FROM seller_orders so
    LEFT JOIN order_review r ON r.order_id = so.order_id
    GROUP BY so.seller_id
),
ranked AS (
    SELECT s.*,
           DENSE_RANK() OVER (ORDER BY s.revenue DESC) AS revenue_rank,
           -- Ineligible sellers get NULL so they sort last and get no rank.
           CASE WHEN s.orders >= 30 THEN
               DENSE_RANK() OVER (
                   ORDER BY CASE WHEN s.orders >= 30
                                 THEN ROUND(s.avg_review, 2) END DESC NULLS LAST)
           END AS rating_rank
    FROM seller_stats s
)
SELECT r.revenue_rank,
       r.rating_rank,
       r.seller_id,
       se.seller_city,
       se.seller_state,
       ROUND(r.revenue, 2)            AS revenue,
       r.orders,
       r.items,
       ROUND(r.revenue / r.orders, 2) AS avg_order_value,
       ROUND(r.avg_review, 2)         AS avg_review,
       r.reviewed_orders
FROM ranked r
JOIN sellers se ON se.seller_id = r.seller_id
WHERE r.revenue_rank <= 25
ORDER BY r.revenue_rank;


-- @output: q6_seller_concentration
-- How concentrated is revenue? Sellers split into 10 revenue deciles.
WITH seller_rev AS (
    SELECT i.seller_id, SUM(i.price) AS revenue
    FROM order_items i
    JOIN orders o ON o.order_id = i.order_id
    WHERE o.order_status = 'delivered'
    GROUP BY i.seller_id
),
deciles AS (
    SELECT seller_id, revenue,
           NTILE(10) OVER (ORDER BY revenue DESC, seller_id) AS revenue_decile
    FROM seller_rev
),
by_decile AS (
    SELECT revenue_decile, COUNT(*) AS sellers, SUM(revenue) AS revenue
    FROM deciles
    GROUP BY revenue_decile
)
SELECT revenue_decile,
       sellers,
       ROUND(revenue, 2)                                              AS revenue,
       ROUND(100.0 * revenue / SUM(revenue) OVER (), 2)               AS revenue_share_pct,
       -- Running share: decile 1 alone, then 1+2, and so on.
       ROUND(100.0 * SUM(revenue) OVER (ORDER BY revenue_decile)
             / SUM(revenue) OVER (), 2)                               AS cumulative_share_pct
FROM by_decile
ORDER BY revenue_decile;
