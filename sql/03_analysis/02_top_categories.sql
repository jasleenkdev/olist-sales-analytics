-- =============================================================================
-- Q2. Top 10 product categories by revenue, with % share of total revenue.
--
-- English names come from category_translation. Two untranslated categories
-- are mapped by hand, and NULL categories become 'unknown'.
-- Techniques: LEFT JOIN, COALESCE, CASE, window SUM() OVER () for share,
--             RANK window function.
-- =============================================================================

-- @output: q2_top_categories
WITH item_revenue AS (
    SELECT COALESCE(
               t.product_category_name_english,
               CASE p.product_category_name
                   WHEN 'pc_gamer' THEN 'pc_gamer'
                   WHEN 'portateis_cozinha_e_preparadores_de_alimentos'
                       THEN 'portable_kitchen_food_preparers'
               END,
               'unknown')                 AS category,
           i.order_id,
           i.price
    FROM order_items i
    JOIN orders o               ON o.order_id = i.order_id
    JOIN products p             ON p.product_id = i.product_id
    LEFT JOIN category_translation t
                                ON t.product_category_name = p.product_category_name
    WHERE o.order_status = 'delivered'
),
by_category AS (
    SELECT category,
           SUM(price)               AS revenue,
           COUNT(DISTINCT order_id) AS orders,
           COUNT(*)                 AS items_sold
    FROM item_revenue
    GROUP BY category
),
ranked AS (
    SELECT category,
           revenue,
           orders,
           items_sold,
           -- SUM() OVER () with an empty window = grand total on every row.
           100.0 * revenue / SUM(revenue) OVER ()       AS revenue_share_pct,
           RANK() OVER (ORDER BY revenue DESC)          AS revenue_rank
    FROM by_category
)
SELECT revenue_rank,
       category,
       ROUND(revenue, 2)                                AS revenue,
       orders,
       items_sold,
       ROUND(revenue / items_sold, 2)                   AS avg_item_price,
       ROUND(revenue_share_pct, 2)                      AS revenue_share_pct,
       -- Running total of share: how concentrated is revenue in the top 10?
       ROUND(SUM(revenue_share_pct) OVER (ORDER BY revenue_rank), 2) AS cumulative_share_pct
FROM ranked
WHERE revenue_rank <= 10
ORDER BY revenue_rank;
