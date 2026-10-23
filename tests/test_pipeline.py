from datetime import date
from types import SimpleNamespace

import pytest

from olist.pipeline import build
from olist.sqlutil import split_statements
from tests.synthetic import write_raw_csvs


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    raw = write_raw_csvs(tmp_path_factory.mktemp("raw"))
    out = tmp_path_factory.mktemp("out")
    con, results = build(raw, ":memory:", out / "processed", out / "report.md")
    yield SimpleNamespace(con=con, results=results, out=out)
    con.close()


@pytest.fixture(scope="module")
def broken(tmp_path_factory):
    raw = write_raw_csvs(tmp_path_factory.mktemp("raw_broken"), broken=True)
    con, results = build(raw, ":memory:")
    yield SimpleNamespace(con=con, results=results)
    con.close()


def one(con, sql):
    return con.execute(sql).fetchone()[0]


def failing(results):
    return {r["name"]: r["failing_rows"] for r in results}


# ---------- model structure ----------

def test_row_counts(built):
    assert one(built.con, "SELECT count(*) FROM fact_orders") == 6
    assert one(built.con, "SELECT count(*) FROM fact_order_items") == 8
    assert one(built.con, "SELECT count(*) FROM dim_customers") == 5
    assert one(built.con, "SELECT count(*) FROM dim_products") == 3
    assert one(built.con, "SELECT count(*) FROM dim_sellers") == 2


def test_dim_date_has_no_gaps(built):
    lo, hi, n = built.con.execute(
        "SELECT min(date_key), max(date_key), count(*) FROM dim_date").fetchone()
    assert lo == date(2017, 1, 10) and hi == date(2017, 3, 3)
    assert n == (hi - lo).days + 1 == 53


def test_one_review_per_order_uses_latest_answer(built):
    assert one(built.con, "SELECT review_score FROM fact_orders WHERE order_id = 'o3'") == 4
    assert one(built.con, "SELECT review_score FROM fact_orders WHERE order_id = 'o5'") is None


def test_multiline_review_text_does_not_break_loading(built):
    assert one(built.con, "SELECT count(*) FROM stg_reviews") == 5


def test_order_flags(built):
    flags = dict(built.con.execute(
        "SELECT order_id, is_late FROM fact_orders WHERE is_delivered").fetchall())
    assert flags == {"o1": False, "o2": True, "o3": False, "o6": False}
    assert one(built.con, "SELECT is_valid_sale FROM fact_orders WHERE order_id = 'o4'") is False
    assert one(built.con, "SELECT is_late FROM fact_orders WHERE order_id = 'o5'") is None


# ---------- KPIs (expected values calculated by hand from tests/synthetic.py) ----------

def test_monthly_kpis(built):
    rows = {r[0]: r for r in built.con.execute(
        "SELECT year_month, orders, revenue, aov, avg_delivery_days, late_rate, "
        "avg_review_score, revenue_mom_growth FROM kpi_monthly ORDER BY year_month").fetchall()}
    assert list(rows) == ["2017-01", "2017-02", "2017-03"]

    jan, feb, mar = rows["2017-01"], rows["2017-02"], rows["2017-03"]
    assert jan[1:7] == (2, pytest.approx(350), pytest.approx(175), pytest.approx(18),
                        pytest.approx(0.5), pytest.approx(3))
    assert jan[7] is None
    assert feb[1:7] == (2, pytest.approx(140), pytest.approx(70), pytest.approx(7),
                        pytest.approx(0.0), pytest.approx(4))
    assert feb[7] == pytest.approx(-0.6)
    assert mar[1:7] == (1, pytest.approx(240), pytest.approx(240), pytest.approx(5),
                        pytest.approx(0.0), pytest.approx(3))
    assert mar[7] == pytest.approx(240 / 140 - 1)


def test_canceled_orders_are_not_revenue(built):
    total = one(built.con, "SELECT sum(revenue) FROM kpi_monthly")
    assert total == pytest.approx(730)  # would be 1729 if the canceled 999 were counted


def test_category_kpi(built):
    rows = {r[0]: r for r in built.con.execute(
        "SELECT category_en, orders, items_sold, revenue, revenue_share FROM kpi_category").fetchall()}
    assert rows["health_beauty"][1:4] == (3, 4, pytest.approx(420))
    assert rows["sports_leisure"][1:4] == (2, 2, pytest.approx(250))
    assert rows["pc_gamer"][1:4] == (1, 1, pytest.approx(60))  # untranslated name falls back
    assert sum(r[4] for r in rows.values()) == pytest.approx(1.0)


def test_state_kpi(built):
    rows = {r[0]: r for r in built.con.execute(
        "SELECT customer_state, orders, revenue, avg_delivery_days, late_rate FROM kpi_state").fetchall()}
    assert rows["SP"][1:] == (3, pytest.approx(470), pytest.approx((10 + 7 + 5) / 3), pytest.approx(0))
    assert rows["RJ"][1:] == (1, pytest.approx(200), pytest.approx(26), pytest.approx(1))
    assert rows["MG"][1] == 1 and rows["MG"][3] is None and rows["MG"][4] is None


def test_seller_kpi(built):
    rows = {r[0]: r for r in built.con.execute(
        "SELECT seller_id, orders, revenue, delivered_orders, late_orders, late_rate "
        "FROM kpi_seller").fetchall()}
    assert rows["s1"][1:] == (2, pytest.approx(230), 2, 0, pytest.approx(0))
    assert rows["s2"][1:] == (3, pytest.approx(500), 2, 1, pytest.approx(0.5))


# ---------- data quality ----------

def test_clean_data_passes_all_error_checks(built):
    errors = [r for r in built.results if r["severity"] == "error" and not r["passed"]]
    assert errors == []


def test_expected_warnings_on_clean_data(built):
    got = failing(built.results)
    assert got["orders_with_multiple_reviews"] == 1   # o3
    assert got["products_unmapped_category"] == 1     # pc_gamer
    assert got["orders_without_payment"] == 1         # o5
    assert got["delivered_without_timestamp"] == 0
    assert got["payment_differs_from_items"] == 0


def test_broken_data_is_detected(broken):
    got = failing(broken.results)
    assert got["items_orphan_order"] == 1
    assert got["items_nonpositive_price"] == 1
    assert got["revenue_reconciles"] == 1  # the orphan item is dropped from the fact table
    errors = [r["name"] for r in broken.results if r["severity"] == "error" and not r["passed"]]
    assert set(errors) == {"items_orphan_order", "items_nonpositive_price", "revenue_reconciles"}


# ---------- outputs and helpers ----------

def test_exports_and_report_are_written(built):
    assert (built.out / "processed" / "fact_orders.csv").is_file()
    assert (built.out / "processed" / "kpi_monthly.csv").is_file()
    report = (built.out / "report.md").read_text(encoding="utf-8")
    assert "| `orders_pk_unique` | error | 0 | PASS |" in report


def test_missing_files_give_a_helpful_error(tmp_path):
    with pytest.raises(FileNotFoundError, match="Download the dataset from Kaggle"):
        build(tmp_path, ":memory:")


def test_split_statements_strips_comments():
    sql = "-- header; not a statement\nSELECT 1; -- trailing\nSELECT 2;\n"
    assert split_statements(sql) == ["SELECT 1", "SELECT 2"]

