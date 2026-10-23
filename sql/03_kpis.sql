-- KPI views. Definitions are in the README ("KPI definitions") and use the flags from fact_orders.
-- Revenue = item price only (freight is not included). Canceled / unavailable orders are excluded.

CREATE OR REPLACE VIEW kpi_monthly AS
WITH m AS (
    SELECT
        strftime(purchase_date, '%Y-%m') AS year_month,
        count(*) FILTER (WHERE is_valid_sale) AS orders,
        sum(items_value) FILTER (WHERE is_valid_sale) AS revenue,
        sum(items_value) FILTER (WHERE is_valid_sale)
            / NULLIF(count(*) FILTER (WHERE is_valid_sale), 0) AS aov,
        count(*) FILTER (WHERE is_delivered) AS delivered_orders,
        count(*) FILTER (WHERE is_late) AS late_orders,
        avg(delivery_days) FILTER (WHERE is_delivered) AS avg_delivery_days,
        CAST(count(*) FILTER (WHERE is_late) AS DOUBLE)
            / NULLIF(count(*) FILTER (WHERE is_delivered), 0) AS late_rate,
        avg(review_score) FILTER (WHERE is_valid_sale) AS avg_review_score
    FROM fact_orders
    GROUP BY 1
)
SELECT
    m.*,
    revenue / NULLIF(lag(revenue) OVER (ORDER BY year_month), 0) - 1 AS revenue_mom_growth
FROM m;

CREATE OR REPLACE VIEW kpi_category AS
SELECT
    p.category_en,
    count(DISTINCT i.order_id) AS orders,
    count(*) AS items_sold,
    sum(i.price) AS revenue,
    sum(i.price) / sum(sum(i.price)) OVER () AS revenue_share
FROM fact_order_items i
JOIN dim_products p ON p.product_id = i.product_id
WHERE i.is_valid_sale
GROUP BY 1;

CREATE OR REPLACE VIEW kpi_state AS
SELECT
    c.state AS customer_state,
    count(*) FILTER (WHERE o.is_valid_sale) AS orders,
    sum(o.items_value) FILTER (WHERE o.is_valid_sale) AS revenue,
    avg(o.delivery_days) FILTER (WHERE o.is_delivered) AS avg_delivery_days,
    CAST(count(*) FILTER (WHERE o.is_late) AS DOUBLE)
        / NULLIF(count(*) FILTER (WHERE o.is_delivered), 0) AS late_rate
FROM fact_orders o
JOIN dim_customers c ON c.customer_id = o.customer_id
GROUP BY 1;

CREATE OR REPLACE VIEW kpi_seller AS
SELECT
    i.seller_id,
    count(DISTINCT i.order_id) AS orders,
    sum(i.price) AS revenue,
    count(DISTINCT i.order_id) FILTER (WHERE o.is_delivered) AS delivered_orders,
    count(DISTINCT i.order_id) FILTER (WHERE o.is_late) AS late_orders,
    CAST(count(DISTINCT i.order_id) FILTER (WHERE o.is_late) AS DOUBLE)
        / NULLIF(count(DISTINCT i.order_id) FILTER (WHERE o.is_delivered), 0) AS late_rate
FROM fact_order_items i
JOIN fact_orders o ON o.order_id = i.order_id
WHERE i.is_valid_sale
GROUP BY 1;
