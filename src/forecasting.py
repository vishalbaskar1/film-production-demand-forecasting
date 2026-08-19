"""
forecasting.py

Phase 8: naive and moving-average forecasting baselines, with a time-aware
train/test split.
Phase 9: Random Forest model trained on lag/rolling/calendar/categorical
features, evaluated on the exact same held-out test period as the baselines.
Phase 10 will add the full evaluation comparison table / writeup.

Forecast level: SKU-location-week (matches Phase 0 design decision).
Test period: the most recent 10 weeks of the 130-week window (~92% train / ~8% test).

Phase 9 note: dim_equipment.csv has a "popularity_factor" column that was used
directly to generate synthetic demand in generate_data.py (it's a multiplier on
expected_demand). It is deliberately EXCLUDED from the model features below --
using it would mean handing the model the generator's own hidden dial rather than
letting it learn from realistic signals. Instead we engineer sku_train_avg_demand,
fit only on training-period rows, as the honest stand-in for "this SKU's typical
demand level."
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor

TEST_WEEKS = 10
MA_WINDOW = 4
CATEGORICAL_COLS = ["equipment_category", "location_id", "production_type", "production_size"]

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


# ---------------------------------------------------------------------------
# Phase 9: feature engineering + Random Forest
# ---------------------------------------------------------------------------

def build_features(df, cutoff_date):
    """Builds the model feature table. Must be called on the output of
    add_baseline_forecasts() (needs naive_forecast / ma4_forecast already present).

    Every feature here is leak-safe by one of these routes:
      - lag_1..lag_4 and rolling_4wk_std: shift-based, can only look backward
        (same pattern as add_baseline_forecasts).
      - naive_forecast / ma4_forecast: already-validated Phase 8 outputs.
      - month/quarter/week_of_year/is_production_active/production_type/
        production_size: calendar facts or production context assumed known
        ahead of the week (production schedules are locked in pre-production).
      - equipment_category/location_id: static attributes, one-hot encoded.
      - sku_train_avg_demand: fit ONLY on rows strictly before cutoff_date,
        then applied to every row (train and test) -- the same "fit on train,
        apply to test" rule you'd use for any encoder/scaler in a real pipeline.
    """
    equip = pd.read_csv("data/processed/dim_equipment.csv")[["sku_id", "equipment_category"]]
    df = df.merge(equip, on="sku_id", how="left")

    df = df.sort_values(["sku_id", "location_id", "week_start_date"]).copy()
    grouped = df.groupby(["sku_id", "location_id"])["units_requested"]

    for lag in [1, 2, 3, 4]:
        df[f"lag_{lag}"] = grouped.shift(lag)

    df["rolling_4wk_std"] = grouped.transform(
        lambda s: s.shift(1).rolling(MA_WINDOW, min_periods=MA_WINDOW).std()
    )

    train_mask = df["week_start_date"] < cutoff_date
    sku_train_avg = df.loc[train_mask].groupby("sku_id")["units_requested"].mean()
    df["sku_train_avg_demand"] = df["sku_id"].map(sku_train_avg)

    # location_id doubles as both a row identifier and a one-hot feature -- get_dummies
    # would otherwise consume the original column, so keep an untouched copy for output/joins.
    df["location_label"] = df["location_id"]

    df = pd.get_dummies(df, columns=CATEGORICAL_COLS, drop_first=False)
    return df

def get_feature_columns(df):
    base = ["lag_1", "lag_2", "lag_3", "lag_4", "rolling_4wk_std",
             "naive_forecast", "ma4_forecast", "sku_train_avg_demand",
             "month", "quarter", "week_of_year", "is_production_active"]
    dummy_cols = [c for c in df.columns if c.startswith(tuple(f"{col}_" for col in CATEGORICAL_COLS))]
    return base + dummy_cols

def train_random_forest(train_df, test_df, feature_cols):
    X_train = train_df[feature_cols]
    y_train = train_df["units_requested"]
    X_test = test_df[feature_cols]

    model = RandomForestRegressor(
        n_estimators=200, max_depth=12, min_samples_leaf=5,
        random_state=42, n_jobs=-1,
    )
    model.fit(X_train, y_train)
    preds = model.predict(X_test)
    return model, preds

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

    # ------------------------------------------------------------------
    # Phase 9: Random Forest
    # ------------------------------------------------------------------
    print("\n\n=== Phase 9: Random Forest ===")
    featured = build_features(full, cutoff_date)
    feature_cols = get_feature_columns(featured)

    train_all = featured[featured["week_start_date"] < cutoff_date]
    test_all = featured[featured["week_start_date"] >= cutoff_date]
    train_feat = train_all.dropna(subset=feature_cols)
    test_feat = test_all.dropna(subset=feature_cols)

    print(f"Feature columns ({len(feature_cols)}): {feature_cols}")
    print(f"Train rows: {len(train_feat)} (out of {len(train_all)}; "
          f"{len(train_all) - len(train_feat)} dropped -- first {MA_WINDOW} weeks of each "
          f"SKU-location series, which don't have a full lag_4 history yet)")
    print(f"Test rows:  {len(test_feat)} (out of {len(test_all)}; none dropped, same as Phase 8)")

    model, preds = train_random_forest(train_feat, test_feat, feature_cols)
    rf_metrics = compute_metrics(test_feat["units_requested"], preds)

    print("\n=== Full comparison on test period: baselines vs. Random Forest ===")
    comparison_full = pd.DataFrame({
        "Naive (last week)": naive_metrics,
        "4-week Moving Average": ma4_metrics,
        "Random Forest": rf_metrics,
    }).T
    print(comparison_full.round(3))

    importances = pd.Series(model.feature_importances_, index=feature_cols).sort_values(ascending=False)
    print("\nTop 10 feature importances:")
    print(importances.head(10).round(4).to_string())

    test_out = test_feat[["sku_id", "location_label", "week_start_date", "units_requested",
                            "naive_forecast", "ma4_forecast"]].copy()
    test_out = test_out.rename(columns={"location_label": "location_id"})
    test_out["rf_forecast"] = preds
    test_out.to_csv("data/processed/test_predictions_with_rf.csv", index=False)
    print("\nSaved: data/processed/test_predictions_with_rf.csv")

    full.to_csv("data/processed/fact_demand_weekly_with_baselines.csv", index=False)
    print("Saved: data/processed/fact_demand_weekly_with_baselines.csv")


if __name__ == "__main__":
    main()
