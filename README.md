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
| Forecast | `olist/forecast.py` | weekly demand forecast, model comparison, safety stock and reorder point |
| Dashboard | `dashboard/app.py` | Streamlit app on the KPI tables and forecast |

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

## Findings

Results from the full dataset (99,441 orders, September 2016 to October 2018). Descriptive statistics; they show what happened, not why.

- **Delivery problems and reviews go together.** Of 96,470 delivered orders, 6.8% arrived later than the estimate. Late orders have an average review score of 2.27, on-time orders 4.29.
- **Two bad months in early 2018.** The late rate was 14.1% in February and 19.0% in March 2018, against about 3–6% in most other months. Average review scores fell to 3.86 and 3.76 in the same months.
- **Black Friday season.** November 2017 was the highest revenue month (7,423 orders, about 1.00 M BRL). Its late rate was 12.4%, up from 4.2% in October.
- **Delivery depends on the region.** Rio de Janeiro (RJ) has the second-most orders but a 12.1% late rate and 15.3 days average delivery, compared with 4.5% and 8.8 days in São Paulo (SP).
- **Revenue is spread across many categories.** The top 5 categories (health_beauty, watches_gifts, bed_bath_table, sports_leisure, computers_accessories) make up 39.9% of revenue. `bed_bath_table` has the most orders (9,399), `health_beauty` the most revenue (about 1.26 M BRL, 9.3%).

Average delivery time over all delivered orders is 12.6 days. Revenue is item price only, without freight.

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

## Dashboard

A Streamlit dashboard shows the KPIs: headline numbers, revenue and orders per month, late deliveries and review scores, categories, regions and sellers. It reads the aggregated KPI tables in `dashboard/data/`.

```bash
pip install -r dashboard/requirements.txt
streamlit run dashboard/app.py
```

To refresh the data after a pipeline run: `cp data/processed/kpi_*.csv dashboard/data/`

## Demand forecast and inventory logic

`python -m olist.forecast` forecasts weekly units sold for the 10 largest product categories, one week ahead. It trains only on earlier weeks and is tested on the last 12 weeks. Gradient boosting (scikit-learn) is compared with two simple baselines: "same as last week" and "average of the last 4 weeks". Results are reported as MAE and WAPE.

From the forecast error of the best model, the script calculates a safety stock and a reorder point per category (safety stock = z × error standard deviation × √lead time). Lead time (2 weeks) and service level (95%) are assumptions. Olist sellers hold the stock, so this illustrates the method and is not a real policy.

```bash
pip install -r requirements.txt
python -m olist.pipeline          # builds the weekly_demand view
python -m olist.forecast          # writes reports/forecast/*.csv
```

The Forecast tab of the dashboard shows the results (copy `reports/forecast/*.csv` to `dashboard/data/`).

### Results (last 12 weeks, 10 categories, one week ahead)

| Model | MAE (units) | WAPE |
|---|---:|---:|
| Same as last week | 25.4 | **22.6 %** |
| Gradient boosting | 27.3 | 24.3 % |
| Average of last 4 weeks | 28.0 | 24.9 % |

The simple "same as last week" baseline is the best model here. Gradient boosting did not beat it with 65 weeks of training data, so the reorder points below are based on the baseline. More history, promotion and holiday data would be needed to improve on it.

## Data and license

The dataset is not included in this repository. It is published by Olist on Kaggle under [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/); this project is non-commercial and credits the source. The code in this repository is MIT licensed.

## Roadmap

- Publish the Streamlit dashboard online
- Hierarchical or probabilistic forecasts; promotion and holiday effects
