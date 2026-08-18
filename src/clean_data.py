"""
clean_data.py

Phase 4 data cleaning. Reads the four raw CineStock tables (data/raw/) and writes
cleaned versions to data/processed/. Every transformation here is deliberate and
documented -- nothing is silently dropped or imputed without a stated reason.

Cleaning decisions made in this script:
  1. production_type / production_size nulls (weeks with no active production) are
     encoded as the explicit category "No Active Production" rather than left as
     nulls -- see Phase 3/4 discussion for why.
  2. Calendar features (year, quarter, month, week_of_year) are derived from
     week_start_date for later seasonality analysis and model features.
  3. An is_production_active boolean is added as a convenience flag (equivalent to
     production_count > 0) since "was a production active this week" is checked
     repeatedly across later SQL/EDA/modeling phases.
  4. Defensive checks (dedup, whitespace-stripping, dtype/negative-value validation)
     are applied even though Phase 3 found the raw data already clean -- this makes
     the pipeline robust if the raw data ever changes.
"""

import pandas as pd

NO_ACTIVE_PRODUCTION = "No Active Production"


def clean_dim_equipment(df):
    df = df.copy()
    for col in ["sku_id", "equipment_name", "equipment_category", "supplier"]:
        df[col] = df[col].str.strip()
    df = df.drop_duplicates(subset=["sku_id"])
    assert (df["unit_cost"] > 0).all(), "found non-positive unit_cost"
    assert (df["lead_time_days"] > 0).all(), "found non-positive lead_time_days"
    return df


def clean_dim_location(df):
    df = df.copy()
    for col in ["location_id", "location_name"]:
        df[col] = df[col].str.strip()
    df = df.drop_duplicates(subset=["location_id"])
    return df


def clean_fact_demand_weekly(df):
    df = df.copy()
    df["week_start_date"] = pd.to_datetime(df["week_start_date"])

    for col in ["sku_id", "location_id", "season"]:
        df[col] = df[col].str.strip()

    # Decision: encode "no active production" explicitly rather than leaving nulls.
    df["production_type"] = df["production_type"].fillna(NO_ACTIVE_PRODUCTION).str.strip()
    df["production_size"] = df["production_size"].fillna(NO_ACTIVE_PRODUCTION).str.strip()

    # Convenience flag used repeatedly in later SQL/EDA/modeling phases.
    df["is_production_active"] = df["production_count"] > 0

    # Calendar features for seasonality analysis (Phase 7) and model features (Phase 9).
    df["year"] = df["week_start_date"].dt.year
    df["quarter"] = df["week_start_date"].dt.quarter
    df["month"] = df["week_start_date"].dt.month
    df["week_of_year"] = df["week_start_date"].dt.isocalendar().week.astype(int)

    df = df.drop_duplicates(subset=["sku_id", "location_id", "week_start_date"])
    assert (df["units_requested"] >= 0).all(), "found negative units_requested"
    assert (df["production_count"] >= 0).all(), "found negative production_count"
    return df


def clean_inventory_snapshot(df):
    df = df.copy()
    for col in ["sku_id", "location_id"]:
        df[col] = df[col].str.strip()
    df = df.drop_duplicates(subset=["sku_id", "location_id"])
    assert (df["on_hand_qty"] > 0).all(), "found non-positive on_hand_qty"
    return df


def main():
    equip = pd.read_csv("data/raw/dim_equipment.csv")
    loc = pd.read_csv("data/raw/dim_location.csv")
    fact = pd.read_csv("data/raw/fact_demand_weekly.csv")
    inv = pd.read_csv("data/raw/inventory_snapshot.csv")

    equip_clean = clean_dim_equipment(equip)
    loc_clean = clean_dim_location(loc)
    fact_clean = clean_fact_demand_weekly(fact)
    inv_clean = clean_inventory_snapshot(inv)

    equip_clean.to_csv("data/processed/dim_equipment.csv", index=False)
    loc_clean.to_csv("data/processed/dim_location.csv", index=False)
    fact_clean.to_csv("data/processed/fact_demand_weekly.csv", index=False)
    inv_clean.to_csv("data/processed/inventory_snapshot.csv", index=False)

    print("Cleaning complete.")
    print(f"dim_equipment:      {len(equip_clean)} rows, {equip_clean.shape[1]} cols")
    print(f"dim_location:       {len(loc_clean)} rows, {loc_clean.shape[1]} cols")
    print(f"fact_demand_weekly: {len(fact_clean)} rows, {fact_clean.shape[1]} cols "
          f"(was {fact.shape[1]} cols in raw -- added is_production_active, year, quarter, month, week_of_year)")
    print(f"inventory_snapshot: {len(inv_clean)} rows, {inv_clean.shape[1]} cols")
    print(f"\nproduction_type value counts after cleaning:")
    print(fact_clean["production_type"].value_counts())


if __name__ == "__main__":
    main()
