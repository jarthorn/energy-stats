# Objective

This is a web application that displays data about electricity grids for countries around the world. For the end user, it is a static web site that they can browse to explore data about the energy transition for particular countries. On the backend, the app scrapes data from a variety of sources and places them in a local sqlite database. A key principle is that everything in this local database can be recomputed from external primary sources, so we don't need to worry about data resiliency.

A secondary objective is enabling the author to learn more about Python and Django. Please stick to normative standard Django project structure and approaches, and let me know if I am straying from established patterns.

# Tech stack

- Python 3.14
- uv for environment management. Always use uv to run python.
- Django 6.0.2.
- SQLite (local) / Postgres (production)
- Ruff for python formatting.
- Production deployment to [railway](https://railway.com)
- gunicorn as a base HTTP server
- The whitenoise library for serving static files.

# Useful scripts

- `bin/format` runs code lint and formatter. You should run this whenever code is modified.
- `bin/test` runs all tests. This should run and all tests pass before completing a coding task.
- `bin/load` runs the entire ETL pipeline. This hits the network and 3rd party services. Don't run this without asking first.

# Data sources

This project uses source data from several different organizations. Since each organization has slightly varying methodologies, it is important that we never directly compare or combine data together from multiple sources. For electricity generation data, Ember is the preferred data source. For total energy supply and primary energy sources, we use data from the Energy Institute's data sets. The CODERS database is used to provide granular statistics on Canadian electricity generation at the provincial level.

# Architecture

## Layout

- One Django project (`energystats/`) and one app (`core/`). Settings are driven by environment variables (loaded from `.env`); see the README for the list.
- `core/models.py`: all models. `core/views.py`: all views (read-only pages; no forms, no user-facing writes). `core/urls.py`: URL routes. `core/templates/core/`: templates.
- `core/management/commands/`: the ETL pipeline and Railway wrapper commands. `energystats/tasks/`: thin HTTP clients for the Ember and CODERS APIs (`load_ember.py`, `load_coders.py`). They fetch and return raw records; interpretation belongs in the management commands.
- `data/`: committed source files that are loaded by commands (the filtered Energy Institute CSV and `fuel-summaries.json`), plus one-off preprocessing scripts for the raw, git-ignored CSVs.
- Tests are in `core/tests/` (`commands/`, `models/`, plus top-level view tests).

## Data flow

The site is read-heavy. Almost everything shown to users is precomputed during ETL, so views mostly read rows rather than aggregating raw data at request time.

1. `extract_ember` (Ember API) loads raw monthly rows into `MonthlyGenerationData`. This is a staging table, and the only raw Ember data.
2. `transform_and_load` derives `Country`, `Fuel`, `CountryFuel` (latest 12 months, YoY growth), `CountryFuelYear`, `FuelYear` and `FuelMonth`. It also ranks countries and fuels, and appends top-country sentences to the fuel summaries from `data/fuel-summaries.json`.
3. `load_monthly_records` derives `MonthlyGenerationRecord`, the all-time monthly generation/share records per country and fuel.
4. `load_country_energy_balance` loads `CountryEnergyBalanceYear` (total energy supply by source, from the Energy Institute CSV).
5. `backfill_country_tracker_years` combines the electricity data with the energy balance to produce `CountryTrackerYear` (per country, per year) and `TrackerYear` (global, weighted by generation) for the "tracker" page.
6. `load_generation_units` (CODERS, Canada only) is run separately from `bin/load`. It replaces `GenerationUnit` rows and rebuilds `GenerationUnitRegionFuelYear` and `GenerationUnitRegionYear`. It needs the Canada `Country` and `Fuel` rows, so it must run after step 2.

Each step depends on the output of the earlier ones, so order matters. The `railway_etl_pipeline` command repeats steps 1-5, and `railway_deploy` runs migrations and `collectstatic`.

## Conventions worth knowing

- Models named `*Year` or `*Month`, plus `CountryTrackerYear` and `GenerationUnitRegion*`, are memoized aggregates. They are derived data, not a source of truth, so fix the ETL command that populates them rather than editing rows.
- Natural keys are enforced with `unique_together`, and commands rebuild or upsert rows using them (this is what makes loads idempotent). `Country` is keyed by ISO-3 `code` and `Fuel` by its `type` string, which is Ember's fuel name. Month values are always stored as the first day of the month.
- Ember rows include aggregate entities and aggregate series (`is_aggregate_entity`, `is_aggregate_series`) and a "Net imports" balancing series. Be careful to exclude these when summing across fuels or countries, or shares can exceed 100%. See `EXCLUDED_ELECTRICITY_FUELS` in `backfill_country_tracker_years.py`.
- "Low-carbon" electricity is defined as Hydro, Nuclear, Wind, Solar, Bioenergy and Other renewables. This set is currently defined in both `core/views.py` and `backfill_country_tracker_years.py`, so keep the two in sync (or consolidate them).
- Supported countries are an enum in `core/country_codes.py` (Ember's ISO-3 codes), and `extract_ember` only loads those.
- Most pages use rolling 12-month windows (latest 12 vs. previous 12) rather than calendar years, so seasonal swings don't distort comparisons.
- Charts are built server-side with Plotly in the views (`fig.to_html(...)`, Plotly JS from a CDN) and embedded in templates. `core/views.py` is large, so look for existing helpers there before adding new chart code.
- Static files are served by WhiteNoise from `static/` and collected to `staticfiles/` at deploy time.
- Admin is optional and gated by `DJANGO_ENABLE_ADMIN` (defaults to the value of `DJANGO_DEBUG`).

# General instructions

- Don't reformat or modify unrelated parts of the code when you make a change. The diff for each change should always be relevant to the change that I requested. I don't like to mix cosmetic and behavioural changes in the same commit.
- I am an experienced developer, you don't need to offer to make trivial code changes for me.
- Please ask clarifying questions if there are key technical decisions to make and you have low confidence in the right choice or believe it is subjective.
- Always add a regression test when fixing a bug. The test should fail when the fix is not applied. In other cases, I don't insist on complete code coverage, but complex implementation logic should be a flag for adding tests that verify the output of that logic (without duplicating the logic itself). All tests should go in the `tests` folder.
- Look for opportunities to break large functions up by introducing helper functions for key semantic chunks of the logic. Helper functions with clearly descriptive names not only avoid code duplication, they improve readability for humans.
- The database is disposable. Never add data directly to the database that can't be regenerated from files in the `data` folder or third party APIs. All data should be loaded via management commands that can be repeated. All data loading commands should be idempotent.
- Never commit changes to git. I use the git commit and push process as my final human validation step.
- Update the README.md file when new setup instructions are needed. A human or agent reading this file should be able to perform any required project setup.
