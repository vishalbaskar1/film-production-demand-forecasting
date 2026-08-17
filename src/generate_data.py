"""
generate_data.py

Generates the synthetic CineStock Production Rentals dataset used throughout this project.

IMPORTANT: This is entirely SYNTHETIC data, generated for portfolio/demonstration purposes.
It is not real company data and should never be represented as such. Every generative
assumption (baseline demand rates, seasonality shape, category/production-type affinities,
stocking factors, etc.) is a modeling choice made explicitly in this file, documented inline.

Reproducibility:
  - RANDOM_SEED is fixed.
  - The date range (START_DATE / END_DATE) is a hardcoded constant, NOT derived from the
    system clock. Re-running this script at any point in the future produces byte-identical
    output.

Outputs (written to data/raw/):
  - dim_equipment.csv       one row per SKU (the equipment catalog)
  - dim_location.csv        one row per rental location
  - fact_demand_weekly.csv  one row per SKU x location x week (dense panel, incl. zero weeks)
  - inventory_snapshot.csv  one row per SKU x location, current on-hand quantity
"""

import datetime
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Reproducibility constants
# ---------------------------------------------------------------------------
RANDOM_SEED = 42
rng = np.random.default_rng(RANDOM_SEED)

# Fixed, hardcoded date range (NOT computed from today's date -- see module docstring).
# END_DATE is the most recent *fully completed* Monday-start week as of the day this
# dataset was built (2026-08-17). START_DATE is exactly 130 weeks (2.5 years) earlier.
END_DATE = datetime.date(2026, 8, 10)
NUM_WEEKS = 130
START_DATE = END_DATE - datetime.timedelta(weeks=NUM_WEEKS - 1)
WEEK_DATES = [START_DATE + datetime.timedelta(weeks=i) for i in range(NUM_WEEKS)]

# ---------------------------------------------------------------------------
# Reference data: categories, locations, production types/sizes
# ---------------------------------------------------------------------------

# Each category has: a baseline weekly demand rate (per SKU, at "1 medium production active"),
# a unit cost range, and a lead time range in days. Ranges are order-of-magnitude realistic
# for film equipment rental, not sourced from any real price list.
CATEGORIES = {
    "Camera":   {"baseline_rate": 1.6, "cost_range": (5000, 80000), "lead_time_range": (10, 21)},
    "Lens":     {"baseline_rate": 1.3, "cost_range": (2000, 30000), "lead_time_range": (7, 14)},
    "Lighting": {"baseline_rate": 3.0, "cost_range": (500, 15000),  "lead_time_range": (5, 12)},
    "Audio":    {"baseline_rate": 2.2, "cost_range": (200, 5000),   "lead_time_range": (5, 10)},
    "Grip":     {"baseline_rate": 4.0, "cost_range": (100, 3000),   "lead_time_range": (2, 7)},
    "Battery":  {"baseline_rate": 5.5, "cost_range": (50, 500),     "lead_time_range": (2, 5)},
    "Monitor":  {"baseline_rate": 1.8, "cost_range": (500, 8000),   "lead_time_range": (5, 12)},
    "Drone":    {"baseline_rate": 0.9, "cost_range": (1000, 20000), "lead_time_range": (10, 21)},
}

# Representative equipment names per category (realistic-sounding, not sourced from a
# real catalog). Used to make the SKU list readable rather than "Camera SKU 1, 2, 3...".
EQUIPMENT_NAMES = {
    "Camera": ["Cinema Camera Body A", "Cinema Camera Body B", "Cinema Camera Body C",
               "Documentary Camera Body A", "Documentary Camera Body B",
               "Broadcast Camera Body A", "Compact Cinema Camera A", "Compact Cinema Camera B",
               "Large Format Camera A", "Large Format Camera B"],
    "Lens":   ["Prime Lens Set A (18-100mm)", "Prime Lens Set B (24-135mm)",
               "Zoom Lens 24-70mm", "Zoom Lens 70-200mm", "Anamorphic Lens Set A",
               "Macro Lens 100mm", "Wide Angle Lens 14mm", "Telephoto Lens 300mm",
               "Vintage Lens Set A", "Speed Booster Adapter A"],
    "Lighting": ["LED Panel Light A", "LED Panel Light B", "Fresnel Light 650W",
                 "Fresnel Light 1000W", "HMI Light 1200W", "HMI Light 4000W",
                 "Softbox Kit A", "Ring Light A", "Practical Light Kit A",
                 "Light Stand Kit A", "Dimmer/Board Controller A"],
    "Audio":  ["Shotgun Microphone A", "Lavalier Mic Kit A", "Boom Pole Kit A",
               "Field Audio Recorder A", "Wireless Mic System A", "Wireless Mic System B",
               "Audio Mixer A", "Studio Headphones Kit A", "Boom Pole Kit B"],
    "Grip":   ["C-Stand Kit A", "Sandbag Set A", "Dolly Track Kit A", "Camera Dolly A",
               "Grip Arm Kit A", "Apple Box Set A", "Flag/Scrim Kit A",
               "Gimbal Stabilizer A", "Tripod Head A", "Slider Rig A"],
    "Battery": ["V-Mount Battery A", "V-Mount Battery B", "Gold-Mount Battery A",
                "Battery Charger Station A", "Portable Power Station A",
                "V-Mount Battery C", "Gold-Mount Battery B", "Battery Distribution Block A"],
    "Monitor": ["On-Camera Monitor 7in", "On-Camera Monitor 5in", "Director Monitor 17in",
                "Video Village Monitor Kit A", "Waveform Monitor A",
                "Field Monitor 10in", "Teleprompter Monitor A", "Client Viewing Monitor A"],
    "Drone":  ["Cinema Drone A", "Cinema Drone B", "Compact Drone A", "FPV Drone Kit A",
               "Cinema Drone C", "FPV Drone Kit B", "Drone Battery Kit A",
               "Drone Controller Kit A", "Compact Drone B"],
}

SUPPLIERS = ["Apex Grip & Lighting Supply", "Meridian Camera Systems", "Pacific Audio Works",
             "Summit Equipment Partners", "Coastal Cine Supply", "Northline Rentals Wholesale"]

LOCATIONS = {
    # activity_level sets the relative baseline production activity for that location
    "Los Angeles": {"activity_level": 1.35},
    "Atlanta":     {"activity_level": 1.15},
    "New York":    {"activity_level": 1.00},
    "New Orleans": {"activity_level": 0.75},
}

PRODUCTION_TYPES = ["Feature Film", "Television", "Commercial", "Documentary", "Music Video"]
PRODUCTION_TYPE_PROBS = [0.15, 0.35, 0.30, 0.12, 0.08]

PRODUCTION_SIZES = ["Small", "Medium", "Large"]
PRODUCTION_SIZE_PROBS = [0.45, 0.35, 0.20]
PRODUCTION_SIZE_MULTIPLIER = {"Small": 0.5, "Medium": 1.0, "Large": 1.8}

# Category x production-type demand affinity multipliers. 1.0 = baseline (no effect).
# This is a documented MODELING ASSUMPTION, not a real industry statistic: it encodes
# "which categories a given production type leans on relatively more/less" so that
# production-type effects show up in the data for Phase 6/7 to discover.
AFFINITY = {
    #                Feature  TV     Commercial  Documentary  Music Video
    "Camera":   dict(zip(PRODUCTION_TYPES, [1.1, 1.1, 1.0, 0.8, 1.0])),
    "Lens":     dict(zip(PRODUCTION_TYPES, [1.2, 1.1, 1.0, 0.7, 1.1])),
    "Lighting": dict(zip(PRODUCTION_TYPES, [1.0, 1.0, 1.4, 0.6, 1.2])),
    "Audio":    dict(zip(PRODUCTION_TYPES, [1.0, 1.0, 0.8, 1.5, 0.7])),
    "Grip":     dict(zip(PRODUCTION_TYPES, [1.1, 1.0, 1.1, 0.7, 1.3])),
    "Battery":  dict(zip(PRODUCTION_TYPES, [1.0, 1.0, 0.9, 1.3, 0.9])),
    "Monitor":  dict(zip(PRODUCTION_TYPES, [1.1, 1.1, 1.0, 0.8, 0.9])),
    "Drone":    dict(zip(PRODUCTION_TYPES, [1.0, 0.8, 1.2, 0.9, 1.4])),
}

SEASON_BY_MONTH = {
    12: "Winter", 1: "Winter", 2: "Winter",
    3: "Spring", 4: "Spring", 5: "Spring",
    6: "Summer", 7: "Summer", 8: "Summer",
    9: "Fall", 10: "Fall", 11: "Fall",
}


# ---------------------------------------------------------------------------
# 1. Equipment catalog (dim_equipment)
# ---------------------------------------------------------------------------
def generate_equipment_catalog():
    rows = []
    sku_num = 1
    for category, names in EQUIPMENT_NAMES.items():
        cost_lo, cost_hi = CATEGORIES[category]["cost_range"]
        lead_lo, lead_hi = CATEGORIES[category]["lead_time_range"]
        for name in names:
            sku_id = f"SKU-{sku_num:03d}"
            unit_cost = round(float(rng.uniform(cost_lo, cost_hi)), 2)
            lead_time_days = int(rng.integers(lead_lo, lead_hi + 1))
            supplier = rng.choice(SUPPLIERS)
            # popularity_factor: log-normal so most SKUs cluster near 1.0 but a few are
            # "hot" (high demand) and a few are niche (rarely rented) -- a realistic
            # long-tail pattern, not a uniform spread.
            popularity_factor = float(rng.lognormal(mean=0.0, sigma=0.5))
            rows.append({
                "sku_id": sku_id,
                "equipment_name": name,
                "equipment_category": category,
                "unit_cost": unit_cost,
                "supplier": supplier,
                "lead_time_days": lead_time_days,
                "popularity_factor": round(popularity_factor, 3),
            })
            sku_num += 1
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 2. Locations (dim_location)
# ---------------------------------------------------------------------------
def generate_locations():
    rows = []
    for loc_num, (name, props) in enumerate(LOCATIONS.items(), start=1):
        rows.append({
            "location_id": f"LOC-{loc_num:02d}",
            "location_name": name,
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 3. Weekly production-activity context, per location
#    (production_count, dominant production_type/size for each location-week)
# ---------------------------------------------------------------------------
def generate_production_context(locations_df):
    records = []
    for _, loc_row in locations_df.iterrows():
        location_id = loc_row["location_id"]
        location_name = loc_row["location_name"]
        activity_level = LOCATIONS[location_name]["activity_level"]

        state = activity_level  # AR(1) starting point
        for week_idx, week_start in enumerate(WEEK_DATES):
            # Slow upward trend across the full window (~15% higher by the end than the start),
            # reflecting modest overall growth in production activity.
            trend_factor = 1.0 + 0.15 * (week_idx / (NUM_WEEKS - 1))

            # Seasonal factor: spring/summer busier (pilot season, summer productions),
            # winter holidays quieter. Modeled as a smooth sinusoid peaking in June.
            day_of_year = week_start.timetuple().tm_yday
            seasonal_factor = 1.0 + 0.25 * np.sin(2 * np.pi * (day_of_year - 80) / 365)

            raw_target = activity_level * trend_factor * seasonal_factor

            # AR(1) smoothing: this week's activity state is mostly last week's state,
            # blended with a fresh pull toward this week's raw target. This produces
            # realistic multi-week "runs" of busy/quiet periods instead of iid noise.
            state = 0.7 * state + 0.3 * raw_target + rng.normal(0, 0.08)
            state = max(state, 0.05)

            production_count = int(rng.poisson(lam=state * 2.2))

            if production_count > 0:
                production_type = str(rng.choice(PRODUCTION_TYPES, p=PRODUCTION_TYPE_PROBS))
                production_size = str(rng.choice(PRODUCTION_SIZES, p=PRODUCTION_SIZE_PROBS))
            else:
                production_type = None
                production_size = None

            records.append({
                "location_id": location_id,
                "week_start_date": week_start,
                "production_count": production_count,
                "production_type": production_type,
                "production_size": production_size,
                "season": SEASON_BY_MONTH[week_start.month],
                "_activity_state": state,  # kept for demand calc below, dropped before export
            })
    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# 4. Weekly demand panel (fact_demand_weekly) -- dense: every SKU x location x week
# ---------------------------------------------------------------------------
def generate_demand(equipment_df, context_df):
    # Small residual baseline so SKUs aren't hard-zero in weeks with no active production
    # (routine maintenance checks, prep for an upcoming shoot, etc.)
    RESIDUAL_BASELINE_FACTOR = 0.05
    SPIKE_PROBABILITY = 0.015
    SPIKE_MULTIPLIER_RANGE = (3.0, 5.0)

    context_df = context_df.set_index(["location_id", "week_start_date"])

    rows = []
    for _, sku_row in equipment_df.iterrows():
        category = sku_row["equipment_category"]
        base_rate = CATEGORIES[category]["baseline_rate"]
        popularity = sku_row["popularity_factor"]
        affinity_by_type = AFFINITY[category]

        for (location_id, week_start), ctx in context_df.iterrows():
            production_count = ctx["production_count"]
            production_type = ctx["production_type"]
            production_size = ctx["production_size"]

            if production_count > 0:
                size_mult = PRODUCTION_SIZE_MULTIPLIER[production_size]
                affinity_mult = affinity_by_type[production_type]
                activity_mult = 0.6 + 0.4 * production_count  # more concurrent productions -> more demand
                expected_demand = base_rate * popularity * size_mult * affinity_mult * activity_mult
            else:
                expected_demand = base_rate * popularity * RESIDUAL_BASELINE_FACTOR

            units = rng.poisson(lam=max(expected_demand, 0.001))

            # Occasional demand spikes (bulk pulls for a big production, award-season crunch, etc.)
            if rng.random() < SPIKE_PROBABILITY:
                units = int(round(units * rng.uniform(*SPIKE_MULTIPLIER_RANGE))) + int(rng.integers(1, 5))

            rows.append({
                "sku_id": sku_row["sku_id"],
                "location_id": location_id,
                "week_start_date": week_start,
                "production_type": production_type,
                "production_size": production_size,
                "production_count": production_count,
                "season": ctx["season"],
                "units_requested": int(units),
            })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 5. Inventory snapshot (inventory_snapshot) -- deliberately uneven stocking
# ---------------------------------------------------------------------------
def generate_inventory_snapshot(fact_df):
    recent_cutoff = END_DATE - datetime.timedelta(weeks=12)
    recent = fact_df[fact_df["week_start_date"] > recent_cutoff]
    recent_avg = (
        recent.groupby(["sku_id", "location_id"])["units_requested"]
        .mean()
        .reset_index()
        .rename(columns={"units_requested": "recent_avg_weekly_demand"})
    )

    # Stocking factor: how many weeks' worth of recent average demand is currently on hand.
    # Wide, deliberately uneven range (0.4x - 2.5x) so some SKU-locations are genuinely
    # under-stocked and some are over-stocked -- this variety is what makes the Phase 11
    # stockout-risk analysis meaningful rather than uniformly "fine."
    recent_avg["stocking_factor"] = rng.uniform(0.4, 2.5, size=len(recent_avg))
    recent_avg["on_hand_qty"] = np.maximum(
        1, np.round(recent_avg["recent_avg_weekly_demand"] * 4 * recent_avg["stocking_factor"])
    ).astype(int)

    return recent_avg[["sku_id", "location_id", "on_hand_qty"]]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print(f"Generating CineStock synthetic dataset (seed={RANDOM_SEED})")
    print(f"Date range: {START_DATE} to {END_DATE} ({NUM_WEEKS} weeks)")

    equipment_df = generate_equipment_catalog()
    locations_df = generate_locations()
    context_df = generate_production_context(locations_df)
    fact_df = generate_demand(equipment_df, context_df)
    inventory_df = generate_inventory_snapshot(fact_df)

    equipment_df.to_csv("data/raw/dim_equipment.csv", index=False)
    locations_df.to_csv("data/raw/dim_location.csv", index=False)
    fact_df.to_csv("data/raw/fact_demand_weekly.csv", index=False)
    inventory_df.to_csv("data/raw/inventory_snapshot.csv", index=False)

    print(f"\ndim_equipment.csv:      {len(equipment_df)} rows")
    print(f"dim_location.csv:       {len(locations_df)} rows")
    print(f"fact_demand_weekly.csv: {len(fact_df)} rows")
    print(f"inventory_snapshot.csv: {len(inventory_df)} rows")


if __name__ == "__main__":
    main()
