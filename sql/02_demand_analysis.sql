-- 02_demand_analysis.sql
-- Core demand-planning business questions: which SKUs/categories/locations drive
-- demand, which SKUs are the most unpredictable, and how do production
-- characteristics affect demand.

-- Q1: Total and average weekly demand by SKU (top 10 by total demand)
SELECT
    e.sku_id,
    e.equipment_name,
    e.equipment_category,
    SUM(f.units_requested)          AS total_demand,
    ROUND(AVG(f.units_requested), 2) AS avg_weekly_demand,
    MAX(f.units_requested)          AS max_weekly_demand
FROM fact_demand_weekly f
JOIN dim_equipment e ON f.sku_id = e.sku_id
GROUP BY e.sku_id, e.equipment_name, e.equipment_category
ORDER BY total_demand DESC
LIMIT 10;

-- Q2: Equipment category demand ranking (RANK window function)
SELECT
    equipment_category,
    total_demand,
    RANK() OVER (ORDER BY total_demand DESC) AS demand_rank
FROM (
    SELECT e.equipment_category, SUM(f.units_requested) AS total_demand
    FROM fact_demand_weekly f
    JOIN dim_equipment e ON f.sku_id = e.sku_id
    GROUP BY e.equipment_category
);

-- Q3: Demand comparison across rental locations
SELECT
    l.location_name,
    SUM(f.units_requested)              AS total_demand,
    ROUND(AVG(f.units_requested), 2)    AS avg_weekly_demand,
    COUNT(DISTINCT f.sku_id)            AS distinct_skus_rented
FROM fact_demand_weekly f
JOIN dim_location l ON f.location_id = l.location_id
GROUP BY l.location_name
ORDER BY total_demand DESC;

-- Q4: Demand volatility -- the 10 SKUs with the highest coefficient of variation
-- (stddev / mean). SQLite has no built-in STDDEV, so variance is computed from its
-- definition: Var(X) = E[X^2] - (E[X])^2.
WITH sku_stats AS (
    SELECT
        sku_id,
        AVG(units_requested)                                             AS mean_demand,
        AVG(units_requested * units_requested) - AVG(units_requested) * AVG(units_requested) AS variance
    FROM fact_demand_weekly
    GROUP BY sku_id
)
SELECT
    e.sku_id,
    e.equipment_name,
    ROUND(s.mean_demand, 2)                                     AS mean_weekly_demand,
    ROUND(SQRT(s.variance), 2)                                  AS stddev_weekly_demand,
    ROUND(SQRT(s.variance) / NULLIF(s.mean_demand, 0), 2)       AS coefficient_of_variation
FROM sku_stats s
JOIN dim_equipment e ON s.sku_id = e.sku_id
ORDER BY coefficient_of_variation DESC
LIMIT 10;

-- Q5: Production-type effects on demand
SELECT
    production_type,
    COUNT(*)                          AS weeks_observed,
    SUM(units_requested)              AS total_demand,
    ROUND(AVG(units_requested), 2)    AS avg_weekly_demand
FROM fact_demand_weekly
GROUP BY production_type
ORDER BY avg_weekly_demand DESC;

-- Q6: Production-size effects, with a CASE-based plain-language interpretation column
SELECT
    production_size,
    ROUND(AVG(units_requested), 2) AS avg_weekly_demand,
    CASE
        WHEN production_size = 'Large'  THEN 'High equipment need'
        WHEN production_size = 'Medium' THEN 'Moderate equipment need'
        WHEN production_size = 'Small'  THEN 'Low equipment need'
        ELSE 'No active production'
    END AS interpretation
FROM fact_demand_weekly
GROUP BY production_size
ORDER BY avg_weekly_demand DESC;

-- Q7: Rolling 4-week average demand trend for the single highest-volume SKU
-- (demonstrates a window function computing a moving average without collapsing rows)
WITH top_sku AS (
    SELECT sku_id FROM fact_demand_weekly
    GROUP BY sku_id ORDER BY SUM(units_requested) DESC LIMIT 1
),
weekly_totals AS (
    SELECT week_start_date, SUM(units_requested) AS weekly_demand
    FROM fact_demand_weekly
    WHERE sku_id = (SELECT sku_id FROM top_sku)
    GROUP BY week_start_date
)
SELECT
    week_start_date,
    weekly_demand,
    ROUND(AVG(weekly_demand) OVER (
        ORDER BY week_start_date
        ROWS BETWEEN 3 PRECEDING AND CURRENT ROW
    ), 2) AS rolling_4wk_avg
FROM weekly_totals
ORDER BY week_start_date
LIMIT 15;
