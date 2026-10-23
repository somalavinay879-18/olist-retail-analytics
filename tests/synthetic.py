"""A tiny synthetic dataset with the same files and columns as the real Olist data.

The numbers are chosen so the expected KPIs can be checked by hand (see test_pipeline.py).
Nothing here is real Olist data.
"""
import csv
from pathlib import Path

FILES = {
    "olist_customers_dataset.csv": (
        ["customer_id", "customer_unique_id", "customer_zip_code_prefix", "customer_city", "customer_state"],
        [
            ["c1", "u1", "01000", "sao paulo", "SP"],
            ["c2", "u2", "20000", "rio de janeiro", "RJ"],
            ["c3", "u1", "01000", "sao paulo", "SP"],
            ["c4", "u3", "01000", "sao paulo", "SP"],
            ["c5", "u4", "30000", "belo horizonte", "MG"],
        ],
    ),
    "olist_orders_dataset.csv": (
        ["order_id", "customer_id", "order_status", "order_purchase_timestamp", "order_approved_at",
         "order_delivered_carrier_date", "order_delivered_customer_date", "order_estimated_delivery_date"],
        [
            ["o1", "c1", "delivered", "2017-01-10 10:00:00", "2017-01-10 11:00:00",
             "2017-01-12 09:00:00", "2017-01-20 10:00:00", "2017-01-25 00:00:00"],
            ["o2", "c2", "delivered", "2017-01-15 09:00:00", "2017-01-15 10:00:00",
             "2017-01-17 09:00:00", "2017-02-10 09:00:00", "2017-02-01 00:00:00"],
            ["o3", "c3", "delivered", "2017-02-05 08:00:00", "2017-02-05 09:00:00",
             "2017-02-06 09:00:00", "2017-02-12 08:00:00", "2017-02-20 00:00:00"],
            ["o4", "c4", "canceled", "2017-02-07 12:00:00", "", "", "", "2017-02-25 00:00:00"],
            ["o5", "c5", "shipped", "2017-02-20 15:00:00", "2017-02-20 16:00:00",
             "2017-02-22 09:00:00", "", "2017-03-10 00:00:00"],
            ["o6", "c1", "delivered", "2017-03-03 12:00:00", "2017-03-03 13:00:00",
             "2017-03-04 09:00:00", "2017-03-08 12:00:00", "2017-03-15 00:00:00"],
        ],
    ),
    "olist_order_items_dataset.csv": (
        ["order_id", "order_item_id", "product_id", "seller_id", "shipping_limit_date", "price", "freight_value"],
        [
            ["o1", "1", "p1", "s1", "2017-01-13 00:00:00", "100.0", "10.0"],
            ["o1", "2", "p2", "s1", "2017-01-13 00:00:00", "50.0", "5.0"],
            ["o2", "1", "p2", "s2", "2017-01-18 00:00:00", "200.0", "20.0"],
            ["o3", "1", "p1", "s1", "2017-02-08 00:00:00", "80.0", "8.0"],
            ["o4", "1", "p3", "s2", "2017-02-10 00:00:00", "999.0", "9.0"],
            ["o5", "1", "p3", "s2", "2017-02-23 00:00:00", "60.0", "6.0"],
            ["o6", "1", "p1", "s2", "2017-03-05 00:00:00", "120.0", "12.0"],
            ["o6", "2", "p1", "s2", "2017-03-05 00:00:00", "120.0", "12.0"],
        ],
    ),
    "olist_order_payments_dataset.csv": (
        ["order_id", "payment_sequential", "payment_type", "payment_installments", "payment_value"],
        [
            ["o1", "1", "credit_card", "1", "100.0"],
            ["o1", "2", "voucher", "1", "65.0"],
            ["o2", "1", "credit_card", "2", "220.0"],
            ["o3", "1", "boleto", "1", "88.0"],
            ["o4", "1", "credit_card", "1", "1008.0"],
            ["o6", "1", "credit_card", "3", "264.0"],
        ],
    ),
    "olist_order_reviews_dataset.csv": (
        ["review_id", "order_id", "review_score", "review_comment_title", "review_comment_message",
         "review_creation_date", "review_answer_timestamp"],
        [
            ["rv1", "o1", "5", "", "Great, fast\ndelivery", "2017-01-21 00:00:00", "2017-01-22 10:00:00"],
            ["rv2", "o2", "1", "", "", "2017-02-11 00:00:00", "2017-02-12 10:00:00"],
            ["rv3a", "o3", "2", "", "", "2017-02-13 00:00:00", "2017-02-14 10:00:00"],
            ["rv3b", "o3", "4", "", "", "2017-02-15 00:00:00", "2017-02-16 10:00:00"],
            ["rv6", "o6", "3", "", "", "2017-03-09 00:00:00", "2017-03-10 10:00:00"],
        ],
    ),
    "olist_products_dataset.csv": (
        ["product_id", "product_category_name", "product_name_lenght", "product_description_lenght",
         "product_photos_qty", "product_weight_g", "product_length_cm", "product_height_cm", "product_width_cm"],
        [
            ["p1", "beleza_saude", "40", "300", "2", "500", "20", "10", "15"],
            ["p2", "esporte_lazer", "35", "250", "1", "1200", "30", "20", "25"],
            ["p3", "pc_gamer", "50", "400", "3", "2000", "40", "30", "35"],
        ],
    ),
    "olist_sellers_dataset.csv": (
        ["seller_id", "seller_zip_code_prefix", "seller_city", "seller_state"],
        [
            ["s1", "01000", "sao paulo", "SP"],
            ["s2", "20000", "rio de janeiro", "RJ"],
        ],
    ),
    "product_category_name_translation.csv": (
        ["product_category_name", "product_category_name_english"],
        [
            ["beleza_saude", "health_beauty"],
            ["esporte_lazer", "sports_leisure"],
        ],
    ),
}

# A broken extra order item: its order does not exist and its price is negative.
BROKEN_ITEM = ["o99", "1", "p1", "s1", "2017-02-01 00:00:00", "-5.0", "1.0"]


def write_raw_csvs(directory, broken: bool = False) -> Path:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for filename, (header, rows) in FILES.items():
        rows = list(rows)
        if broken and filename == "olist_order_items_dataset.csv":
            rows.append(BROKEN_ITEM)
        with open(directory / filename, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(header)
            writer.writerows(rows)
    return directory
