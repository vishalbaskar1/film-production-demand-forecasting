"""
inventory_analysis.py

Phase 11: safety stock, reorder point, and stockout-risk classification.

Design decisions (from Phase 0, restated here since this is where they get
implemented):
  - Lead-time demand is FORECAST-based, not a simple historical average. Each
    SKU-location's average Random Forest forecast over the Phase 8/9 test
    period is treated as "current expected weekly demand," then scaled by
    lead time. Averaging across the 10 test weeks (rather than using only the
    single most recent week) avoids basing an inventory decision on one
    noisy week.
  - Safety stock uses the CATEGORY-POOLED forecast-error standard deviation
    from Phase 10 (data/processed/forecast_error_by_category.csv), not a
    per-SKU std -- individual SKU-location series don't have enough test
    observations (10 weeks) to estimate a stable std on their own.
  - Service level: 95% (Z computed exactly via scipy.stats.norm.ppf, not a
    hardcoded approximation).
  - Safety stock formula: Z * sigma_error * sqrt(lead_time_weeks). The
    sqrt(lead time) scaling assumes each week's forecast error is roughly
    independent of the next -- reasonable here since the Random Forest's lag
    features already absorbed most of the week-to-week autocorrelation in
    demand, so what's left in sigma_error should be closer to independent
    noise.
  - Reorder quantity is a simple "bring on-hand back up to the reorder point"
    calculation, not a full EOQ (economic order quantity) optimization --
    this dataset has no real cost-of-ordering data to justify that level of
    sophistication.
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import norm

SERVICE_LEVEL = 0.95
BLUE = "#2a78d6"
GRAY = "#9a9a95"
RED = "#e34948"
AMBER = "#eda100"
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

OUT_DIR = "images/inventory"


def load_inputs():
    preds = pd.read_csv("data/processed/test_predictions_with_rf.csv", parse_dates=["week_start_date"])
    equip = pd.read_csv("data/processed/dim_equipment.csv")
    inv = pd.read_csv("data/processed/inventory_snapshot.csv")
    cat_error = pd.read_csv("data/processed/forecast_error_by_category.csv")
    return preds, equip, inv, cat_error


def compute_avg_forecast_demand(preds):
    """Average Random Forest forecast per SKU-location across the test period
    -- treated as the current expected weekly demand rate."""
    return (
        preds.groupby(["sku_id", "location_id"])["rf_forecast"]
        .mean()
        .reset_index()
        .rename(columns={"rf_forecast": "avg_weekly_forecast_demand"})
    )


def build_inventory_table(preds, equip, inv, cat_error):
    z = norm.ppf(SERVICE_LEVEL)

    avg_demand = compute_avg_forecast_demand(preds)

    table = inv.merge(equip[["sku_id", "equipment_name", "equipment_category", "lead_time_days"]],
                       on="sku_id", how="left")
    table = table.merge(avg_demand, on=["sku_id", "location_id"], how="left")
    table = table.merge(cat_error[["equipment_category", "std_error"]], on="equipment_category", how="left")

    table["lead_time_weeks"] = table["lead_time_days"] / 7.0
    table["lead_time_demand"] = table["avg_weekly_forecast_demand"] * table["lead_time_weeks"]
    table["safety_stock"] = z * table["std_error"] * np.sqrt(table["lead_time_weeks"])
    table["reorder_point"] = table["lead_time_demand"] + table["safety_stock"]

    table["weeks_of_cover"] = table["on_hand_qty"] / table["avg_weekly_forecast_demand"].replace(0, np.nan)

    def classify(row):
        if row["on_hand_qty"] < row["safety_stock"]:
            return "Critical"
        elif row["on_hand_qty"] < row["reorder_point"]:
            return "Reorder Now"
        else:
            return "OK"

    table["risk_status"] = table.apply(classify, axis=1)
    table["reorder_qty_recommended"] = (table["reorder_point"] - table["on_hand_qty"]).clip(lower=0).round().astype(int)

    for col in ["lead_time_weeks", "lead_time_demand", "safety_stock", "reorder_point", "weeks_of_cover"]:
        table[col] = table[col].round(2)

    return table, z


def chart_risk_by_category(table):
    counts = table.groupby(["equipment_category", "risk_status"]).size().unstack(fill_value=0)
    for col in ["OK", "Reorder Now", "Critical"]:
        if col not in counts.columns:
            counts[col] = 0
    counts = counts[["OK", "Reorder Now", "Critical"]]
    counts = counts.loc[counts.sum(axis=1).sort_values(ascending=True).index]

    fig, ax = plt.subplots(figsize=(8, 5))
    left = np.zeros(len(counts))
    for status, color in [("OK", GRAY), ("Reorder Now", AMBER), ("Critical", RED)]:
        ax.barh(counts.index, counts[status], left=left, color=color, label=status)
        left += counts[status].values
    ax.set_xlabel("number of SKU-locations")
    ax.set_title("Inventory risk status by equipment category")
    ax.legend(frameon=False, loc="lower right")
    fig.tight_layout()
    fig.savefig(f"{OUT_DIR}/01_risk_by_category.png", dpi=150)
    plt.close(fig)


def main():
    import os
    os.makedirs(OUT_DIR, exist_ok=True)

    preds, equip, inv, cat_error = load_inputs()
    table, z = build_inventory_table(preds, equip, inv, cat_error)

    print(f"Service level: {SERVICE_LEVEL:.0%}  ->  Z = {z:.4f} (scipy.stats.norm.ppf({SERVICE_LEVEL}))")
    print(f"SKU-locations evaluated: {len(table)}")

    print("\n=== Risk status counts ===")
    print(table["risk_status"].value_counts().to_string())

    print("\n=== Risk status by equipment category ===")
    print(table.groupby(["equipment_category", "risk_status"]).size().unstack(fill_value=0))

    print("\n=== Sample: 10 highest-priority reorder recommendations (Critical first, then largest gap) ===")
    priority = table.copy()
    priority["_status_rank"] = priority["risk_status"].map({"Critical": 0, "Reorder Now": 1, "OK": 2})
    priority = priority.sort_values(["_status_rank", "reorder_qty_recommended"], ascending=[True, False])
    display_cols = ["sku_id", "equipment_name", "location_id", "on_hand_qty", "avg_weekly_forecast_demand",
                     "lead_time_demand", "safety_stock", "reorder_point", "risk_status", "reorder_qty_recommended"]
    print(priority[display_cols].head(10).to_string(index=False))

    chart_risk_by_category(table)

    table.to_csv("data/processed/inventory_recommendations.csv", index=False)
    print("\nSaved: data/processed/inventory_recommendations.csv")
    print("Saved chart to", OUT_DIR)


if __name__ == "__main__":
    main()
