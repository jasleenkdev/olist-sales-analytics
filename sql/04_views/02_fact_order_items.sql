-- =============================================================================
-- fact_order_items: one row per order line. Grain = (order_id, order_item_id).
-- Carries customer_unique_id and purchase_date so it links straight to the
-- dimensions (no fact-to-fact relationship needed in Power BI).
-- =============================================================================
CREATE OR REPLACE VIEW fact_order_items AS
SELECT i.order_id,
       i.order_item_id,
       i.product_id,
       i.seller_id,
       c.customer_unique_id,
       CAST(o.order_purchase_timestamp AS DATE)                  AS purchase_date,
       o.order_status,
       CASE WHEN o.order_status = 'delivered' THEN 1 ELSE 0 END  AS is_delivered,
       i.price,
       i.freight_value
FROM order_items i
JOIN orders o    ON o.order_id = i.order_id
JOIN customers c ON c.customer_id = o.customer_id;
