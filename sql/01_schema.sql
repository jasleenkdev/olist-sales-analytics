-- =============================================================================
-- 01_schema.sql
-- Relational schema for the Olist Brazilian E-Commerce dataset.
--
-- Written in ANSI / PostgreSQL-compatible DDL so the same file runs on DuckDB
-- (used here) and on PostgreSQL with no changes.
--
-- Load order matters because of the foreign keys:
--   category_translation -> customers -> sellers -> products -> geolocation
--   -> orders -> order_items -> order_payments -> order_reviews
-- =============================================================================

DROP TABLE IF EXISTS order_reviews;
DROP TABLE IF EXISTS order_payments;
DROP TABLE IF EXISTS order_items;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS geolocation;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS sellers;
DROP TABLE IF EXISTS customers;
DROP TABLE IF EXISTS category_translation;

-- Portuguese -> English product category names (71 rows).
-- Two categories used by products are missing from this file, so products
-- does NOT get a foreign key to this table (see docs/data_quality.md).
CREATE TABLE category_translation (
    product_category_name          VARCHAR(80) PRIMARY KEY,
    product_category_name_english  VARCHAR(80) NOT NULL
);

-- One row per customer_id. NOTE: Olist issues a new customer_id per order;
-- the real person is customer_unique_id (used for retention / RFM).
CREATE TABLE customers (
    customer_id               VARCHAR(32) PRIMARY KEY,
    customer_unique_id        VARCHAR(32) NOT NULL,
    customer_zip_code_prefix  VARCHAR(5)  NOT NULL,  -- text: keeps leading zeros
    customer_city             VARCHAR(60) NOT NULL,
    customer_state            CHAR(2)     NOT NULL
);

CREATE TABLE sellers (
    seller_id               VARCHAR(32) PRIMARY KEY,
    seller_zip_code_prefix  VARCHAR(5)  NOT NULL,
    seller_city             VARCHAR(60) NOT NULL,
    seller_state            CHAR(2)     NOT NULL
);

-- Column names fix the source typo "lenght" -> "length".
CREATE TABLE products (
    product_id                  VARCHAR(32) PRIMARY KEY,
    product_category_name       VARCHAR(80),
    product_name_length         INTEGER,
    product_description_length  INTEGER,
    product_photos_qty          INTEGER,
    product_weight_g            INTEGER,
    product_length_cm           INTEGER,
    product_height_cm           INTEGER,
    product_width_cm            INTEGER
);

-- Zip prefixes repeat (many lat/lng points per prefix), so there is no
-- natural key. Kept for completeness and not used in the star schema.
CREATE TABLE geolocation (
    geolocation_zip_code_prefix  VARCHAR(5)       NOT NULL,
    geolocation_lat              DOUBLE PRECISION NOT NULL,
    geolocation_lng              DOUBLE PRECISION NOT NULL,
    geolocation_city             VARCHAR(60)      NOT NULL,
    geolocation_state            CHAR(2)          NOT NULL
);

CREATE TABLE orders (
    order_id                       VARCHAR(32) PRIMARY KEY,
    customer_id                    VARCHAR(32) NOT NULL REFERENCES customers (customer_id),
    order_status                   VARCHAR(20) NOT NULL,
    order_purchase_timestamp       TIMESTAMP   NOT NULL,
    order_approved_at              TIMESTAMP,
    order_delivered_carrier_date   TIMESTAMP,
    order_delivered_customer_date  TIMESTAMP,
    order_estimated_delivery_date  TIMESTAMP   NOT NULL
);

-- One row per item in an order. order_item_id is 1..n inside an order.
CREATE TABLE order_items (
    order_id             VARCHAR(32)   NOT NULL REFERENCES orders (order_id),
    order_item_id        INTEGER       NOT NULL,
    product_id           VARCHAR(32)   NOT NULL REFERENCES products (product_id),
    seller_id            VARCHAR(32)   NOT NULL REFERENCES sellers (seller_id),
    shipping_limit_date  TIMESTAMP     NOT NULL,
    price                NUMERIC(10,2) NOT NULL,
    freight_value        NUMERIC(10,2) NOT NULL,
    PRIMARY KEY (order_id, order_item_id)
);

-- An order can be paid with several methods (payment_sequential = 1..n).
CREATE TABLE order_payments (
    order_id              VARCHAR(32)   NOT NULL REFERENCES orders (order_id),
    payment_sequential    INTEGER       NOT NULL,
    payment_type          VARCHAR(20)   NOT NULL,
    payment_installments  INTEGER       NOT NULL,
    payment_value         NUMERIC(10,2) NOT NULL,
    PRIMARY KEY (order_id, payment_sequential)
);

-- review_id is NOT unique on its own in the source (the same review can be
-- attached to several orders), so the key is (review_id, order_id).
CREATE TABLE order_reviews (
    review_id                VARCHAR(32)  NOT NULL,
    order_id                 VARCHAR(32)  NOT NULL REFERENCES orders (order_id),
    review_score             SMALLINT     NOT NULL CHECK (review_score BETWEEN 1 AND 5),
    review_comment_title     VARCHAR(100),
    review_comment_message   VARCHAR(1000),
    review_creation_date     TIMESTAMP    NOT NULL,
    review_answer_timestamp  TIMESTAMP    NOT NULL,
    PRIMARY KEY (review_id, order_id)
);
