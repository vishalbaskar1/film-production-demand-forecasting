"""
validate_data.py

Phase 3 data validation. Runs a systematic set of checks over the four raw CineStock
tables (data/raw/) BEFORE any cleaning happens, and prints a data-quality report.

This script only inspects and reports -- it never modifies or drops rows. Any issue
found here is a decision for Phase 4 (cleaning) to make deliberately, not something
this script fixes silently.
"""

import pandas as pd

pd.set_option("display.width", 120)

EXPECTED_CATEGORIES = {"Camera", "Lens", "Lighting", "Audio", "Grip", "Battery", "Monitor", "Drone"}
EXPECTED_PRODUCTION_TYPES = {"Feature Film", "Television", "Commercial", "Documentary", "Music Video"}
EXPECTED_PRODUCTION_SIZES = {"Small", "Medium", "Large"}
EXPECTED_SEASONS = {"Winter", "Spring", "Summer", "Fall"}
EXPECTED_SKUS = 75
EXPECTED_LOCATIONS = 4
EXPECTED_WEEKS = 130


def section(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def load_tables():
    equip = pd.read_csv("data/raw/dim_equipment.csv")
    loc = pd.read_csv("data/raw/dim_location.csv")
    fact = pd.read_csv("data/raw/fact_demand_weekly.csv", parse_dates=["week_start_date"])
    inv = pd.read_csv("data/raw/inventory_snapshot.csv")
    return equip, loc, fact, inv


def check_shape_and_types(name, df):
    print(f"\n--- {name} ---")
    print("shape:", df.shape)
    print(df.dtypes)


def check_missing_values(name, df):
    print(f"\n--- {name}: missing values ---")
    missing = df.isna().sum()
    missing = missing[missing > 0]
    if missing.empty:
        print("none")
    else:
        print(missing)


def check_duplicates(name, df, subset=None):
    dupe_count = df.duplicated(subset=subset).sum()
    label = f"on {subset}" if subset else "(full row)"
    print(f"{name}: duplicate rows {label}: {dupe_count}")


def main():
    equip, loc, fact, inv = load_tables()

    section("1. SHAPE, COLUMNS, DATA TYPES")
    check_shape_and_types("dim_equipment", equip)
    check_shape_and_types("dim_location", loc)
    check_shape_and_types("fact_demand_weekly", fact)
    check_shape_and_types("inventory_snapshot", inv)

    section("2. MISSING VALUES")
    check_missing_values("dim_equipment", equip)
    check_missing_values("dim_location", loc)
    check_missing_values("fact_demand_weekly", fact)
    check_missing_values("inventory_snapshot", inv)
    # Cross-check: production_type/size should be null ONLY when production_count == 0
    null_type_rows = fact[fact["production_type"].isna()]
    inconsistent = null_type_rows[null_type_rows["production_count"] != 0]
    print(f"\nfact_demand_weekly: rows with null production_type but production_count != 0: "
          f"{len(inconsistent)}  (should be 0 -- confirms nulls are explained by 'no active production')")

    section("3. DUPLICATE ROWS")
    check_duplicates("dim_equipment", equip, subset=["sku_id"])
    check_duplicates("dim_location", loc, subset=["location_id"])
    check_duplicates("fact_demand_weekly", fact, subset=["sku_id", "location_id", "week_start_date"])
    check_duplicates("inventory_snapshot", inv, subset=["sku_id", "location_id"])

    section("4. PANEL COMPLETENESS (dense panel check)")
    expected_rows = EXPECTED_SKUS * EXPECTED_LOCATIONS * EXPECTED_WEEKS
    print(f"expected rows (SKUs x locations x weeks): {expected_rows}")
    print(f"actual rows in fact_demand_weekly:         {len(fact)}")
    print(f"match: {len(fact) == expected_rows}")

    section("5. DATE RANGE")
    print("min week_start_date:", fact["week_start_date"].min())
    print("max week_start_date:", fact["week_start_date"].max())
    print("unique weeks:", fact["week_start_date"].nunique(), f"(expected {EXPECTED_WEEKS})")
    # all weeks should be Mondays
    non_mondays = fact.loc[fact["week_start_date"].dt.weekday != 0, "week_start_date"].nunique()
    print("weeks that are NOT Mondays:", non_mondays)

    section("6. CARDINALITY CHECKS")
    print(f"unique SKUs in dim_equipment: {equip['sku_id'].nunique()} (expected {EXPECTED_SKUS})")
    print(f"unique locations in dim_location: {loc['location_id'].nunique()} (expected {EXPECTED_LOCATIONS})")
    print(f"unique categories in dim_equipment: {equip['equipment_category'].nunique()} (expected 8)")
    print(f"unique SKUs referenced in fact table: {fact['sku_id'].nunique()}")
    print(f"unique locations referenced in fact table: {fact['location_id'].nunique()}")

    section("7. REFERENTIAL INTEGRITY")
    orphan_skus = set(fact["sku_id"]) - set(equip["sku_id"])
    orphan_locs = set(fact["location_id"]) - set(loc["location_id"])
    print(f"SKUs in fact_demand_weekly not present in dim_equipment: {len(orphan_skus)} {orphan_skus if orphan_skus else ''}")
    print(f"Locations in fact_demand_weekly not present in dim_location: {len(orphan_locs)} {orphan_locs if orphan_locs else ''}")

    inv_pairs = set(zip(inv["sku_id"], inv["location_id"]))
    fact_pairs = set(zip(fact["sku_id"], fact["location_id"]))
    print(f"inventory_snapshot SKU-location pairs not present in fact table: {len(inv_pairs - fact_pairs)}")
    print(f"fact table SKU-location pairs missing from inventory_snapshot: {len(fact_pairs - inv_pairs)}")

    section("8. CATEGORY / LABEL SANITY")
    actual_categories = set(equip["equipment_category"].unique())
    print("equipment_category values:", actual_categories)
    print("unexpected category values:", actual_categories - EXPECTED_CATEGORIES)

    actual_types = set(fact["production_type"].dropna().unique())
    print("\nproduction_type values:", actual_types)
    print("unexpected production_type values:", actual_types - EXPECTED_PRODUCTION_TYPES)

    actual_sizes = set(fact["production_size"].dropna().unique())
    print("\nproduction_size values:", actual_sizes)
    print("unexpected production_size values:", actual_sizes - EXPECTED_PRODUCTION_SIZES)

    actual_seasons = set(fact["season"].unique())
    print("\nseason values:", actual_seasons)
    print("unexpected season values:", actual_seasons - EXPECTED_SEASONS)

    section("9. INVALID / IMPOSSIBLE NUMERIC VALUES")
    print("dim_equipment.unit_cost <= 0:", (equip["unit_cost"] <= 0).sum())
    print("dim_equipment.lead_time_days <= 0:", (equip["lead_time_days"] <= 0).sum())
    print("fact_demand_weekly.units_requested < 0:", (fact["units_requested"] < 0).sum())
    print("fact_demand_weekly.production_count < 0:", (fact["production_count"] < 0).sum())
    print("inventory_snapshot.on_hand_qty <= 0:", (inv["on_hand_qty"] <= 0).sum())
    print("inventory_snapshot.on_hand_qty missing SKU-location entirely:",
          EXPECTED_SKUS * EXPECTED_LOCATIONS - len(inv))

    section("10. DESCRIPTIVE STATISTICS")
    print("\n-- dim_equipment numeric columns --")
    print(equip[["unit_cost", "lead_time_days", "popularity_factor"]].describe().round(2))
    print("\n-- fact_demand_weekly.units_requested --")
    print(fact["units_requested"].describe().round(2))
    print("\n-- inventory_snapshot.on_hand_qty --")
    print(inv["on_hand_qty"].describe().round(2))

    section("11. OUTLIER SCAN (units_requested, IQR method)")
    q1, q3 = fact["units_requested"].quantile([0.25, 0.75])
    iqr = q3 - q1
    upper_fence = q3 + 3 * iqr  # 3x IQR = "extreme" outlier convention, not the usual 1.5x,
    # since this is count/spike data where some skew is expected by design
    outliers = fact[fact["units_requested"] > upper_fence]
    print(f"Q1={q1}, Q3={q3}, IQR={iqr}, extreme-outlier fence (Q3 + 3*IQR)={upper_fence}")
    print(f"rows above fence: {len(outliers)} ({len(outliers)/len(fact)*100:.2f}% of all rows)")
    print("\ntop 5 by units_requested:")
    print(outliers.merge(equip[["sku_id", "equipment_category", "popularity_factor"]], on="sku_id")
          .sort_values("units_requested", ascending=False)
          .head(5)[["sku_id", "location_id", "week_start_date", "equipment_category",
                     "popularity_factor", "production_size", "units_requested"]])


if __name__ == "__main__":
    main()
