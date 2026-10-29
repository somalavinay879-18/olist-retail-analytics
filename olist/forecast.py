"""Weekly demand forecast per product category, plus an illustrative inventory policy.

    python -m olist.forecast --db data/olist.duckdb --out reports/forecast

Setup
  * Target: units sold per category and week (valid sales only, see sql/04_weekly_demand.sql).
  * Forecast type: one week ahead. For each week the models only see demand up to the previous week.
  * Validation: time-based. The last TEST_WEEKS weeks are held out; the model is trained on earlier weeks only.
  * Models: two simple baselines (last week, average of the last 4 weeks) and gradient boosting.
  * Metrics: MAE and WAPE (sum of absolute errors / sum of actual demand).
"""
import argparse
import sys
from pathlib import Path
from statistics import NormalDist

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

# The Olist data is sparse in the first months of 2016 and in the last weeks of 2018.
START_WEEK = "2017-01-02"
END_WEEK = "2018-08-13"      # last full week used (weeks start on Monday)
TEST_WEEKS = 12
TOP_CATEGORIES = 10

# Assumptions for the inventory illustration. Olist sellers hold the stock, so this shows the method, not a real policy.
LEAD_TIME_WEEKS = 2
SERVICE_LEVEL = 0.95

FEATURES = ["lag_1", "lag_2", "lag_3", "lag_4", "roll_mean_4", "roll_mean_8", "week_of_year", "category_code"]
MODELS = ["naive_last_week", "moving_average_4", "gradient_boosting"]


def build_panel(weekly: pd.DataFrame, start: str = START_WEEK, end: str = END_WEEK,
                top_n: int = TOP_CATEGORIES) -> pd.DataFrame:
    """One row per (category, week) for the top categories, with missing weeks filled with 0 units."""
    weekly = weekly.copy()
    weekly["week_start"] = pd.to_datetime(weekly["week_start"])
    totals = weekly.groupby("category_en")["units"].sum().sort_values(ascending=False)
    keep = list(totals.head(top_n).index)
    weeks = pd.date_range(start, end, freq="W-MON")
    index = pd.MultiIndex.from_product([keep, weeks], names=["category_en", "week_start"])
    panel = (weekly[weekly["category_en"].isin(keep)]
             .set_index(["category_en", "week_start"])["units"]
             .reindex(index, fill_value=0)
             .astype(float)
             .reset_index())
    return panel


def add_features(panel: pd.DataFrame) -> pd.DataFrame:
    """Lag and rolling features. Every feature of week t uses only weeks before t."""
    panel = panel.sort_values(["category_en", "week_start"]).copy()
    grouped = panel.groupby("category_en")["units"]
    for lag in (1, 2, 3, 4):
        panel[f"lag_{lag}"] = grouped.shift(lag)
    shifted = grouped.shift(1)
    panel["roll_mean_4"] = shifted.groupby(panel["category_en"]).transform(lambda s: s.rolling(4).mean())
    panel["roll_mean_8"] = shifted.groupby(panel["category_en"]).transform(lambda s: s.rolling(8).mean())
    panel["week_of_year"] = panel["week_start"].dt.isocalendar().week.astype(int)
    panel["category_code"] = panel["category_en"].astype("category").cat.codes
    return panel.dropna(subset=["lag_1", "lag_2", "lag_3", "lag_4", "roll_mean_4", "roll_mean_8"]).reset_index(drop=True)


def wape(actual, predicted) -> float:
    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    total = actual.sum()
    return float(np.abs(actual - predicted).sum() / total) if total else float("nan")


def mae(actual, predicted) -> float:
    return float(np.mean(np.abs(np.asarray(actual, dtype=float) - np.asarray(predicted, dtype=float))))


def split_by_time(features: pd.DataFrame, test_weeks: int = TEST_WEEKS):
    weeks = sorted(features["week_start"].unique())
    cutoff = weeks[-test_weeks]
    train = features[features["week_start"] < cutoff]
    test = features[features["week_start"] >= cutoff].copy()
    return train, test


def fit_and_predict(train: pd.DataFrame, test: pd.DataFrame) -> pd.DataFrame:
    """Returns the test rows with one prediction column per model."""
    test = test.copy()
    test["naive_last_week"] = test["lag_1"]
    test["moving_average_4"] = test["roll_mean_4"]
    categorical = [FEATURES.index("category_code")]
    model = HistGradientBoostingRegressor(
        max_iter=200, learning_rate=0.05, max_depth=3, min_samples_leaf=20,
        categorical_features=categorical, random_state=42)
    model.fit(train[FEATURES], train["units"])
    test["gradient_boosting"] = np.clip(model.predict(test[FEATURES]), 0, None)
    return test


def score(test: pd.DataFrame) -> pd.DataFrame:
    rows = [{"model": m, "mae": mae(test["units"], test[m]), "wape": wape(test["units"], test[m])}
            for m in MODELS]
    return pd.DataFrame(rows)


def score_by_category(test: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for category, part in test.groupby("category_en"):
        row = {"category_en": category, "avg_weekly_units": part["units"].mean()}
        for m in MODELS:
            row[f"wape_{m}"] = wape(part["units"], part[m])
        rows.append(row)
    return pd.DataFrame(rows).sort_values("avg_weekly_units", ascending=False)


def inventory_policy(test: pd.DataFrame, model: str, lead_time_weeks: int = LEAD_TIME_WEEKS,
                     service_level: float = SERVICE_LEVEL) -> pd.DataFrame:
    """Safety stock and reorder point per category from the forecast error of the chosen model.

    safety stock  = z * std(forecast error) * sqrt(lead time in weeks)
    reorder point = average weekly forecast * lead time + safety stock
    """
    z = NormalDist().inv_cdf(service_level)
    rows = []
    for category, part in test.groupby("category_en"):
        error_std = float((part["units"] - part[model]).std(ddof=1))
        avg_forecast = float(part[model].mean())
        safety = z * error_std * np.sqrt(lead_time_weeks)
        rows.append({
            "category_en": category,
            "avg_weekly_forecast": avg_forecast,
            "forecast_error_std": error_std,
            "safety_stock": safety,
            "reorder_point": avg_forecast * lead_time_weeks + safety,
            "model": model,
            "lead_time_weeks": lead_time_weeks,
            "service_level": service_level,
        })
    return pd.DataFrame(rows).sort_values("avg_weekly_forecast", ascending=False)


def run_forecast(weekly: pd.DataFrame, start: str = START_WEEK, end: str = END_WEEK,
                 test_weeks: int = TEST_WEEKS, top_n: int = TOP_CATEGORIES) -> dict:
    panel = build_panel(weekly, start, end, top_n)
    features = add_features(panel)
    train, test = split_by_time(features, test_weeks)
    test = fit_and_predict(train, test)
    metrics = score(test)
    best = metrics.sort_values("wape").iloc[0]["model"]
    return {
        "metrics": metrics,
        "by_category": score_by_category(test),
        "inventory": inventory_policy(test, best),
        "forecast_vs_actual": test[["category_en", "week_start", "units"] + MODELS],
        "best_model": best,
        "train_weeks": int(train["week_start"].nunique()),
        "test_weeks": int(test["week_start"].nunique()),
    }


def main(argv=None) -> int:
    import duckdb

    parser = argparse.ArgumentParser(description="Weekly demand forecast for the Olist data")
    parser.add_argument("--db", default="data/olist.duckdb")
    parser.add_argument("--out", default="reports/forecast")
    args = parser.parse_args(argv)

    if not Path(args.db).is_file():
        print(f"{args.db} not found. Run `python -m olist.pipeline` first.")
        return 2
    con = duckdb.connect(args.db, read_only=True)
    try:
        weekly = con.execute("SELECT category_en, week_start, units FROM weekly_demand").df()
    except duckdb.CatalogException:
        print("weekly_demand view not found. Run `python -m olist.pipeline` again.")
        return 2
    finally:
        con.close()

    result = run_forecast(weekly)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    result["metrics"].to_csv(out / "forecast_metrics.csv", index=False)
    result["by_category"].to_csv(out / "forecast_by_category.csv", index=False)
    result["inventory"].to_csv(out / "inventory_policy.csv", index=False)
    result["forecast_vs_actual"].to_csv(out / "forecast_vs_actual.csv", index=False)

    print(f"Trained on {result['train_weeks']} weeks, tested on the last {result['test_weeks']} weeks "
          f"({TOP_CATEGORIES} categories, one-week-ahead forecast)\n")
    print(result["metrics"].round(3).to_string(index=False))
    print(f"\nBest model by WAPE: {result['best_model']}")
    print(f"\nInventory illustration ({LEAD_TIME_WEEKS}-week lead time, {int(SERVICE_LEVEL * 100)}% service level):")
    print(result["inventory"][["category_en", "avg_weekly_forecast", "safety_stock", "reorder_point"]]
          .round(1).to_string(index=False))
    print(f"\nFiles written to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
