-- =============================================================================
-- dim_seller: one row per seller.
-- =============================================================================
CREATE OR REPLACE VIEW dim_seller AS
SELECT seller_id,
       seller_city,
       seller_state,
       seller_zip_code_prefix
FROM sellers;
