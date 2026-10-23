# Data quality report

| Check | Severity | Failing rows | Status | What it checks |
|---|---|---:|---|---|
| `orders_pk_unique` | error | 0 | PASS | order_id is unique in orders |
| `customers_pk_unique` | error | 0 | PASS | customer_id is unique in customers |
| `products_pk_unique` | error | 0 | PASS | product_id is unique in products |
| `sellers_pk_unique` | error | 0 | PASS | seller_id is unique in sellers |
| `order_items_pk_unique` | error | 0 | PASS | (order_id, order_item_id) is unique in order items |
| `items_orphan_order` | error | 0 | PASS | every order item belongs to an existing order |
| `items_orphan_product` | error | 0 | PASS | every order item has an existing product |
| `items_orphan_seller` | error | 0 | PASS | every order item has an existing seller |
| `orders_orphan_customer` | error | 0 | PASS | every order has an existing customer |
| `orders_missing_purchase_ts` | error | 0 | PASS | every order has a valid purchase timestamp |
| `items_nonpositive_price` | error | 0 | PASS | every order item has a price above 0 |
| `delivered_before_purchase` | error | 0 | PASS | delivery is never before purchase |
| `review_score_out_of_range` | error | 0 | PASS | review score is between 1 and 5 |
| `fact_orders_row_count` | error | 0 | PASS | fact_orders has exactly one row per order (no join fan-out) |
| `revenue_reconciles` | error | 0 | PASS | item revenue in fact_orders equals item revenue in staging |
| `delivered_without_timestamp` | warn | 8 | WARN | orders with status delivered but no delivery date |
| `orders_with_multiple_reviews` | warn | 547 | WARN | orders with more than one review (the latest answered one is used) |
| `products_unmapped_category` | warn | 13 | WARN | products whose category has no English translation |
| `orders_without_payment` | warn | 1 | WARN | valid orders that have no payment record |
| `payment_differs_from_items` | warn | 250 | WARN | orders where payment differs from items + freight by more than 1.00 |
