-- =============================================================================
-- dim_product: one row per product with English category name.
-- =============================================================================
CREATE OR REPLACE VIEW dim_product AS
SELECT p.product_id,
       COALESCE(p.product_category_name, 'unknown')          AS category_pt,
       COALESCE(
           t.product_category_name_english,
           CASE p.product_category_name
               WHEN 'pc_gamer' THEN 'pc_gamer'
               WHEN 'portateis_cozinha_e_preparadores_de_alimentos'
                   THEN 'portable_kitchen_food_preparers'
           END,
           'unknown')                                        AS category,
       p.product_photos_qty,
       p.product_weight_g,
       p.product_length_cm,
       p.product_height_cm,
       p.product_width_cm
FROM products p
LEFT JOIN category_translation t ON t.product_category_name = p.product_category_name;
