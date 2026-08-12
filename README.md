# Film Production Demand Forecasting & Inventory Dashboard

**Status: in development.** This README is a placeholder created during initial environment setup and will be
expanded into a full project write-up once the analysis is complete (see Phase 15 of the project plan).

## What this project is

An end-to-end demand forecasting and inventory analytics project built around a fictional film-production
equipment rental company, **CineStock Production Rentals**. The project uses Python, SQL/SQLite, time-series
forecasting, and Tableau to answer one business question:

> Which equipment SKUs are at risk of insufficient inventory during upcoming production periods, and what
> inventory or reorder actions should operations teams take?

## About the data

This project uses a **synthetic dataset** generated specifically for this project. It is not real company
data. Generation logic, assumptions, and known limitations are documented in `src/generate_data.py` and will
be summarized in the full README once the dataset is built.

## Repository structure

```
film-production-demand-forecasting/
├── data/           raw, processed, and output datasets
├── database/       SQLite database
├── sql/            business-analysis SQL queries
├── notebooks/      exploratory and forecasting notebooks
├── src/            Python scripts (data generation, cleaning, database load, forecasting, inventory)
├── tableau/        dashboard notes and packaged workbook
└── images/         dashboard screenshots
```

## How to run (placeholder)

Setup and reproduction instructions will be added here once the pipeline is complete.

---
*Full documentation — business problem, methodology, SQL analysis, forecasting approach, inventory
methodology, results, dashboard, assumptions, and limitations — will be added in later phases of
development.*
