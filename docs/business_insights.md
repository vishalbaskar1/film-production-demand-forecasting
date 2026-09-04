# Business Insights — CineStock Inventory Risk & Reorder Analysis

> **Note on the data:** CineStock Production Rentals is a fictional company. All demand, inventory, and equipment data in this project is synthetically generated for portfolio/demonstration purposes. Nothing below describes a real company's actual operations.

## The Business Question

Which equipment SKUs are at risk of insufficient inventory during upcoming production periods, and what inventory or reorder actions should operations teams take?

This document summarizes what the analysis actually found, in business terms. Full methodology, code, and SQL live in the rest of the repo; this is the "so what" layer written for a non-technical stakeholder.

## Finding 1: A demand-history-aware forecasting model meaningfully outperforms a simple baseline — but not evenly across equipment types

A 4-week moving average baseline (a reasonable, low-effort forecast any operations team could compute by hand) produced a WAPE (weighted absolute percentage error) of 78.9% on the 10-week test period. A Random Forest model — trained on lagged demand, rolling demand volatility, calendar features, and production-context features — reduced that to 47.8% WAPE, a 39.4% relative improvement.

That said, the model's accuracy is not uniform across equipment categories, and the gap matters for what comes next:

| Equipment Category | WAPE | MAE |
|---|---|---|
| Drone | 68.3% | 1.28 |
| Audio | 58.3% | 2.49 |
| Camera | 56.6% | 2.17 |
| Lens | 56.2% | 1.71 |
| Battery | 47.0% | 5.04 |
| Monitor | 44.6% | 2.15 |
| Lighting | 41.4% | 2.99 |
| Grip | 40.0% | 3.19 |

Drone has the *worst* WAPE despite having the *lowest* MAE — a reminder that these two metrics answer different questions. MAE says "the average forecast is only off by about 1 unit," which sounds great. WAPE says "relative to how much drone equipment actually gets requested, that 1-unit error is large" — because average weekly drone demand is itself small. For low-volume equipment, small absolute errors translate into large percentage errors, which is exactly the kind of equipment where a business can't afford to be caught flat-footed by a stockout.

The model also shows a small systematic bias: across the whole test period, the average residual (actual minus forecast) is +0.385, meaning it tends to slightly under-forecast rather than over-forecast, and that under-forecasting is concentrated in occasional demand spikes rather than typical weeks (visible in the actual-vs-predicted scatter plot in `images/evaluation/`). In practice, this means the forecast is more trustworthy for routine weeks than for predicting an unusual surge — a real limitation, stated honestly rather than smoothed over.

## Finding 2: Inventory risk is concentrated in a small number of equipment categories, not spread evenly across the catalog

Across all 300 SKU-location combinations, the analysis classifies 231 as OK, 38 as Reorder Now, and 31 as Critical (already below the calculated safety stock buffer). That's 69 SKU-locations — 23% of the catalog — needing some level of attention right now.

That risk is not evenly distributed:

| Category | % of SKU-locations at risk (Critical + Reorder Now) | Total units recommended to reorder |
|---|---|---|
| Drone | 63.9% | 115 |
| Camera | 42.5% | 97 |
| Audio | 22.2% | 20 |
| Lens | 20.0% | 21 |
| Monitor | 15.6% | 19 |
| Lighting | 11.4% | 25 |
| Grip | 5.0% | 3 |
| Battery | 3.1% | 2 |

Two categories — Drone and Camera — account for 212 of the 302 total units recommended for reorder (70%), despite being only 76 of the 300 SKU-location combinations (25%). This is not a coincidence: both categories also had the two worst forecast WAPE scores. Worse forecast accuracy directly widens the safety-stock formula's error term, which pushes the reorder point higher, which flags more SKU-locations as at-risk. The forecasting quality and the inventory risk findings are telling the same story from two different angles — that's a genuine cross-validation of the pipeline, not two unrelated results that happen to point the same direction.

Camera and Drone deserve attention for different reasons, though. Drone has the highest *percentage* of its catalog at risk (a category-wide problem), while Camera contributes more *total units* to reorder in absolute terms and dominates the highest-priority individual items (5 of the top 10 highest-priority reorders are Camera equipment). A business responding to this would likely treat Drone as a category-level forecasting/stocking policy problem, and Camera as needing both category-level attention and close tracking of a handful of specific high-value SKUs.

## Finding 3: The highest-priority reorder actions

The top individual reorder recommendations, ranked by urgency (Critical status) and then by quantity needed:

| Equipment | Location | On Hand | Reorder Point | Recommended Reorder Qty |
|---|---|---|---|---|
| Cinema Camera Body A | LOC-04 | 6 | 20.0 | 14 |
| FPV Drone Kit A | LOC-02 | 2 | 10.7 | 9 |
| Documentary Camera Body B | LOC-01 | 8 | 16.0 | 8 |
| Documentary Camera Body B | LOC-03 | 7 | 15.4 | 8 |
| Large Format Camera A | LOC-03 | 11 | 18.5 | 8 |
| Broadcast Camera Body A | LOC-04 | 5 | 11.6 | 7 |
| Compact Cinema Camera A | LOC-01 | 7 | 13.7 | 7 |
| Fresnel Light 1000W | LOC-03 | 8 | 15.4 | 7 |
| Fresnel Light 1000W | LOC-04 | 10 | 17.0 | 7 |
| On-Camera Monitor 5in | LOC-04 | 6 | 12.9 | 7 |

Across all 69 at-risk SKU-locations, the model recommends reordering 302 total units. This full list, filterable by category and location, is what the Tableau dashboard's "Reorder Priority" view surfaces for an operations team.

## Limitations and Assumptions (stated honestly)

- **Synthetic data.** Every number above comes from a generated dataset, not a real company's transaction history. The relative patterns (Drone/Camera being harder to forecast and higher-risk) are internally consistent findings from this dataset, not claims about the real film-equipment-rental industry.
- **Category-pooled forecast error, not per-SKU.** Safety stock uses each category's pooled forecast-error standard deviation rather than an individual SKU's, because 10 test weeks per SKU-location is too few observations to estimate a stable standard deviation on its own. This is a reasonable statistical tradeoff, but it means two SKUs in the same category are treated as equally volatile even if their real behavior differs.
- **Reorder quantity is a simple gap-fill, not full EOQ.** The recommended reorder quantity brings on-hand stock back up to the reorder point; it is not an economic-order-quantity calculation, since this dataset has no real ordering-cost or holding-cost data to support that level of optimization.
- **The model under-predicts spikes.** As noted in Finding 1, the Random Forest forecast is more reliable for typical weeks than for unusual demand surges. A team relying on this forecast should treat "Critical" and "Reorder Now" flags as a floor, not a ceiling, on urgency during unusually busy production periods.
- **Point-in-time snapshot.** This analysis reflects one fixed point in time (inventory snapshot and forecast test period as of the dataset's generation). A production version would need to re-run forecasting and risk classification on a rolling basis as new demand data arrives.

## What a Real Deployment Would Need Next

- More historical data per SKU-location to support per-SKU (rather than category-pooled) error estimation.
- Actual ordering and holding cost data to move from a simple reorder-point model toward true EOQ optimization.
- A recurring (e.g., weekly) re-run of the forecasting and inventory pipeline, rather than a single static snapshot.
- Investigation into *why* Drone and Camera are harder to forecast — is it genuinely higher demand volatility, or missing features (e.g., specific production types that heavily drive drone/camera demand) that a richer feature set could capture?
