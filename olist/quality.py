"""Data quality checks. Each check is a SQL query that returns the number of failing rows.

severity "error": the pipeline stops with a non-zero exit code.
severity "warn":  known or tolerable issue, reported but does not fail the run.
"""
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Check:
    name: str
    severity: str
    description: str
    sql: str


def _dupes(table: str, key: str) -> str:
    return (f"SELECT count(*) FROM (SELECT {key} FROM {table} "
            f"GROUP BY {key} HAVING count(*) > 1) AS t")


def _orphans(child: str, child_key: str, parent: str, parent_key: str) -> str:
    return (f"SELECT count(*) FROM {child} c LEFT JOIN {parent} p "
            f"ON p.{parent_key} = c.{child_key} "
            f"WHERE c.{child_key} IS NOT NULL AND p.{parent_key} IS NULL")


CHECKS = [
    Check("orders_pk_unique", "error", "order_id is unique in orders",
          _dupes("stg_orders", "order_id")),
    Check("customers_pk_unique", "error", "customer_id is unique in customers",
          _dupes("stg_customers", "customer_id")),
    Check("products_pk_unique", "error", "product_id is unique in products",
          _dupes("stg_products", "product_id")),
    Check("sellers_pk_unique", "error", "seller_id is unique in sellers",
          _dupes("stg_sellers", "seller_id")),
    Check("order_items_pk_unique", "error", "(order_id, order_item_id) is unique in order items",
          _dupes("stg_order_items", "order_id, order_item_id")),
    Check("items_orphan_order", "error", "every order item belongs to an existing order",
          _orphans("stg_order_items", "order_id", "stg_orders", "order_id")),
    Check("items_orphan_product", "error", "every order item has an existing product",
          _orphans("stg_order_items", "product_id", "stg_products", "product_id")),
    Check("items_orphan_seller", "error", "every order item has an existing seller",
          _orphans("stg_order_items", "seller_id", "stg_sellers", "seller_id")),
    Check("orders_orphan_customer", "error", "every order has an existing customer",
          _orphans("stg_orders", "customer_id", "stg_customers", "customer_id")),
    Check("orders_missing_purchase_ts", "error", "every order has a valid purchase timestamp",
          "SELECT count(*) FROM stg_orders WHERE purchase_ts IS NULL"),
    Check("items_nonpositive_price", "error", "every order item has a price above 0",
          "SELECT count(*) FROM stg_order_items WHERE price IS NULL OR price <= 0"),
    Check("delivered_before_purchase", "error", "delivery is never before purchase",
          "SELECT count(*) FROM stg_orders WHERE delivered_ts < purchase_ts"),
    Check("review_score_out_of_range", "error", "review score is between 1 and 5",
          "SELECT count(*) FROM stg_reviews WHERE review_score IS NULL "
          "OR review_score NOT BETWEEN 1 AND 5"),
    Check("fact_orders_row_count", "error",
          "fact_orders has exactly one row per order (no join fan-out)",
          "SELECT abs((SELECT count(*) FROM fact_orders) - (SELECT count(*) FROM stg_orders))"),
    Check("revenue_reconciles", "error",
          "item revenue in fact_orders equals item revenue in staging",
          "SELECT CASE WHEN abs((SELECT COALESCE(sum(items_value), 0) FROM fact_orders) "
          "- (SELECT COALESCE(sum(price), 0) FROM stg_order_items)) > 0.01 THEN 1 ELSE 0 END"),
    Check("delivered_without_timestamp", "warn",
          "orders with status delivered but no delivery date",
          "SELECT count(*) FROM stg_orders WHERE order_status = 'delivered' AND delivered_ts IS NULL"),
    Check("orders_with_multiple_reviews", "warn",
          "orders with more than one review (the latest answered one is used)",
          _dupes("stg_reviews", "order_id")),
    Check("products_unmapped_category", "warn",
          "products whose category has no English translation",
          "SELECT count(*) FROM stg_products p LEFT JOIN stg_category_translation t "
          "ON t.category_pt = p.category_pt "
          "WHERE p.category_pt IS NOT NULL AND t.category_pt IS NULL"),
    Check("orders_without_payment", "warn", "valid orders that have no payment record",
          "SELECT count(*) FROM stg_orders o "
          "WHERE o.order_status NOT IN ('canceled', 'unavailable') "
          "AND NOT EXISTS (SELECT 1 FROM stg_payments p WHERE p.order_id = o.order_id)"),
    Check("payment_differs_from_items", "warn",
          "orders where payment differs from items + freight by more than 1.00",
          "SELECT count(*) FROM fact_orders WHERE payment_value > 0 AND items_value > 0 "
          "AND abs(payment_value - items_value - freight_value) > 1"),
]


def run_checks(con) -> list[dict]:
    results = []
    for check in CHECKS:
        failing = con.execute(check.sql).fetchone()[0]
        results.append({
            "name": check.name,
            "severity": check.severity,
            "description": check.description,
            "failing_rows": int(failing),
            "passed": failing == 0,
        })
    return results


def has_errors(results: list[dict]) -> bool:
    return any(r["severity"] == "error" and not r["passed"] for r in results)


def write_report(results: list[dict], path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Data quality report",
        "",
        "| Check | Severity | Failing rows | Status | What it checks |",
        "|---|---|---:|---|---|",
    ]
    for r in results:
        status = "PASS" if r["passed"] else ("FAIL" if r["severity"] == "error" else "WARN")
        lines.append(f"| `{r['name']}` | {r['severity']} | {r['failing_rows']:,} | {status} | {r['description']} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
