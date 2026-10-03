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

### Prerequisites

- Python 3.14+
- [`uv`](https://github.com/astral-sh/uv) installed

### Install dependencies

```bash
uv sync
```

### Create a local `.env`

Create a file at the project root named `.env` (it is loaded automatically by Django settings).

Minimum required:

```dotenv
DJANGO_SECRET_KEY=change-me-in-local-dev
```

Common optional settings:

```dotenv
# Django
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1

# Optional: use Postgres instead of SQLite (e.g. Railway or local Postgres)
# DATABASE_URL=postgres://USER:PASSWORD@HOST:5432/DBNAME

# Required for Ember extraction jobs / commands
EMBER_API_KEY=your_ember_api_key

# Required for CODERS generation-unit load commands
CODERS_API_KEY=your_coders_api_key
```

Notes:

- **`DJANGO_SECRET_KEY` is required**. If it’s missing, Django will crash on startup.
- If `DATABASE_URL` is not set, the app uses **SQLite** at `db.sqlite3`.
- `EMBER_API_KEY` is not strictly required, but it is essential to get the most valuable data sets. Ember API keys are freely available from [Ember's API page](https://ember-energy.org/data/api/).
- `CODERS_API_KEY` is needed for Canadian generation-unit data. Request a free account at the [CODERS dashboard](https://coders.cme-emh.ca/).

### Initialize the database

```bash
uv run python manage.py migrate
```

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

- `extract_ember` (requires `EMBER_API_KEY`)
- `transform_and_load`
- `load_monthly_records`
- `load_country_energy_balance`

If you only want to load the Energy Institute balance data:

```bash
uv run python manage.py load_country_energy_balance
```

## Data source attribution

This project draws from data provided by multiple organizations. Because methodologies can differ, the site avoids directly combining or comparing metrics from different sources as if they were identical. In every case, we strive to use the most reputable and up-to-date data available. Our main sources are:

- **Energy Institute (EI) — Statistical Review of World Energy**: Total energy supply and related energy-system totals. See the source [dataset](https://www.energyinst.org/statistical-review/resources-and-data-downloads) and [methodology](https://sr25downloads.blob.core.windows.net/production-reports/Methodology.pdf). Note that while the IEA is the key global source for primary energy data, their restrictive licensing prevents us from using it for this site. The Energy Institute is an independent and well regarded alternative source.

- **Ember — Monthly Electricity Data**: Monthly electricity generation data for 88 countries. See the source [dataset](https://ember-energy.org/data/monthly-electricity-data/) and [methodology](https://ember-energy.org/app/uploads/2024/05/Ember-Electricity-Data-Methodology.pdf). Note that data series from Ember for each country start at different years, and are updated on different cadences. In most cases, we use rolling 12-month data windows so that the most recent data are included, while avoiding the skewing effect of seasonal fluctuations. Also noteworthy, data from China starts in 2015, and data from India starts in 2019. These countries are large enough that global-level statistics can be skewed when viewed year over year over those time periods.

- **CODERS — Canadian Open-Source Database for Energy Research and Systems-Modelling**: Canadian generation data is sourced from the Canadian Open-Source Database for Energy Research and Systems-Modelling ([CODERS](https://coders.cme-emh.ca/)). Licensed under [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/). On this site, generation-unit capacity and average annual energy are aggregated by province/territory.

