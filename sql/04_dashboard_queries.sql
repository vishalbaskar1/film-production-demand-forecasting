-- 04_dashboard_queries.sql
-- Phase 12: the dashboard-ready exports. Deliberately deferred from Phase 6 --
-- these queries need the Phase 9 forecast_results and Phase 11
-- inventory_recommendations tables, which didn't exist until now.
--
-- Each query here JOINs the normalized analysis tables back to the dimension
-- tables (and, for Q2, the original fact table) to produce a single flat,
-- friendly-named table -- exactly the shape a BI tool like Tableau wants,
-- since Tableau shouldn't have to know our normalized schema or do its own
-- joins across four+ tables just to draw one chart.

-- Q1: Inventory risk detail -- one row per SKU-location, with everything an
-- operations user needs to act on a reorder decision: current stock, the
-- forecast-driven target, and the recommended order quantity.
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

-- Q2: Forecast vs. actual detail -- one row per SKU-location-week of the test
-- period, with the actual pulled back in from fact_demand_weekly (not
-- duplicated in forecast_results) so Tableau can plot forecast-vs-actual
-- trend lines, filterable by category/location/SKU.
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

-- Q3: KPI summary -- one row per equipment_category, for headline dashboard
-- tiles: how many SKU-locations are in each risk tier, and how many total
-- units would it take to clear every open reorder in that category.
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
