"""
eda_analysis.py

Phase 7 exploratory data analysis. Reads the Phase 4 cleaned data and produces six
charts, each tied to one explicit business question, saved to images/eda/.

Color follows the dataviz-skill discipline: single-series magnitude comparisons get
one sequential hue (not a different color per bar), the trend chart uses an
emphasis treatment (context line in gray, the smoothed trend in the accent hue),
and the category x production-type comparison uses a sequential-hue heatmap since
it's a magnitude grid, not a categorical-identity chart.
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd

# Palette (validated categorical order + sequential blue), from the dataviz skill
BLUE = "#2a78d6"
GRAY = "#9a9a95"
TEXT = "#0b0b0b"
CAT_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100",
              "#e87ba4", "#008300", "#4a3aa7", "#e34948"]

plt.rcParams.update({
    "figure.facecolor": "white", "axes.facecolor": "white",
    "axes.edgecolor": "#d8d8d5", "axes.linewidth": 0.8,
    "axes.grid": True, "grid.color": "#ececeb", "grid.linewidth": 0.7,
    "text.color": TEXT, "axes.labelcolor": TEXT,
    "xtick.color": "#52514e", "ytick.color": "#52514e",
    "font.size": 10, "axes.titlesize": 12, "axes.titleweight": "bold",
    "axes.spines.top": False, "axes.spines.right": False,
})

OUT_DIR = "images/eda"


def load_data():
    fact = pd.read_csv("data/processed/fact_demand_weekly.csv", parse_dates=["week_start_date"])
    equip = pd.read_csv("data/processed/dim_equipment.csv")
    return fact.merge(equip[["sku_id", "equipment_category"]], on="sku_id")


def chart1_distribution(df):
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(df["units_requested"], bins=range(0, 60, 2), color=BLUE, edgecolor="white", linewidth=0.5)
    ax.set_xlim(0, 60)
    ax.set_title("Distribution of weekly demand per SKU-location-week")
    ax.set_xlabel("units_requested (capped at 60 for readability; max in data is 193)")
    ax.set_ylabel("number of SKU-location-weeks")
    fig.tight_layout()
    fig.savefig(f"{OUT_DIR}/01_demand_distribution.png", dpi=150)
    plt.close(fig)
    zero_pct = (df["units_requested"] == 0).mean() * 100
    over_20_pct = (df["units_requested"] > 20).mean() * 100
    return zero_pct, over_20_pct


def chart2_trend(df):
    weekly = df.groupby("week_start_date")["units_requested"].sum().reset_index()
    weekly["rolling_8wk"] = weekly["units_requested"].rolling(8, min_periods=1).mean()

    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(weekly["week_start_date"], weekly["units_requested"], color=GRAY, linewidth=1, label="Raw weekly total")
    ax.plot(weekly["week_start_date"], weekly["rolling_8wk"], color=BLUE, linewidth=2, label="8-week rolling average")
    ax.set_title("Total company-wide weekly demand over time")
    ax.set_ylabel("units_requested (all SKUs, all locations)")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.legend(frameon=False, loc="upper left")
    fig.tight_layout()
    fig.savefig(f"{OUT_DIR}/02_demand_trend.png", dpi=150)
    plt.close(fig)
    first_year_avg = weekly[weekly["week_start_date"].dt.year == 2024]["units_requested"].mean()
    last_year_avg = weekly[weekly["week_start_date"].dt.year == 2026]["units_requested"].mean()
    return first_year_avg, last_year_avg


def chart3_seasonality(df):
    monthly = df.groupby("month")["units_requested"].mean().reset_index()
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(monthly["month"], monthly["units_requested"], color=BLUE, width=0.6)
    ax.set_title("Average weekly demand by month (seasonality)")
    ax.set_xlabel("month")
    ax.set_ylabel("avg units_requested per SKU-location-week")
    ax.set_xticks(range(1, 13))
    fig.tight_layout()
    fig.savefig(f"{OUT_DIR}/03_seasonality.png", dpi=150)
    plt.close(fig)
    peak_month = int(monthly.loc[monthly["units_requested"].idxmax(), "month"])
    trough_month = int(monthly.loc[monthly["units_requested"].idxmin(), "month"])
    return peak_month, trough_month


def chart4_category_location(df):
    cat_totals = df.groupby("equipment_category")["units_requested"].sum().sort_values(ascending=False)
    loc_totals = df.groupby("location_id")["units_requested"].sum().sort_values(ascending=False)

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    axes[0].barh(cat_totals.index[::-1], cat_totals.values[::-1], color=BLUE)
    axes[0].set_title("Total demand by equipment category")
    axes[0].set_xlabel("total units_requested")

    axes[1].barh(loc_totals.index[::-1], loc_totals.values[::-1], color=BLUE)
    axes[1].set_title("Total demand by location")
    axes[1].set_xlabel("total units_requested")
    fig.tight_layout()
    fig.savefig(f"{OUT_DIR}/04_category_location.png", dpi=150)
    plt.close(fig)
    return cat_totals, loc_totals


def chart5_volatility(df):
    sku_stats = df.groupby("sku_id")["units_requested"].agg(["mean", "std"]).reset_index()
    sku_stats["cv"] = sku_stats["std"] / sku_stats["mean"].replace(0, np.nan)
    top10 = sku_stats.sort_values("cv", ascending=False).head(10)
    equip = pd.read_csv("data/processed/dim_equipment.csv")
    top10 = top10.merge(equip[["sku_id", "equipment_name"]], on="sku_id")

    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.barh(top10["equipment_name"][::-1], top10["cv"][::-1], color=BLUE)
    ax.set_title("10 most volatile SKUs (coefficient of variation)")
    ax.set_xlabel("coefficient of variation (std / mean)")
    fig.tight_layout()
    fig.savefig(f"{OUT_DIR}/05_volatility.png", dpi=150)
    plt.close(fig)
    return top10


def chart6_production_heatmap(df):
    active = df[df["production_type"] != "No Active Production"]
    pivot = active.pivot_table(index="equipment_category", columns="production_type",
                                values="units_requested", aggfunc="mean")
    # Order columns to match the affinity design discussed in Phase 2
    col_order = ["Feature Film", "Television", "Commercial", "Documentary", "Music Video"]
    pivot = pivot[col_order]

    fig, ax = plt.subplots(figsize=(8, 5.5))
    im = ax.imshow(pivot.values, cmap="Blues", aspect="auto")
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=30, ha="right")
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    ax.set_title("Average demand by equipment category x production type\n(active-production weeks only)")
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            val = pivot.values[i, j]
            text_color = "white" if val > pivot.values.max() * 0.6 else TEXT
            ax.text(j, i, f"{val:.1f}", ha="center", va="center", color=text_color, fontsize=9)
    fig.colorbar(im, ax=ax, label="avg units_requested", shrink=0.8)
    fig.tight_layout()
    fig.savefig(f"{OUT_DIR}/06_production_heatmap.png", dpi=150)
    plt.close(fig)
    return pivot


def main():
    import os
    os.makedirs(OUT_DIR, exist_ok=True)
    df = load_data()

    print("=== Chart 1: Demand distribution ===")
    zero_pct, over_20_pct = chart1_distribution(df)
    print(f"zero-demand weeks: {zero_pct:.1f}% | weeks with >20 units: {over_20_pct:.1f}%")

    print("\n=== Chart 2: Demand trend over time ===")
    first_year_avg, last_year_avg = chart2_trend(df)
    print(f"2024 avg weekly total: {first_year_avg:.0f} | 2026 (partial) avg weekly total: {last_year_avg:.0f}")

    print("\n=== Chart 3: Seasonality ===")
    peak_month, trough_month = chart3_seasonality(df)
    print(f"peak month: {peak_month} | trough month: {trough_month}")

    print("\n=== Chart 4: Category & location demand ===")
    cat_totals, loc_totals = chart4_category_location(df)
    print("category totals:\n", cat_totals)
    print("location totals:\n", loc_totals)

    print("\n=== Chart 5: SKU volatility ===")
    top10 = chart5_volatility(df)
    print(top10[["sku_id", "equipment_name", "mean", "std", "cv"]].to_string(index=False))

    print("\n=== Chart 6: Category x production-type heatmap ===")
    pivot = chart6_production_heatmap(df)
    print(pivot.round(2))

    print("\nAll charts saved to", OUT_DIR)


if __name__ == "__main__":
    main()
