# Film Production Demand Forecasting & Inventory Dashboard

An end-to-end business analytics and supply chain project: forecasting equipment demand and generating
inventory reorder recommendations for a fictional film-production equipment rental company, **CineStock
Production Rentals**. Built with Python, SQL/SQLite, time-series forecasting, and Tableau.

**Live dashboard:** https://public.tableau.com/views/CineStockInventoryRiskReorderDashboard/InventoryRiskOverview

## Business Problem

> Which equipment SKUs are at risk of insufficient inventory during upcoming production periods, and what
> inventory or reorder actions should operations teams take?

CineStock rents cameras, lenses, lighting, audio, grip equipment, monitors, batteries, and drones to film
productions across 4 locations. This project builds a pipeline that forecasts weekly demand per SKU per
location, evaluates that forecast honestly against a simple baseline, and converts the forecast into
statistically-grounded safety stock, reorder points, and stockout-risk flags — then surfaces all of it in an
interactive dashboard an operations team could actually use.

## About the Data

**This project uses a synthetic dataset generated specifically for this project — it is not real company
data**, and nothing in this repository, the dashboard, or the write-ups should be read as describing a real
company's actual operations. The dataset is a dense weekly panel: 75 SKUs × 4 locations × 8 equipment
categories, spanning 130 weeks (~2.5 years) of simulated rental demand, generated with realistic but
artificial patterns (seasonality, production-type affinity, occasional demand spikes, and inventory levels
deliberately uncorrelated with demand so that real stockout risk emerges from the analysis rather than being
built in). Full generation logic and assumptions are documented in `src/generate_data.py`.

## Repository Structure

```
film-production-demand-forecasting/
├── data/
│   ├── raw/            synthetic data as generated
│   ├── processed/      cleaned tables + analysis outputs (forecasts, error metrics, inventory recs)
│   └── outputs/         flat, joined CSVs exported for Tableau
├── database/           SQLite database (production_inventory.db)
├── sql/                 business-analysis SQL queries (data quality, demand, inventory, dashboard exports)
├── notebooks/           01_eda.ipynb — exploratory data analysis notebook
├── src/                 pipeline scripts, run in order (see "How to Reproduce" below)
├── tableau/             packaged Tableau workbook (.twbx)
├── images/              saved charts (EDA, evaluation, inventory) referenced throughout this README
└── docs/
    └── business_insights.md   full write-up of findings, in business language
```

## Methodology

The pipeline runs in the following stages; each stage's script lives in `src/`.

1. **Data generation** (`generate_data.py`) — synthetic weekly demand panel with realistic seasonality,
   production-type/category affinity, and Poisson demand with occasional spikes.
2. **Data validation** (`validate_data.py`) — an 11-section check (shape, nulls, duplicates, referential
   integrity, panel completeness, outliers, and more) run against the raw data before anything downstream
   trusts it.
3. **Data cleaning** (`clean_data.py`) — fills non-production weeks, adds calendar features, writes the
   cleaned tables to `data/processed/`.
4. **SQLite database** (`database.py`) — loads the cleaned data into a star-schema SQLite database
   (`dim_equipment`, `dim_location`, `fact_demand_weekly`, `inventory_snapshot`), plus two additional tables
   added later for the forecast and inventory outputs (`forecast_results`, `inventory_recommendations`) —
   deliberately normalized so nothing is duplicated across tables. Foreign-key integrity is verified on every
   run via `PRAGMA foreign_key_check`.
5. **SQL business analysis** (`sql/01_data_quality.sql`–`03_inventory_analysis.sql`) — CTEs, joins, window
   functions (rolling averages, `RANK()`), and aggregations answering real operational questions directly in
   SQL, explorable against the database with any SQLite client.
6. **Exploratory data analysis** (`eda_analysis.py`, `notebooks/01_eda.ipynb`) — demand distribution, trend,
   seasonality, category/location breakdowns, and volatility, saved to `images/eda/`.
7. **Baseline forecasting** (`forecasting.py`) — a time-aware train/test split (last 10 of 130 weeks held out)
   with two baselines: naive (last observed week) and a 4-week moving average.
8. **Random Forest forecasting** (`forecasting.py`, extended) — lag features, rolling volatility, calendar
   features, and one-hot encoded categorical context, trained only on the training window to avoid leakage.
9. **Forecast evaluation** (`evaluate_forecasts.py`) — MAE, RMSE, and WAPE recomputed from saved predictions
   (a reproducibility check), plus diagnostic charts (actual-vs-predicted, residuals, WAPE by category) in
   `images/evaluation/`.
10. **Inventory analytics** (`inventory_analysis.py`) — safety stock, reorder points, and a 3-tier
    stockout-risk classification (Critical / Reorder Now / OK), using category-pooled forecast-error standard
    deviation at a 95% service level.
11. **Dashboard data export** (`export_dashboard_data.py`, `sql/04_dashboard_queries.sql`) — flat, joined CSVs
    written to `data/outputs/` for Tableau to connect to directly (no SQLite driver required).
12. **Tableau dashboard** — an interactive dashboard (KPI tiles, risk-by-category, forecast-vs-actual,
    reorder-priority table, with category and location filters), published to Tableau Public.

## Key Results

| Model | MAE | RMSE | WAPE |
|---|---|---|---|
| Naive (last week) | 5.22 | 8.43 | 96.0% |
| 4-week moving average | 4.29 | 6.73 | 78.9% |
| Random Forest | 2.60 | 4.90 | 47.8% |

The Random Forest model reduces forecast error by **39.4%** (relative WAPE) versus the moving-average
baseline. It is not equally accurate everywhere, though — it performs worst (highest WAPE) on Drone and
Camera equipment, and has a small systematic tendency to under-predict demand spikes rather than routine
weeks. Both limitations are discussed honestly, with supporting charts, in `docs/business_insights.md`.

Using that forecast, the inventory analysis classifies all 300 SKU-location combinations:

- **231 OK**, **38 Reorder Now**, **31 Critical** — 23% of the catalog needs attention right now.
- **302 total units** recommended for reorder across all at-risk SKU-locations.
- Risk is concentrated, not evenly spread: Drone (63.9% of its SKU-locations at risk) and Camera (42.5%,
  and the largest share of total units to reorder) account for the majority of the reorder burden — directly
  traceable to those two categories also having the worst forecast accuracy.

See `docs/business_insights.md` for the full findings, including the top individual reorder priorities,
stated assumptions, and what a real deployment would need beyond this project's scope.

## Dashboard

The finished dashboard is published to Tableau Public:
**https://public.tableau.com/views/CineStockInventoryRiskReorderDashboard/InventoryRiskOverview**

It includes: KPI tiles (critical count, reorder-now count, total units to reorder), a risk-by-category
breakdown, a forecast-vs-actual trend view, and a full reorder-priority table — all cross-filterable by
equipment category and location. The packaged workbook (`.twbx`) is also included in `tableau/` for anyone
who wants to open the underlying build in Tableau Desktop or Tableau Public.

## Limitations and Assumptions

Full detail is in `docs/business_insights.md`; in short:

- All data is synthetic; findings describe patterns in this generated dataset, not a real business.
- Safety stock uses category-pooled (not per-SKU) forecast-error variance, since 10 test weeks per
  SKU-location isn't enough to estimate a stable per-SKU standard deviation.
- Reorder quantities are a simple gap-fill to the reorder point, not a full economic-order-quantity (EOQ)
  optimization — this dataset has no real ordering/holding cost data to support that.
- The forecast is more reliable for typical weeks than for unusual demand spikes.
- This is a single point-in-time snapshot, not a continuously-updating system.

## How to Reproduce

```bash
# 1. Clone and install dependencies
git clone <this-repo>
cd film-production-demand-forecasting
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 2. Run the pipeline in order (each step's outputs feed the next)
python src/generate_data.py          # data/raw/
python src/validate_data.py          # data quality checks against data/raw/
python src/clean_data.py             # data/processed/
python src/eda_analysis.py           # images/eda/
python src/forecasting.py            # baseline + Random Forest, data/processed/test_predictions_with_rf.csv
python src/evaluate_forecasts.py     # images/evaluation/, forecast_error_by_category.csv
python src/inventory_analysis.py     # inventory_recommendations.csv, images/inventory/
python src/database.py               # database/production_inventory.db (run last — loads all tables, incl. forecast/inventory results)
python src/export_dashboard_data.py  # data/outputs/*.csv, for Tableau

# 3. Explore the SQL analysis (optional)
sqlite3 database/production_inventory.db < sql/01_data_quality.sql

# 4. Open the Tableau workbook (tableau/*.twbx) in Tableau Desktop/Public,
#    or view the published dashboard link above directly.
```

Note: `src/database.py` must be run **after** the forecasting and inventory scripts, since it loads their
output CSVs into the database alongside the core dimension/fact tables — running it earlier will fail with a
missing-file error.

## Tech Stack

Python (pandas, NumPy, scikit-learn, SciPy, Matplotlib) · SQL / SQLite · Tableau · Git/GitHub

## Author

Vishal Baskar — Business Analytics & AI / Supply Chain Management & Analytics, University of Texas at Dallas
