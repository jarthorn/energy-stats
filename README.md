## Energy Stats

Welcome to Energy Stats, a web app for exploring electricity grid and energy-transition data for countries around the world.

For end users, this is a **browseable, mostly-static website** with country-level pages and charts. On the backend, it **extracts/scrapes source datasets** and loads them into a local database. A core principle is that **everything in the database can be recomputed from external primary sources**, so the app doesn’t rely on manually-curated state for resilience. Only the highest quality data sources are used, primarily: The Energy Institute, International Energy Agency, and Ember.

## Contributing

Contributions are welcome in any form:

- **Feedback / ideas**: open an issue describing what you’d like to see.
- **Bug reports**: include steps to reproduce, expected vs actual behavior, and screenshots/logs if relevant.
- **Pull requests**: small, focused PRs are easiest to review. Please include a short test plan in the PR description.

### Development guidelines

- **Use `uv`** to run Python and Django commands (`uv run ...`).
- **Run Ruff before committing**:

```bash
uv run ruff check .
uv run ruff format .
```

## Tech stack

- **Python**: 3.14+
- **Environment / runner**: `uv` (use `uv run ...` for commands)
- **Web framework**: Django 6
- **DB**: SQLite locally, Postgres in production
- **Static files**: WhiteNoise (production-friendly)
- **Formatting / linting**: Ruff

## Data sources

This project uses datasets from multiple organizations. Because methodologies differ, we **do not directly compare or combine metrics across sources**. As a general rule:

- **Electricity generation**: Ember is preferred.
- **Total energy supply / primary energy**: Energy Institute datasets.

## Local setup

These steps take a fresh machine from nothing to a fully working copy of the app, including data. Everything the app needs is either in this repository or can be re-obtained from an external service. The only things that are **not** in the repository are your `.env` file (secrets) and the SQLite database (which is regenerated from source data).

### Prerequisites

- [`uv`](https://github.com/astral-sh/uv) installed (e.g. `brew install uv`).
- Python 3.14.2 or newer (this will be installed by `uv sync` if not already available).
- Optional: a local Postgres server, only if you want to develop against Postgres instead of SQLite.

### Install dependencies

```bash
uv sync
```

This creates `.venv/` and installs the exact versions pinned in `uv.lock` (including Ruff).

### Create a local `.env`

Create a file at the project root named `.env` (it is loaded automatically by Django settings). This file should never be shared or committed to git.

#### Generate a `DJANGO_SECRET_KEY`

`DJANGO_SECRET_KEY` is required, and you generate a fresh one for each machine. Run:

```bash
uv run python -c "import secrets; print(secrets.token_urlsafe(50))"
```

Paste the output into `.env` as the value of `DJANGO_SECRET_KEY`.

#### Fill in the rest of `.env`

A typical local development file:

```dotenv
# Django
DJANGO_SECRET_KEY=paste-the-generated-key-here
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1

# Optional: expose /admin/ (defaults to the value of DJANGO_DEBUG)
# DJANGO_ENABLE_ADMIN=True

# Optional: use Postgres instead of SQLite (e.g. Railway or local Postgres)
# DATABASE_URL=postgres://USER:PASSWORD@HOST:5432/DBNAME

# Required for Ember extraction (extract_ember)
EMBER_API_KEY=your_ember_api_key

# Required for CODERS generation-unit loading (load_generation_units)
CODERS_API_KEY=your_coders_api_key
```

Notes:

- **`DJANGO_SECRET_KEY` is required**. If it’s missing, Django will crash on startup.
- `DJANGO_DEBUG` defaults to `False`. Without `DJANGO_DEBUG=True` locally you get production-style behaviour (no debug pages, and the admin is disabled unless `DJANGO_ENABLE_ADMIN=True`).
- If `DJANGO_ALLOWED_HOSTS` is not set, it defaults to `localhost,127.0.0.1`.
- If `DATABASE_URL` is not set, the app uses **SQLite** at `db.sqlite3`. When `DATABASE_URL` is set, the connection **requires SSL**, so a local Postgres server must have SSL enabled (the simplest option for local development is to use SQLite).
- `EMBER_API_KEY` is required by `extract_ember`, which is the first step of the data pipeline, so you need it to load the most valuable data sets. API keys are freely available from [Ember's API page](https://ember-energy.org/data/api/).
- `CODERS_API_KEY` is needed only for Canadian generation-unit data. Request a free account at the [CODERS dashboard](https://coders.cme-emh.ca/).

### Initialize the database

```bash
uv run python manage.py migrate
```

This creates an empty `db.sqlite3`. Don't copy the database file from your old machine; it is git-ignored and is rebuilt from source data in the next section.

### Load the data

A new database is empty, so the site won't show anything useful until you load data. Follow [Loading / refreshing data](#loading--refreshing-data) below. A full load requires the API keys from your `.env` and an internet connection, and takes a while.

### Verify the setup

```bash
./bin/test
```

This runs `ruff check` followed by the Django test suite. Both should pass on a fresh checkout.

### Run the development server

```bash
uv run python manage.py runserver
```

Then visit `http://127.0.0.1:8000/`.

## Loading / refreshing data

This repo contains several Django management commands used to extract, transform, and load datasets.

If you just want to run the “full” pipeline locally, start with the `bin/load` script:

```bash
./bin/load
```

It runs (via `uv`) a sequence of management commands:

- `extract_ember --start-date 2025-01` (requires `EMBER_API_KEY`; downloads from the Ember API)
- `transform_and_load`
- `load_monthly_records`
- `load_country_energy_balance` (reads the Energy Institute CSV committed in `data/`; no download needed)
- `backfill_country_tracker_years`

`bin/load` does **not** load Canadian generation units. That's a separate step that requires `CODERS_API_KEY`, and it must run after `transform_and_load` (it needs the Canada country and fuel rows to exist):

```bash
uv run python manage.py load_generation_units
```

If you only want to load the Energy Institute balance data:

```bash
uv run python manage.py load_country_energy_balance
```

To pull Ember history further back, run the steps individually with an earlier start date, e.g. `uv run python manage.py extract_ember --start-date 2015-01`, then re-run the remaining commands from `bin/load`.

### Source data files in `data/`

The files the app actually loads are committed to the repo, so cloning is enough: `data/ei-world-consolidated-panel-filtered-2025.csv` (used by `load_country_energy_balance`) and `data/fuel-summaries.json` (used by `transform_and_load`).

A few large, raw source files are git-ignored and are **not** restored by cloning: `data/ei-world-consolidated-panel-2024.csv`, `data/ei-world-consolidated-panel-2025.csv` and `data/iea-world-energy-balances-2025.csv`. They are only inputs to the one-off preprocessing scripts in `data/` (`preprocess_ei_data.py`, `convert_ei_narrow_to_panel.py`, `preprocess_iea_data.py`) that produce the committed `*-filtered-*.csv` files. You only need them if you want to regenerate those filtered files (for example when a new Energy Institute release comes out); re-download them from the sources listed under [Data source attribution](#data-source-attribution), or copy them from your old machine.

## Data source attribution

This project draws from data provided by multiple organizations. Because methodologies can differ, the site avoids directly combining or comparing metrics from different sources as if they were identical. In every case, we strive to use the most reputable and up-to-date data available. Our main sources are:

- **Energy Institute (EI) — Statistical Review of World Energy**: Total energy supply and related energy-system totals. See the source [dataset](https://www.energyinst.org/statistical-review/resources-and-data-downloads) and [methodology](https://sr25downloads.blob.core.windows.net/production-reports/Methodology.pdf). Note that while the IEA is the key global source for primary energy data, their restrictive licensing prevents us from using it for this site. The Energy Institute is an independent and well regarded alternative source.

- **Ember — Monthly Electricity Data**: Monthly electricity generation data for 88 countries. See the source [dataset](https://ember-energy.org/data/monthly-electricity-data/) and [methodology](https://ember-energy.org/app/uploads/2024/05/Ember-Electricity-Data-Methodology.pdf). Note that data series from Ember for each country start at different years, and are updated on different cadences. In most cases, we use rolling 12-month data windows so that the most recent data are included, while avoiding the skewing effect of seasonal fluctuations. Also noteworthy, data from China starts in 2015, and data from India starts in 2019. These countries are large enough that global-level statistics can be skewed when viewed year over year over those time periods.

- **CODERS — Canadian Open-Source Database for Energy Research and Systems-Modelling**: Canadian generation data is sourced from the Canadian Open-Source Database for Energy Research and Systems-Modelling ([CODERS](https://coders.cme-emh.ca/)). Licensed under [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/). On this site, generation-unit capacity and average annual energy are aggregated by province/territory.

