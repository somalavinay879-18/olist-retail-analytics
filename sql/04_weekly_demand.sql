-- Weekly demand per product category, input for the forecasting step.
-- Units = order items of valid sales (canceled / unavailable orders excluded).
-- Weeks start on Monday. Weeks without sales have no row here; the forecast code fills them with 0.

CREATE OR REPLACE VIEW weekly_demand AS
SELECT
    p.category_en,
    CAST(date_trunc('week', i.purchase_date) AS DATE) AS week_start,
    count(*) AS units,
    sum(i.price) AS revenue
FROM fact_order_items i
JOIN dim_products p ON p.product_id = i.product_id
WHERE i.is_valid_sale
GROUP BY 1, 2;
