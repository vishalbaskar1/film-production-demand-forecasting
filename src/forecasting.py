"""
forecasting.py

Phase 8: naive and moving-average forecasting baselines, with a time-aware
train/test split. Phase 9 will add the Random Forest model to this same file;
Phase 10 will add the full evaluation comparison table.

Forecast level: SKU-location-week (matches Phase 0 design decision).
Test period: the most recent 10 weeks of the 130-week window (~92% train / ~8% test).
"""

import numpy as np
import pandas as pd

TEST_WEEKS = 10


def load_fact():
    return pd.read_csv("data/processed/fact_demand_weekly.csv", parse_dates=["week_start_date"])


def time_aware_split(df):
    """Split by a global date cutoff -- NOT a random shuffle. Train = everything
    strictly before the cutoff; test = the last TEST_WEEKS calendar weeks."""
    all_weeks = sorted(df["week_start_date"].unique())
    cutoff_date = all_weeks[-TEST_WEEKS]
    train = df[df["week_start_date"] < cutoff_date].copy()
    test = df[df["week_start_date"] >= cutoff_date].copy()
    return train, test, cutoff_date


def add_baseline_forecasts(df, ma_window=4):
    """Adds naive_forecast and ma{window}_forecast columns to the FULL panel
    (train+test together), computed per SKU-location series, sorted by date.

    Both forecasts use .shift(1) before any averaging, so week t's forecast is
    built only from actuals at week t-1 and earlier -- it structurally cannot
    see week t's own value. This is what makes the split "time-aware safe" even
    though train and test rows are processed together here.
    """
    df = df.sort_values(["sku_id", "location_id", "week_start_date"]).copy()
    grouped = df.groupby(["sku_id", "location_id"])["units_requested"]

    # Naive: forecast(t) = actual(t-1)
    df["naive_forecast"] = grouped.shift(1)

    # Moving average: forecast(t) = mean(actual(t-4) ... actual(t-1)).
    # Uses transform() with a lambda that does shift(1) FIRST (excludes today),
    # THEN rolling(4) -- and transform() keeps the rolling window scoped to each
    # SKU-location group. (A plain grouped.shift(1).rolling(4) would compute the
    # rolling window across the whole sorted table, bleeding across group
    # boundaries -- that was the bug in the first version of this function.)
    df[f"ma{ma_window}_forecast"] = grouped.transform(
        lambda s: s.shift(1).rolling(ma_window, min_periods=ma_window).mean()
    )
    return df


def compute_metrics(actual, forecast):
    """MAE, RMSE, WAPE over the given rows. WAPE (sum of absolute errors / sum
    of actuals) is used instead of MAPE because MAPE is undefined/explodes on
    the many zero-demand weeks in this dataset."""
    actual = np.asarray(actual, dtype=float)
    forecast = np.asarray(forecast, dtype=float)
    errors = actual - forecast
    mae = np.mean(np.abs(errors))
    rmse = np.sqrt(np.mean(errors ** 2))
    wape = np.sum(np.abs(errors)) / np.sum(np.abs(actual))
    return {"MAE": mae, "RMSE": rmse, "WAPE": wape}


def main():
    df = load_fact()
    train, test, cutoff_date = time_aware_split(df)

    print(f"Total weeks: {df['week_start_date'].nunique()}")
    print(f"Train: {train['week_start_date'].nunique()} weeks "
          f"({train['week_start_date'].min().date()} to {train['week_start_date'].max().date()}), {len(train)} rows")
    print(f"Test:  {test['week_start_date'].nunique()} weeks "
          f"({test['week_start_date'].min().date()} to {test['week_start_date'].max().date()}), {len(test)} rows")
    print(f"Cutoff date: {cutoff_date.date()}  (train strictly before this, test on/after)")
    assert train["week_start_date"].max() < test["week_start_date"].min(), "train/test overlap -- leakage!"
    print("Leakage check passed: max(train date) < min(test date)")

    full = add_baseline_forecasts(df, ma_window=4)

    # Leakage trace: show one SKU-location's raw numbers so the shift is visible, not just asserted
    sample = full[(full["sku_id"] == "SKU-053") & (full["location_id"] == "LOC-01")].sort_values("week_start_date")
    print("\nLeakage trace for SKU-053 / LOC-01 (first 8 weeks with a full 4-week window):")
    trace_cols = ["week_start_date", "units_requested", "naive_forecast", "ma4_forecast"]
    print(sample[trace_cols].dropna().head(8).to_string(index=False))

    # Evaluate on the test period only
    test_full = full[full["week_start_date"] >= cutoff_date].dropna(subset=["naive_forecast", "ma4_forecast"])
    print(f"\nTest rows evaluated: {len(test_full)} (out of {len(test)} total test rows; "
          f"none dropped, since all test weeks have 120 weeks of prior history)")

    naive_metrics = compute_metrics(test_full["units_requested"], test_full["naive_forecast"])
    ma4_metrics = compute_metrics(test_full["units_requested"], test_full["ma4_forecast"])

    print("\n=== Baseline comparison on test period ===")
    comparison = pd.DataFrame({"Naive (last week)": naive_metrics, "4-week Moving Average": ma4_metrics}).T
    print(comparison.round(3))

    full.to_csv("data/processed/fact_demand_weekly_with_baselines.csv", index=False)
    print("\nSaved: data/processed/fact_demand_weekly_with_baselines.csv")


if __name__ == "__main__":
    main()
