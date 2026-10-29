import numpy as np
import pandas as pd
import pytest

from olist import forecast


def synthetic_weekly(weeks=80, categories=("a", "b", "c"), seed=0):
    """Weekly demand with a trend, a yearly pattern and noise. Some weeks are missing on purpose."""
    rng = np.random.default_rng(seed)
    start = pd.Timestamp("2017-01-02")
    rows = []
    for k, category in enumerate(categories):
        for w in range(weeks):
            if w % 17 == 5:   # a week without any sale: no row
                continue
            base = 20 * (k + 1) + 0.4 * w + 5 * np.sin(2 * np.pi * w / 52)
            rows.append({"category_en": category, "week_start": start + pd.Timedelta(weeks=w),
                         "units": max(0, int(base + rng.normal(0, 3)))})
    return pd.DataFrame(rows)


def test_panel_fills_missing_weeks_with_zero_and_keeps_top_categories():
    weekly = synthetic_weekly()
    panel = forecast.build_panel(weekly, start="2017-01-02", end="2018-07-02", top_n=2)
    assert set(panel["category_en"]) == {"c", "b"}              # the two largest
    per_category = panel.groupby("category_en").size()
    assert (per_category == len(pd.date_range("2017-01-02", "2018-07-02", freq="W-MON"))).all()
    week5 = panel[(panel["category_en"] == "c") & (panel["week_start"] == pd.Timestamp("2017-01-02") + pd.Timedelta(weeks=5))]
    assert week5["units"].iloc[0] == 0


def test_features_only_use_the_past():
    weekly = synthetic_weekly()
    panel = forecast.build_panel(weekly, start="2017-01-02", end="2018-07-02", top_n=3)
    features = forecast.add_features(panel)
    units = panel.set_index(["category_en", "week_start"])["units"]
    for _, row in features.sample(20, random_state=1).iterrows():
        previous = row["week_start"] - pd.Timedelta(weeks=1)
        assert row["lag_1"] == units[(row["category_en"], previous)]
        last4 = [units[(row["category_en"], row["week_start"] - pd.Timedelta(weeks=n))] for n in (1, 2, 3, 4)]
        assert row["roll_mean_4"] == pytest.approx(np.mean(last4))


def test_split_is_by_time_and_has_no_overlap():
    weekly = synthetic_weekly()
    features = forecast.add_features(forecast.build_panel(weekly, "2017-01-02", "2018-07-02", 3))
    train, test = forecast.split_by_time(features, test_weeks=12)
    assert train["week_start"].max() < test["week_start"].min()
    assert test["week_start"].nunique() == 12


def test_metrics_by_hand():
    actual, predicted = [10, 20, 30], [12, 18, 30]
    assert forecast.mae(actual, predicted) == pytest.approx(4 / 3)
    assert forecast.wape(actual, predicted) == pytest.approx(4 / 60)
    assert np.isnan(forecast.wape([0, 0], [1, 1]))


def test_inventory_formula_with_known_numbers():
    test = pd.DataFrame({
        "category_en": ["a"] * 4,
        "units": [10.0, 14.0, 10.0, 14.0],
        "gradient_boosting": [12.0, 12.0, 12.0, 12.0],   # errors -2, +2, -2, +2
    })
    policy = forecast.inventory_policy(test, "gradient_boosting", lead_time_weeks=4, service_level=0.975)
    row = policy.iloc[0]
    std = np.std([-2, 2, -2, 2], ddof=1)
    z = 1.959964                                          # 97.5 % service level
    assert row["forecast_error_std"] == pytest.approx(std)
    assert row["safety_stock"] == pytest.approx(z * std * 2, rel=1e-4)   # sqrt(4 weeks) = 2
    assert row["reorder_point"] == pytest.approx(12 * 4 + z * std * 2, rel=1e-4)


def test_full_run_on_synthetic_data():
    result = forecast.run_forecast(synthetic_weekly(), start="2017-01-02", end="2018-07-02",
                                   test_weeks=12, top_n=3)
    metrics = result["metrics"].set_index("model")
    assert set(metrics.index) == set(forecast.MODELS)
    assert metrics["wape"].between(0, 1).all()
    assert result["test_weeks"] == 12
    assert result["best_model"] in forecast.MODELS
    assert len(result["forecast_vs_actual"]) == 12 * 3
    assert (result["inventory"]["safety_stock"] >= 0).all()
    # the data is a smooth trend plus small noise, so a learned model must beat "same as last week" by a margin
    assert metrics.loc["moving_average_4", "wape"] < 0.25
