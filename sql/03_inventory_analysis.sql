-- 03_inventory_analysis.sql
-- Preview-level inventory risk questions using only what SQL alone can compute:
-- current inventory vs. recent average demand. This is deliberately SIMPLER than
-- the formal Phase 11 method (forecast-driven lead-time demand + forecast-error-based
-- safety stock), which needs a trained model's output that doesn't exist yet. The
-- "quick_risk_flag" here is a rough SQL-only preview, not the final methodology --
-- it will be superseded by the real stockout-risk classification in Phase 11.

-- Q1: Weeks of cover per SKU-location (on-hand inventory / recent avg weekly demand),
-- the 15 lowest -- i.e. the SKU-locations that would run out soonest if demand
-- continued at its recent pace.
WITH recent_demand AS (
    SELECT sku_id, location_id, AVG(units_requested) AS recent_avg_weekly_demand
    FROM fact_demand_weekly
    WHERE week_start_date > (SELECT date(MAX(week_start_date), '-84 days') FROM fact_demand_weekly)
    GROUP BY sku_id, location_id
)
SELECT
    e.sku_id,
    e.equipment_name,
    l.location_name,
    i.on_hand_qty,
    ROUND(r.recent_avg_weekly_demand, 2)                              AS recent_avg_weekly_demand,
    ROUND(i.on_hand_qty / NULLIF(r.recent_avg_weekly_demand, 0), 2)   AS weeks_of_cover
FROM inventory_snapshot i
JOIN recent_demand r ON i.sku_id = r.sku_id AND i.location_id = r.location_id
JOIN dim_equipment e ON i.sku_id = e.sku_id
JOIN dim_location l ON i.location_id = l.location_id
ORDER BY weeks_of_cover ASC
LIMIT 15;

-- Q2: Quick risk flag -- compare on-hand inventory to a rough lead-time demand estimate
-- (recent avg weekly demand x lead time in weeks). Rows where on-hand inventory is
-- BELOW that estimate are flagged as a potential risk worth a closer look.
WITH recent_demand AS (
    SELECT sku_id, location_id, AVG(units_requested) AS recent_avg_weekly_demand
    FROM fact_demand_weekly
    WHERE week_start_date > (SELECT date(MAX(week_start_date), '-84 days') FROM fact_demand_weekly)
    GROUP BY sku_id, location_id
),
inventory_check AS (
    SELECT
        e.sku_id, e.equipment_name, e.equipment_category, e.lead_time_days,
        l.location_name,
        i.on_hand_qty,
        r.recent_avg_weekly_demand,
        r.recent_avg_weekly_demand * (e.lead_time_days / 7.0) AS lead_time_demand_estimate
    FROM inventory_snapshot i
    JOIN recent_demand r ON i.sku_id = r.sku_id AND i.location_id = r.location_id
    JOIN dim_equipment e ON i.sku_id = e.sku_id
    JOIN dim_location l ON i.location_id = l.location_id
)
SELECT
    *,
    CASE
        WHEN on_hand_qty < lead_time_demand_estimate THEN 'Potential Risk'
        ELSE 'Likely OK'
    END AS quick_risk_flag
FROM inventory_check
ORDER BY (on_hand_qty - lead_time_demand_estimate) ASC
LIMIT 15;
