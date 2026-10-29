"""Run the whole pipeline: load raw CSVs, build staging / star schema / KPIs, check quality, export.

    python -m olist.pipeline --raw data/raw --db data/olist.duckdb
"""
import argparse
import sys
from pathlib import Path

import duckdb

from olist.load import load_raw
from olist.quality import has_errors, run_checks, write_report
from olist.sqlutil import split_statements

SQL_DIR = Path(__file__).resolve().parents[1] / "sql"
SQL_STEPS = ["01_staging.sql", "02_star_schema.sql", "03_kpis.sql", "04_weekly_demand.sql"]
EXPORT_TABLES = [
    "dim_customers", "dim_products", "dim_sellers", "dim_date",
    "fact_orders", "fact_order_items",
    "kpi_monthly", "kpi_category", "kpi_state", "kpi_seller", "weekly_demand",
]


def run_sql_file(con, path: Path) -> None:
    for statement in split_statements(path.read_text(encoding="utf-8")):
        con.execute(statement)


def export_tables(con, export_dir) -> None:
    export_dir = Path(export_dir)
    export_dir.mkdir(parents=True, exist_ok=True)
    for table in EXPORT_TABLES:
        target = str(export_dir / f"{table}.csv").replace("'", "''")
        con.execute(f"COPY (SELECT * FROM {table}) TO '{target}' (HEADER, DELIMITER ',')")


def build(raw_dir, db_path=":memory:", export_dir=None, report_path=None):
    """Build everything. Returns (connection, quality_results)."""
    if db_path != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    load_raw(con, raw_dir)
    for step in SQL_STEPS:
        run_sql_file(con, SQL_DIR / step)
    results = run_checks(con)
    if report_path:
        write_report(results, report_path)
    if export_dir:
        export_tables(con, export_dir)
    return con, results


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Olist retail analytics pipeline")
    parser.add_argument("--raw", default="data/raw", help="folder with the Olist CSV files")
    parser.add_argument("--db", default="data/olist.duckdb", help="DuckDB file to create")
    parser.add_argument("--export", default="data/processed", help="folder for CSV exports")
    parser.add_argument("--report", default="reports/data_quality_report.md")
    args = parser.parse_args(argv)

    try:
        con, results = build(args.raw, args.db, args.export, args.report)
    except FileNotFoundError as error:
        print(error)
        return 2

    for r in results:
        status = "PASS" if r["passed"] else ("FAIL" if r["severity"] == "error" else "WARN")
        print(f"[{status}] {r['name']:<32} {r['failing_rows']:>8,}  {r['description']}")
    orders = con.execute("SELECT count(*) FROM fact_orders").fetchone()[0]
    print(f"\nfact_orders: {orders:,} rows. Exports in {args.export}, report in {args.report}")
    con.close()
    return 1 if has_errors(results) else 0


if __name__ == "__main__":
    sys.exit(main())
