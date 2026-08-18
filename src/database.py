"""
database.py

Phase 5: builds the SQLite database (database/production_inventory.db) from the
Phase 4 cleaned tables (data/processed/) and loads the data into it.

Design: a star schema -- two dimension tables (dim_equipment, dim_location) and two
fact tables (fact_demand_weekly, inventory_snapshot), with explicit primary and
foreign keys. See Phase 5 discussion for why this schema (not a more normalized one)
was chosen.

Rerunnable: drops and recreates all tables each time, so this script always produces
the database fresh from the current processed CSVs rather than accumulating state.
"""

import sqlite3
import pandas as pd

DB_PATH = "database/production_inventory.db"

SCHEMA = """
DROP TABLE IF EXISTS fact_demand_weekly;
DROP TABLE IF EXISTS inventory_snapshot;
DROP TABLE IF EXISTS dim_equipment;
DROP TABLE IF EXISTS dim_location;

CREATE TABLE dim_equipment (
    sku_id              TEXT PRIMARY KEY,
    equipment_name      TEXT NOT NULL,
    equipment_category  TEXT NOT NULL,
    unit_cost           REAL NOT NULL,
    supplier            TEXT NOT NULL,
    lead_time_days      INTEGER NOT NULL,
    popularity_factor   REAL NOT NULL
);

CREATE TABLE dim_location (
    location_id     TEXT PRIMARY KEY,
    location_name   TEXT NOT NULL
);

CREATE TABLE fact_demand_weekly (
    sku_id                  TEXT NOT NULL,
    location_id             TEXT NOT NULL,
    week_start_date         TEXT NOT NULL,
    production_type         TEXT NOT NULL,
    production_size         TEXT NOT NULL,
    production_count        INTEGER NOT NULL,
    season                  TEXT NOT NULL,
    units_requested         INTEGER NOT NULL,
    is_production_active    INTEGER NOT NULL,
    year                    INTEGER NOT NULL,
    quarter                 INTEGER NOT NULL,
    month                   INTEGER NOT NULL,
    week_of_year            INTEGER NOT NULL,
    PRIMARY KEY (sku_id, location_id, week_start_date),
    FOREIGN KEY (sku_id) REFERENCES dim_equipment(sku_id),
    FOREIGN KEY (location_id) REFERENCES dim_location(location_id)
);

CREATE TABLE inventory_snapshot (
    sku_id          TEXT NOT NULL,
    location_id     TEXT NOT NULL,
    on_hand_qty     INTEGER NOT NULL,
    PRIMARY KEY (sku_id, location_id),
    FOREIGN KEY (sku_id) REFERENCES dim_equipment(sku_id),
    FOREIGN KEY (location_id) REFERENCES dim_location(location_id)
);
"""


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")

    # Create schema
    conn.executescript(SCHEMA)

    # Load processed data. Dimension tables first (fact tables reference them via FK).
    equip = pd.read_csv("data/processed/dim_equipment.csv")
    loc = pd.read_csv("data/processed/dim_location.csv")
    fact = pd.read_csv("data/processed/fact_demand_weekly.csv")
    inv = pd.read_csv("data/processed/inventory_snapshot.csv")

    equip.to_sql("dim_equipment", conn, if_exists="append", index=False)
    loc.to_sql("dim_location", conn, if_exists="append", index=False)
    fact.to_sql("fact_demand_weekly", conn, if_exists="append", index=False)
    inv.to_sql("inventory_snapshot", conn, if_exists="append", index=False)
    conn.commit()

    # Foreign key integrity check -- PRAGMA foreign_key_check returns rows only
    # if a violation exists, so an empty result confirms every FK resolves.
    violations = conn.execute("PRAGMA foreign_key_check;").fetchall()

    # Row count verification
    counts = {}
    for table in ["dim_equipment", "dim_location", "fact_demand_weekly", "inventory_snapshot"]:
        counts[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    print("Database built at:", DB_PATH)
    for table, count in counts.items():
        print(f"  {table}: {count} rows")
    print(f"\nForeign key violations: {len(violations)} (expected 0)")

    # Quick sanity join, proving the schema actually supports the analysis we need
    sample = conn.execute("""
        SELECT e.equipment_category, l.location_name, SUM(f.units_requested) AS total_demand
        FROM fact_demand_weekly f
        JOIN dim_equipment e ON f.sku_id = e.sku_id
        JOIN dim_location l ON f.location_id = l.location_id
        GROUP BY e.equipment_category, l.location_name
        ORDER BY total_demand DESC
        LIMIT 5
    """).fetchall()
    print("\nSanity check -- top 5 category/location combos by total demand:")
    for row in sample:
        print(" ", row)

    conn.close()


if __name__ == "__main__":
    main()
