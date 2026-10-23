-- Star schema: dimensions and facts built from the staging tables.
--
-- Grain
--   fact_orders       one row per order
--   fact_order_items  one row per order item
--
-- Business rules (documented once, used everywhere)
--   is_valid_sale  order status is not 'canceled' or 'unavailable'
--   is_delivered   status is 'delivered' AND a delivery timestamp exists
--   is_late        delivered on a later calendar day than the estimated delivery date
--   review_score   one review per order: the most recently answered one

CREATE OR REPLACE TABLE dim_customers AS
SELECT customer_id, customer_unique_id, zip_prefix, city, state
FROM stg_customers;

CREATE OR REPLACE TABLE dim_sellers AS
SELECT seller_id, zip_prefix, city, state
FROM stg_sellers;

CREATE OR REPLACE TABLE dim_products AS
SELECT
    p.product_id,
    p.category_pt,
    COALESCE(t.category_en, p.category_pt, 'unknown') AS category_en,
    p.photos_qty,
    p.weight_g
FROM stg_products p
LEFT JOIN stg_category_translation t ON t.category_pt = p.category_pt;

CREATE OR REPLACE TABLE dim_date AS
WITH RECURSIVE bounds AS (
    SELECT
        CAST(min(purchase_ts) AS DATE) AS lo,
        CAST(max(purchase_ts) AS DATE) AS hi
    FROM stg_orders
),
days(date_key) AS (
    SELECT lo FROM bounds
    UNION ALL
    SELECT CAST(days.date_key + 1 AS DATE)
    FROM days, bounds
    WHERE days.date_key < bounds.hi
)
SELECT
    date_key,
    year(date_key) AS year,
    month(date_key) AS month,
    strftime(date_key, '%Y-%m') AS year_month,
    isodow(date_key) AS iso_weekday,
    CAST(date_trunc('week', date_key) AS DATE) AS week_start
FROM days;

CREATE OR REPLACE TABLE fact_orders AS
WITH items AS (
    SELECT
        order_id,
        count(*) AS items_count,
        sum(price) AS items_value,
        sum(freight_value) AS freight_value
    FROM stg_order_items
    GROUP BY order_id
),
pay AS (
    SELECT order_id, sum(payment_value) AS payment_value
    FROM stg_payments
    GROUP BY order_id
),
latest_review AS (
    SELECT order_id, review_score
    FROM (
        SELECT
            order_id,
            review_score,
            row_number() OVER (
                PARTITION BY order_id
                ORDER BY answer_ts DESC NULLS LAST, review_id
            ) AS rn
        FROM stg_reviews
    ) AS ranked
    WHERE rn = 1
)
SELECT
    o.order_id,
    o.customer_id,
    o.order_status,
    o.purchase_ts,
    CAST(o.purchase_ts AS DATE) AS purchase_date,
    o.approved_ts,
    o.carrier_ts,
    o.delivered_ts,
    o.estimated_ts,
    (o.order_status NOT IN ('canceled', 'unavailable')) AS is_valid_sale,
    (o.order_status = 'delivered' AND o.delivered_ts IS NOT NULL) AS is_delivered,
    COALESCE(i.items_count, 0) AS items_count,
    COALESCE(i.items_value, 0) AS items_value,
    COALESCE(i.freight_value, 0) AS freight_value,
    COALESCE(p.payment_value, 0) AS payment_value,
    CASE WHEN o.order_status = 'delivered' AND o.delivered_ts IS NOT NULL
         THEN (epoch(o.delivered_ts) - epoch(o.purchase_ts)) / 86400.0 END AS delivery_days,
    CASE WHEN o.order_status = 'delivered' AND o.delivered_ts IS NOT NULL
         THEN (epoch(o.delivered_ts) - epoch(o.estimated_ts)) / 86400.0 END AS delay_days,
    CASE WHEN o.order_status = 'delivered' AND o.delivered_ts IS NOT NULL
         THEN CAST(o.delivered_ts AS DATE) > CAST(o.estimated_ts AS DATE) END AS is_late,
    r.review_score
FROM stg_orders o
LEFT JOIN items i ON i.order_id = o.order_id
LEFT JOIN pay p ON p.order_id = o.order_id
LEFT JOIN latest_review r ON r.order_id = o.order_id;

CREATE OR REPLACE TABLE fact_order_items AS
SELECT
    i.order_id,
    i.order_item_id,
    i.product_id,
    i.seller_id,
    o.customer_id,
    o.purchase_date,
    o.order_status,
    o.is_valid_sale,
    i.price,
    i.freight_value
FROM stg_order_items i
JOIN fact_orders o ON o.order_id = i.order_id;
