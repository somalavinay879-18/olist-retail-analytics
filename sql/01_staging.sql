-- Staging layer: one clean table per raw file.
-- Raw files are loaded as text (all_varchar), so every type conversion happens here, in one place.
-- TRY_CAST returns NULL instead of failing, so bad values show up in the data quality checks.

CREATE OR REPLACE TABLE stg_customers AS
SELECT
    customer_id,
    customer_unique_id,
    customer_zip_code_prefix AS zip_prefix,
    lower(trim(customer_city)) AS city,
    upper(trim(customer_state)) AS state
FROM raw_customers;

CREATE OR REPLACE TABLE stg_orders AS
SELECT
    order_id,
    customer_id,
    lower(trim(order_status)) AS order_status,
    TRY_CAST(order_purchase_timestamp AS TIMESTAMP) AS purchase_ts,
    TRY_CAST(order_approved_at AS TIMESTAMP) AS approved_ts,
    TRY_CAST(order_delivered_carrier_date AS TIMESTAMP) AS carrier_ts,
    TRY_CAST(order_delivered_customer_date AS TIMESTAMP) AS delivered_ts,
    TRY_CAST(order_estimated_delivery_date AS TIMESTAMP) AS estimated_ts
FROM raw_orders;

CREATE OR REPLACE TABLE stg_order_items AS
SELECT
    order_id,
    TRY_CAST(order_item_id AS INTEGER) AS order_item_id,
    product_id,
    seller_id,
    TRY_CAST(shipping_limit_date AS TIMESTAMP) AS shipping_limit_ts,
    TRY_CAST(price AS DOUBLE) AS price,
    TRY_CAST(freight_value AS DOUBLE) AS freight_value
FROM raw_order_items;

CREATE OR REPLACE TABLE stg_payments AS
SELECT
    order_id,
    TRY_CAST(payment_sequential AS INTEGER) AS payment_sequential,
    lower(trim(payment_type)) AS payment_type,
    TRY_CAST(payment_installments AS INTEGER) AS payment_installments,
    TRY_CAST(payment_value AS DOUBLE) AS payment_value
FROM raw_payments;

CREATE OR REPLACE TABLE stg_reviews AS
SELECT
    review_id,
    order_id,
    TRY_CAST(review_score AS INTEGER) AS review_score,
    TRY_CAST(review_creation_date AS TIMESTAMP) AS creation_ts,
    TRY_CAST(review_answer_timestamp AS TIMESTAMP) AS answer_ts
FROM raw_reviews;

CREATE OR REPLACE TABLE stg_products AS
SELECT
    product_id,
    product_category_name AS category_pt,
    TRY_CAST(product_photos_qty AS INTEGER) AS photos_qty,
    TRY_CAST(product_weight_g AS DOUBLE) AS weight_g
FROM raw_products;

CREATE OR REPLACE TABLE stg_sellers AS
SELECT
    seller_id,
    seller_zip_code_prefix AS zip_prefix,
    lower(trim(seller_city)) AS city,
    upper(trim(seller_state)) AS state
FROM raw_sellers;

CREATE OR REPLACE TABLE stg_category_translation AS
SELECT
    product_category_name AS category_pt,
    product_category_name_english AS category_en
FROM raw_category_translation;
