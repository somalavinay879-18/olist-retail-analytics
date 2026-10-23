# Olist Retail Analytics: Sales & Delivery Performance

![CI](https://github.com/somalavinay879-18/olist-retail-analytics/actions/workflows/ci.yml/badge.svg)

An end-to-end analytics project on a real Brazilian e-commerce dataset (about 100,000 orders, 2016–2018). Raw CSV files are loaded into DuckDB, cleaned, modelled as a star schema, checked with automated data quality tests and turned into KPIs for sales and delivery performance.

**Business questions**

- How do revenue, order count and average order value develop month by month?
- Which product categories and customer states drive revenue?
- How reliable is delivery (late rate, delivery time) and how does it relate to customer review scores?
- Which sellers have the highest late-delivery rate?

## Pipeline

```
CSV files -> raw_* (text) -> stg_* (typed, cleaned) -> star schema -> KPI views -> CSV export -> dashboard
                                      |                     |
                                      +--- data quality checks (20 checks, report in reports/)
```

| Layer | File | What happens |
|---|---|---|
| Load | `olist/load.py` | each CSV becomes a raw table, everything as text |
| Staging | `sql/01_staging.sql` | types, trimming, consistent names |
| Star schema | `sql/02_star_schema.sql` | 4 dimensions, 2 facts, business flags |
| KPIs | `sql/03_kpis.sql` | monthly, category, state and seller views |
| Quality | `olist/quality.py` | 15 error checks, 5 warnings, markdown report |
| Run | `olist/pipeline.py` | runs everything, exports CSVs for BI tools |

## Data model

| Table | Grain |
|---|---|
| `fact_orders` | one row per order (dates, status, item / freight / payment totals, delivery days, late flag, review score) |
| `fact_order_items` | one row per order item |
| `dim_customers`, `dim_sellers`, `dim_products`, `dim_date` | one row per customer, seller, product, calendar day |

## KPI definitions

| KPI | Definition |
|---|---|
| Valid sale | order status is not `canceled` or `unavailable` |
| Revenue | sum of item prices of valid sales (freight excluded) |
| AOV | revenue ÷ number of valid orders |
| Delivered order | status `delivered` and a delivery date exists |
| Delivery time | days from purchase to delivery, delivered orders only |
| Late order | delivered on a later calendar day than the estimated delivery date |
| Late rate | late orders ÷ delivered orders |
| Review score | one review per order, the most recently answered one |
| MoM growth | revenue ÷ revenue of the previous month − 1 |

## Data quality

20 checks run on every build and are written to [`reports/data_quality_report.md`](reports/data_quality_report.md). Errors (duplicate keys, orphan foreign keys, non-positive prices, impossible dates, join fan-out, revenue not reconciling) stop the run. Known data issues are reported as warnings instead (for example orders with more than one review, or product categories without an English translation).

## Run it

1. Download the dataset from Kaggle: [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) and unzip the CSV files into `data/raw/`.
2. Install and run:

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
python -m olist.pipeline
```

This creates `data/olist.duckdb`, writes CSVs for a BI tool to `data/processed/` and the quality report to `reports/`.

## Tests

```bash
pip install -r requirements-dev.txt
pytest -q
```

The tests run the whole pipeline on a tiny synthetic dataset with the same files and columns as the real one (`tests/synthetic.py`), so they run in CI without the real data. Expected KPI values were calculated by hand. A second dataset with deliberately broken rows checks that the quality checks catch them.

## Data and license

The dataset is not included in this repository. It is published by Olist on Kaggle under [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/); this project is non-commercial and credits the source. The code in this repository is MIT licensed.

## Roadmap

- Power BI / Tableau dashboard on the exported tables
- Weekly demand forecasting: seasonal-naive baseline vs gradient boosting with time-based validation
- Inventory logic: safety stock and reorder points from forecast error
