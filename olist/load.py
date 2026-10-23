"""Load the Olist CSV files into DuckDB as raw (all-text) tables."""
from pathlib import Path

RAW_FILES = {
    "raw_customers": "olist_customers_dataset.csv",
    "raw_orders": "olist_orders_dataset.csv",
    "raw_order_items": "olist_order_items_dataset.csv",
    "raw_payments": "olist_order_payments_dataset.csv",
    "raw_reviews": "olist_order_reviews_dataset.csv",
    "raw_products": "olist_products_dataset.csv",
    "raw_sellers": "olist_sellers_dataset.csv",
    "raw_category_translation": "product_category_name_translation.csv",
}


def load_raw(con, raw_dir) -> dict[str, int]:
    """Create one raw_* table per CSV. Returns {table: row_count}."""
    raw_dir = Path(raw_dir)
    missing = [name for name in RAW_FILES.values() if not (raw_dir / name).is_file()]
    if missing:
        raise FileNotFoundError(
            f"Missing Olist files in {raw_dir}: {', '.join(missing)}. "
            "Download the dataset from Kaggle (see README) and unzip it into data/raw/."
        )

    counts = {}
    for table, filename in RAW_FILES.items():
        path = str((raw_dir / filename).resolve()).replace("'", "''")
        con.execute(
            f"CREATE OR REPLACE TABLE {table} AS "
            f"SELECT * FROM read_csv('{path}', header=true, all_varchar=true, "
            f"quote='\"', escape='\"', sample_size=-1)"
        )
        counts[table] = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
    return counts
