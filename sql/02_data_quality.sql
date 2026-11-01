-- =============================================================================
-- 02_data_quality.sql
-- Data quality checks run before any analysis. Each "-- @output:" block is
-- saved to outputs/data_quality/<name>.csv by scripts/run_quality.py.
-- Findings and the handling decision for each are in docs/data_quality.md.
-- =============================================================================


-- @output: data_quality/01_row_counts
-- Baseline size of every table after loading.
SELECT 'orders'               AS table_name, COUNT(*) AS row_count FROM orders
UNION ALL SELECT 'order_items',          COUNT(*) FROM order_items
UNION ALL SELECT 'order_payments',       COUNT(*) FROM order_payments
UNION ALL SELECT 'order_reviews',        COUNT(*) FROM order_reviews
UNION ALL SELECT 'customers',            COUNT(*) FROM customers
UNION ALL SELECT 'products',             COUNT(*) FROM products
UNION ALL SELECT 'sellers',              COUNT(*) FROM sellers
UNION ALL SELECT 'geolocation',          COUNT(*) FROM geolocation
UNION ALL SELECT 'category_translation', COUNT(*) FROM category_translation;


-- @output: data_quality/02_null_counts
-- NULLs in every column that allows them. COUNT(*) - COUNT(col) = number of NULLs.
SELECT 'orders' AS table_name, 'order_approved_at' AS column_name,
       COUNT(*) - COUNT(order_approved_at) AS null_count, COUNT(*) AS total_rows FROM orders
UNION ALL SELECT 'orders', 'order_delivered_carrier_date',
       COUNT(*) - COUNT(order_delivered_carrier_date), COUNT(*) FROM orders
UNION ALL SELECT 'orders', 'order_delivered_customer_date',
       COUNT(*) - COUNT(order_delivered_customer_date), COUNT(*) FROM orders
UNION ALL SELECT 'products', 'product_category_name',
       COUNT(*) - COUNT(product_category_name), COUNT(*) FROM products
UNION ALL SELECT 'products', 'product_weight_g',
       COUNT(*) - COUNT(product_weight_g), COUNT(*) FROM products
UNION ALL SELECT 'products', 'product_photos_qty',
       COUNT(*) - COUNT(product_photos_qty), COUNT(*) FROM products
UNION ALL SELECT 'order_reviews', 'review_comment_title',
       COUNT(*) - COUNT(review_comment_title), COUNT(*) FROM order_reviews
UNION ALL SELECT 'order_reviews', 'review_comment_message',
       COUNT(*) - COUNT(review_comment_message), COUNT(*) FROM order_reviews
ORDER BY table_name, column_name;


-- @output: data_quality/03_duplicates
-- Primary keys are enforced by the schema, so these look for softer duplicates.
WITH geo_dupes AS (
    SELECT COUNT(*) - 1 AS extra_rows
    FROM geolocation
    GROUP BY geolocation_zip_code_prefix, geolocation_lat, geolocation_lng,
             geolocation_city, geolocation_state
    HAVING COUNT(*) > 1
),
review_ids AS (
    SELECT review_id FROM order_reviews GROUP BY review_id HAVING COUNT(*) > 1
),
orders_multi_review AS (
    SELECT order_id FROM order_reviews GROUP BY order_id HAVING COUNT(*) > 1
),
people AS (
    SELECT customer_unique_id FROM customers
    GROUP BY customer_unique_id HAVING COUNT(*) > 1
)
SELECT 'geolocation: exact duplicate rows (extra copies)' AS check_name,
       CAST((SELECT SUM(extra_rows) FROM geo_dupes) AS BIGINT) AS issue_count
UNION ALL SELECT 'order_reviews: review_id shared by more than one order',
       (SELECT COUNT(*) FROM review_ids)
UNION ALL SELECT 'order_reviews: orders with more than one review',
       (SELECT COUNT(*) FROM orders_multi_review)
UNION ALL SELECT 'customers: customer_unique_id with several customer_id values',
       (SELECT COUNT(*) FROM people)
UNION ALL SELECT 'customers: distinct customer_id',
       (SELECT COUNT(DISTINCT customer_id) FROM customers)
UNION ALL SELECT 'customers: distinct customer_unique_id',
       (SELECT COUNT(DISTINCT customer_unique_id) FROM customers);


-- @output: data_quality/04_orphans
-- Foreign keys guarantee children point at real parents (all would be 0).
-- These look the other way: parents with no children, plus untranslated categories.
SELECT 'orders with no order_items' AS check_name,
       COUNT(*) AS issue_count
FROM orders o
WHERE NOT EXISTS (SELECT 1 FROM order_items i WHERE i.order_id = o.order_id)
UNION ALL
SELECT 'orders with no payment row', COUNT(*)
FROM orders o
WHERE NOT EXISTS (SELECT 1 FROM order_payments p WHERE p.order_id = o.order_id)
UNION ALL
SELECT 'orders with no review', COUNT(*)
FROM orders o
WHERE NOT EXISTS (SELECT 1 FROM order_reviews r WHERE r.order_id = o.order_id)
UNION ALL
SELECT 'products never sold', COUNT(*)
FROM products p
WHERE NOT EXISTS (SELECT 1 FROM order_items i WHERE i.product_id = p.product_id)
UNION ALL
SELECT 'products whose category has no English translation', COUNT(*)
FROM products p
LEFT JOIN category_translation t USING (product_category_name)
WHERE p.product_category_name IS NOT NULL
  AND t.product_category_name IS NULL
UNION ALL
SELECT 'customer zip prefixes not found in geolocation', COUNT(*)
FROM customers c
WHERE NOT EXISTS (SELECT 1 FROM geolocation g
                  WHERE g.geolocation_zip_code_prefix = c.customer_zip_code_prefix);


-- @output: data_quality/05_impossible_dates
-- Timestamps that break the natural order purchase <= approved <= carrier <= customer.
SELECT 'approved before purchase' AS check_name,
       COUNT(*) FILTER (WHERE order_approved_at < order_purchase_timestamp) AS issue_count
FROM orders
UNION ALL
SELECT 'handed to carrier before purchase',
       COUNT(*) FILTER (WHERE order_delivered_carrier_date < order_purchase_timestamp)
FROM orders
UNION ALL
SELECT 'handed to carrier before approval',
       COUNT(*) FILTER (WHERE order_delivered_carrier_date < order_approved_at)
FROM orders
UNION ALL
SELECT 'delivered to customer before carrier pickup',
       COUNT(*) FILTER (WHERE order_delivered_customer_date < order_delivered_carrier_date)
FROM orders
UNION ALL
SELECT 'delivered to customer before purchase',
       COUNT(*) FILTER (WHERE order_delivered_customer_date < order_purchase_timestamp)
FROM orders
UNION ALL
SELECT 'estimated delivery before purchase',
       COUNT(*) FILTER (WHERE order_estimated_delivery_date < CAST(order_purchase_timestamp AS DATE))
FROM orders
UNION ALL
SELECT 'status delivered but no delivery date',
       COUNT(*) FILTER (WHERE order_status = 'delivered' AND order_delivered_customer_date IS NULL)
FROM orders
UNION ALL
SELECT 'delivery date present but status not delivered',
       COUNT(*) FILTER (WHERE order_status <> 'delivered' AND order_delivered_customer_date IS NOT NULL)
FROM orders
UNION ALL
SELECT 'review answered before review created',
       COUNT(*) FILTER (WHERE review_answer_timestamp < review_creation_date)
FROM order_reviews;


-- @output: data_quality/06_order_status
-- Status distribution. Only 'delivered' orders are complete sales.
SELECT order_status,
       COUNT(*) AS orders,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct_of_orders
FROM orders
GROUP BY order_status
ORDER BY orders DESC;


-- @output: data_quality/07_value_checks
-- Values that are allowed by the types but make no business sense.
SELECT 'order_items: price <= 0' AS check_name,
       COUNT(*) FILTER (WHERE price <= 0) AS issue_count FROM order_items
UNION ALL SELECT 'order_payments: payment_value = 0',
       COUNT(*) FILTER (WHERE payment_value = 0) FROM order_payments
UNION ALL SELECT 'order_payments: installments = 0',
       COUNT(*) FILTER (WHERE payment_installments = 0) FROM order_payments
UNION ALL SELECT 'order_payments: payment_type not_defined',
       COUNT(*) FILTER (WHERE payment_type = 'not_defined') FROM order_payments
UNION ALL SELECT 'products: weight_g = 0',
       COUNT(*) FILTER (WHERE product_weight_g = 0) FROM products;


-- @output: data_quality/08_date_coverage
-- Purchase volume per month. Shows the sparse start (late 2016) and the
-- abrupt end (Sept to Oct 2018) that the time-series analysis must handle.
SELECT CAST(DATE_TRUNC('month', order_purchase_timestamp) AS DATE) AS purchase_month,
       COUNT(*)                                                    AS all_orders,
       COUNT(*) FILTER (WHERE order_status = 'delivered')          AS delivered_orders
FROM orders
GROUP BY 1
ORDER BY 1;


-- @output: data_quality/09_payment_reconciliation
-- Delivered orders: do payments equal item price + freight?
-- Differences come from installment interest and vouchers.
WITH item_totals AS (
    SELECT order_id, SUM(price + freight_value) AS items_total
    FROM order_items GROUP BY order_id
),
pay_totals AS (
    SELECT order_id, SUM(payment_value) AS paid_total
    FROM order_payments GROUP BY order_id
)
SELECT COUNT(*)                                                         AS delivered_orders_compared,
       COUNT(*) FILTER (WHERE ABS(p.paid_total - i.items_total) <= 0.01) AS exact_match,
       COUNT(*) FILTER (WHERE p.paid_total - i.items_total > 0.01)       AS paid_more,
       COUNT(*) FILTER (WHERE i.items_total - p.paid_total > 0.01)       AS paid_less
FROM orders o
JOIN item_totals i USING (order_id)
JOIN pay_totals  p USING (order_id)
WHERE o.order_status = 'delivered';
