"""
evaluate_forecasts.py

Phase 10: formal evaluation of the Phase 8/9 forecasts on the held-out test
period. Produces:
  - a consolidated MAE/RMSE/WAPE comparison table (naive, MA4, Random Forest),
    recomputed from the saved predictions as a reproducibility check.
  - forecast error broken down by equipment_category, for the winning model
    (Random Forest) -- saved to forecast_error_by_category.csv, which is a
    direct input to Phase 11's safety stock formula (category-pooled
    forecast-error standard deviation, per the Phase 0 design decision).
  - three diagnostic charts: actual vs. predicted scatter, residual
    distribution, and WAPE by category.

Reads data/processed/test_predictions_with_rf.csv (Phase 9 output) rather than
retraining the model -- evaluation should be reproducible from saved
predictions alone.
"""

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from forecasting import compute_metrics

BLUE = "#2a78d6"
GRAY = "#9a9a95"
RED = "#e34948"
TEXT = "#0b0b0b"

plt.rcParams.update({
    "figure.facecolor": "white", "axes.facecolor": "white",
    "axes.edgecolor": "#d8d8d5", "axes.linewidth": 0.8,
    "axes.grid": True, "grid.color": "#ececeb", "grid.linewidth": 0.7,
    "text.color": TEXT, "axes.labelcolor": TEXT,
    "xtick.color": "#52514e", "ytick.color": "#52514e",
    "font.size": 10, "axes.titlesize": 12, "axes.titleweight": "bold",
    "axes.spines.top": False, "axes.spines.right": False,
})

OUT_DIR = "images/evaluation"


def load_predictions():
    preds = pd.read_csv("data/processed/test_predictions_with_rf.csv", parse_dates=["week_start_date"])
    equip = pd.read_csv("data/processed/dim_equipment.csv")[["sku_id", "equipment_category"]]
    return preds.merge(equip, on="sku_id", how="left")


def comparison_table(df):
    naive = compute_metrics(df["units_requested"], df["naive_forecast"])
    ma4 = compute_metrics(df["units_requested"], df["ma4_forecast"])
    rf = compute_metrics(df["units_requested"], df["rf_forecast"])
    return pd.DataFrame({"Naive (last week)": naive, "4-week Moving Average": ma4, "Random Forest": rf}).T


def error_by_category(df):
    """Forecast error (actual - rf_forecast) pooled by equipment_category.
    Pooling gives each category roughly (10 test weeks) x (# SKUs in category)
    x (4 locations) error observations -- hundreds, versus only ~10 if computed
    per individual SKU-location series, which is too few to estimate a stable
    standard deviation from."""
    df = df.copy()
    df["error"] = df["units_requested"] - df["rf_forecast"]
    summary = df.groupby("equipment_category").agg(
        n_observations=("error", "size"),
        mean_error=("error", "mean"),
        std_error=("error", "std"),
        mae=("error", lambda e: np.mean(np.abs(e))),
    ).reset_index()

    wape_rows = []
    for cat, g in df.groupby("equipment_category"):
        wape_rows.append({
            "equipment_category": cat,
            "wape": np.sum(np.abs(g["units_requested"] - g["rf_forecast"])) / np.sum(np.abs(g["units_requested"])),
        })
    wape = pd.DataFrame(wape_rows)

    summary = summary.merge(wape, on="equipment_category")
    return summary.sort_values("wape", ascending=False)


def chart_actual_vs_predicted(df):
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.scatter(df["rf_forecast"], df["units_requested"], color=BLUE, alpha=0.35, s=18, edgecolor="none")
    max_val = max(df["units_requested"].max(), df["rf_forecast"].max())
    ax.plot([0, max_val], [0, max_val], color=GRAY, linewidth=1.5, linestyle="--", label="Perfect prediction")
    ax.set_xlabel("Random Forest forecast (units)")
    ax.set_ylabel("Actual demand (units)")
    ax.set_title("Actual vs. predicted demand (test period)")
    ax.legend(frameon=False, loc="upper left")
    fig.tight_layout()
    fig.savefig(f"{OUT_DIR}/01_actual_vs_predicted.png", dpi=150)
    plt.close(fig)


def chart_residuals(df):
    residuals = df["units_requested"] - df["rf_forecast"]
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(residuals, bins=40, color=BLUE, edgecolor="white", linewidth=0.5)
    ax.axvline(0, color=RED, linewidth=1.5, linestyle="--", label="Zero error")
    ax.set_xlabel("Residual (actual - forecast)")
    ax.set_ylabel("count of SKU-location-weeks")
    ax.set_title("Random Forest residual distribution (test period)")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(f"{OUT_DIR}/02_residual_distribution.png", dpi=150)
    plt.close(fig)
    return residuals.mean(), residuals.std()


def chart_wape_by_category(cat_summary):
    cat_summary = cat_summary.sort_values("wape")
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.barh(cat_summary["equipment_category"], cat_summary["wape"] * 100, color=BLUE)
    ax.set_xlabel("WAPE (%)")
    ax.set_title("Random Forest WAPE by equipment category (test period)")
    fig.tight_layout()
    fig.savefig(f"{OUT_DIR}/03_wape_by_category.png", dpi=150)
    plt.close(fig)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    df = load_predictions()

    print(f"Test predictions loaded: {len(df)} rows, {df['week_start_date'].nunique()} weeks, "
          f"{df['sku_id'].nunique()} SKUs, {df['equipment_category'].nunique()} categories")

    table = comparison_table(df)
    print("\n=== Final model comparison (recomputed from saved predictions) ===")
    print(table.round(3))

    mean_resid, std_resid = chart_residuals(df)
    print(f"\nRandom Forest residual mean: {mean_resid:.3f} (near 0 = no systematic bias), "
          f"std: {std_resid:.3f}")

    chart_actual_vs_predicted(df)

    cat_summary = error_by_category(df)
    print("\n=== Forecast error by equipment category (Random Forest) ===")
    print(cat_summary.round(3).to_string(index=False))

    chart_wape_by_category(cat_summary)

    cat_summary.to_csv("data/processed/forecast_error_by_category.csv", index=False)
    print("\nSaved: data/processed/forecast_error_by_category.csv (Phase 11 safety stock input)")
    print("Saved charts to", OUT_DIR)


if __name__ == "__main__":
    main()
