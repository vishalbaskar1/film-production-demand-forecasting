"""
export_dashboard_data.py

Phase 12: runs the three sql/04_dashboard_queries.sql queries against the
database and writes the results to data/outputs/ as plain CSVs -- these are
what Tableau Public will actually connect to in Phase 13.

Why flat CSVs instead of pointing Tableau at the SQLite database directly:
Tableau Public has no built-in SQLite connector (it would require installing
a separate ODBC driver, which is unnecessary friction for a portfolio
project). Its native "Text File" connector needs no setup at all, so exporting
clean, already-joined CSVs is the simpler and more standard approach.

The three queries below are the exact same SQL as sql/04_dashboard_queries.sql
(kept in sync manually -- the .sql file is the human-readable reference you'd
paste into DB Browser to explore, this script is what actually produces the
Tableau inputs on demand).
"""

import sqlite3

import pandas as pd

DB_PATH = "database/production_inventory.db"
OUT_DIR = "data/outputs"

INVENTORY_RISK_QUERY = """
SELECT
    e.sku_id,
    e.equipment_name,
    e.equipment_category,
    l.location_id,
    l.location_name,
    i.on_hand_qty,
    ROUND(r.avg_weekly_forecast_demand, 2) AS avg_weekly_forecast_demand,
    e.lead_time_days,
    r.lead_time_demand,
    r.safety_stock,
    r.reorder_point,
    r.weeks_of_cover,
    r.risk_status,
    r.reorder_qty_recommended
FROM inventory_recommendations r
JOIN dim_equipment e ON r.sku_id = e.sku_id
JOIN dim_location l ON r.location_id = l.location_id
JOIN inventory_snapshot i ON r.sku_id = i.sku_id AND r.location_id = i.location_id
ORDER BY
    CASE r.risk_status WHEN 'Critical' THEN 0 WHEN 'Reorder Now' THEN 1 ELSE 2 END,
    r.reorder_qty_recommended DESC;
"""

FORECAST_VS_ACTUAL_QUERY = """
SELECT
    e.sku_id,
    e.equipment_name,
    e.equipment_category,
    l.location_id,
    l.location_name,
    fr.week_start_date,
    fd.units_requested AS actual_demand,
    fr.naive_forecast,
    fr.ma4_forecast,
    fr.rf_forecast
FROM forecast_results fr
JOIN fact_demand_weekly fd
    ON fr.sku_id = fd.sku_id AND fr.location_id = fd.location_id AND fr.week_start_date = fd.week_start_date
JOIN dim_equipment e ON fr.sku_id = e.sku_id
JOIN dim_location l ON fr.location_id = l.location_id
ORDER BY e.sku_id, l.location_id, fr.week_start_date;
"""

KPI_SUMMARY_QUERY = """
SELECT
    e.equipment_category,
    COUNT(*)                                                              AS sku_locations,
    SUM(CASE WHEN r.risk_status = 'Critical' THEN 1 ELSE 0 END)           AS critical_count,
    SUM(CASE WHEN r.risk_status = 'Reorder Now' THEN 1 ELSE 0 END)        AS reorder_now_count,
    SUM(CASE WHEN r.risk_status = 'OK' THEN 1 ELSE 0 END)                 AS ok_count,
    SUM(r.reorder_qty_recommended)                                        AS total_units_to_reorder
FROM inventory_recommendations r
JOIN dim_equipment e ON r.sku_id = e.sku_id
GROUP BY e.equipment_category
ORDER BY critical_count DESC;
"""


def main():
    import os
    os.makedirs(OUT_DIR, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)

    exports = {
        "dashboard_inventory_risk.csv": INVENTORY_RISK_QUERY,
        "dashboard_forecast_vs_actual.csv": FORECAST_VS_ACTUAL_QUERY,
        "dashboard_kpi_summary.csv": KPI_SUMMARY_QUERY,
    }

    for filename, query in exports.items():
        df = pd.read_sql_query(query, conn)
        out_path = f"{OUT_DIR}/{filename}"
        df.to_csv(out_path, index=False)
        print(f"{filename}: {len(df)} rows, {len(df.columns)} columns -> {out_path}")

    conn.close()

    # Quick verification: row counts should match what we already know from
    # Phase 11 (300 SKU-locations) and Phase 9/10 (3000 test-period rows).
    risk = pd.read_csv(f"{OUT_DIR}/dashboard_inventory_risk.csv")
    fva = pd.read_csv(f"{OUT_DIR}/dashboard_forecast_vs_actual.csv")
    kpi = pd.read_csv(f"{OUT_DIR}/dashboard_kpi_summary.csv")

    print("\n=== Verification ===")
    print(f"Inventory risk rows: {len(risk)} (expected 300)")
    print(f"Forecast vs actual rows: {len(fva)} (expected 3000)")
    print(f"KPI summary rows: {len(kpi)} (expected 8, one per equipment category)")
    print(f"KPI summary total_units_to_reorder across all categories: {kpi['total_units_to_reorder'].sum()}")
    print(f"Inventory risk status counts (cross-check vs Phase 11):")
    print(risk["risk_status"].value_counts().to_string())


if __name__ == "__main__":
    main()
