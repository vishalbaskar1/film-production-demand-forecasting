-- 01_data_quality.sql
-- Business question: is the database internally consistent -- right row counts,
-- no unexpected nulls, no duplicate facts, no orphaned foreign keys?
-- This is the SQL-native counterpart to the Python validation in Phase 3/4; it exists
-- here because "can you sanity-check a database with pure SQL" is a real, testable skill.

-- Row counts per table
SELECT 'dim_equipment' AS table_name, COUNT(*) AS row_count FROM dim_equipment
UNION ALL
SELECT 'dim_location', COUNT(*) FROM dim_location
UNION ALL
SELECT 'fact_demand_weekly', COUNT(*) FROM fact_demand_weekly
UNION ALL
SELECT 'inventory_snapshot', COUNT(*) FROM inventory_snapshot;

-- Null check on key business columns in the fact table
SELECT
    SUM(CASE WHEN sku_id IS NULL THEN 1 ELSE 0 END)          AS null_sku_id,
    SUM(CASE WHEN location_id IS NULL THEN 1 ELSE 0 END)     AS null_location_id,
    SUM(CASE WHEN units_requested IS NULL THEN 1 ELSE 0 END) AS null_units_requested
FROM fact_demand_weekly;

-- Duplicate check: no (sku_id, location_id, week_start_date) combination should repeat
SELECT sku_id, location_id, week_start_date, COUNT(*) AS n
FROM fact_demand_weekly
GROUP BY sku_id, location_id, week_start_date
HAVING COUNT(*) > 1;

-- Referential integrity: fact rows whose sku_id has no match in dim_equipment
-- (a LEFT JOIN that comes back empty on the dimension side means "no match found")
SELECT f.sku_id, COUNT(*) AS orphaned_rows
FROM fact_demand_weekly f
LEFT JOIN dim_equipment e ON f.sku_id = e.sku_id
WHERE e.sku_id IS NULL
GROUP BY f.sku_id;
