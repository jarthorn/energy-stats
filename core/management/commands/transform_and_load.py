"""
Management command: transform_and_load

Transforms data from the MonthlyGenerationData table and loads it into
Country, Fuel, and CountryFuel aggregate tables. This constitutes the
'Transform' and 'Load' phases of our ETL pipeline.

Usage:
    python manage.py transform_and_load
    python manage.py transform_and_load --country GBR DEU FRA
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Sum

from core.models import Country, CountryFuel, CountryFuelYear, Fuel, MonthlyGenerationData

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = (
        "Transform data from MonthlyGenerationData and load it into "
        "Country, Fuel, and CountryFuel tables."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--country",
            nargs="*",
            metavar="CODE",
            help=(
                "ISO-3 country codes to process (e.g. GBR DEU). "
                "Defaults to all countries present in MonthlyGenerationData."
            ),
        )

    def handle(self, *args, **options):
        requested: list[str] | None = options["country"]

        # Resolve the list of country codes to process
        if requested:
            try:
                country_codes = [c.upper() for c in requested]
            except Exception as exc:
                raise CommandError(str(exc)) from exc
        else:
            # Default to all countries that have data in our staging table
            country_codes = list(
                MonthlyGenerationData.objects.values_list("country_code", flat=True).distinct()
            )

        total_countries = len(country_codes)
        self.stdout.write(f"Starting Transform and Load for {total_countries} countries...")

        for idx, code in enumerate(country_codes, start=1):
            self.stdout.write(f"[{idx}/{total_countries}] Processing {code}...")

            # Fetch all monthly records for this country from staging
            records = MonthlyGenerationData.objects.filter(country_code=code).order_by("date")

            if not records.exists():
                self.stdout.write(self.style.WARNING(f"  No data found in MonthlyGenerationData for {code}."))
                continue

            # 1. Transform: Identify windows and calculate country metrics
            latest_12, previous_12 = _get_date_windows(records)
            if not latest_12:
                continue

            latest_month = latest_12[-1]
            country_name = records.first().country

            country_metrics = _transform_country_metrics(records, latest_12, previous_12)

            # 2. Load: Persist Country data
            country_obj = _load_country(code, country_name, country_metrics, latest_month)

            # 3. Transform & Load: Iterate through fuel types
            fuel_types = records.values_list("fuel_type", flat=True).distinct()

            for fuel_type in fuel_types:
                if not fuel_type:
                    continue

                fuel_records = records.filter(fuel_type=fuel_type)

                # Transform fuel data
                fuel_metrics = _transform_fuel_metrics(fuel_records, latest_12, previous_12)

                # Load fuel data and associations
                _load_fuel_data(country_obj, fuel_type, fuel_metrics, latest_month)

            # 4. Transform & Load: Annual Aggregations
            _load_annual_data(country_obj, records)

        # 5. Post-processing: Final Load phase (Rankings)
        _apply_rankings(self.stdout)

        self.stdout.write(self.style.SUCCESS("\nTransformation and Loading complete."))

# ---------------------------------------------------------------------------
# Transformation Helpers (Private)
# ---------------------------------------------------------------------------

def _get_date_windows(records) -> tuple[list[date], list[date]]:
    """
    Identify the latest 12-month and previous 12-month windows.
    Returns (latest_12_dates, previous_12_dates).
    """
    unique_dates = sorted(list(set(records.values_list("date", flat=True))))
    if not unique_dates:
        return [], []

    # We take the most recent 12 months for the 'latest' window
    # and the 12 months before that for the 'previous' window.
    latest_12 = unique_dates[-12:]
    previous_12 = unique_dates[-24:-12]
    return latest_12, previous_12

def _transform_country_metrics(
    records,
    latest_12_dates: list[date],
    previous_12_dates: list[date]
) -> dict:
    """
    Calculate country-level metrics: total generation for latest/previous
    windows and low-carbon percentage.
    """
    # Total generation across all fuel types per month
    total_by_date: dict[date, float] = defaultdict(float)
    for r in records:
        total_by_date[r.date] += r.generation_twh

    country_latest = sum(total_by_date.get(d, 0.0) for d in latest_12_dates)
    country_previous = sum(total_by_date.get(d, 0.0) for d in previous_12_dates)

    # Calculate low carbon percentage (Transform)
    low_carbon_generation = 0.0
    total_generation_except_imports = 0.0
    LOW_CARBON_FUELS = {"Hydro", "Nuclear", "Wind", "Solar", "Bioenergy", "Other renewables"}

    for r in records:
        if r.fuel_type == "Net imports":
            continue

        if r.date in latest_12_dates:
            total_generation_except_imports += r.generation_twh
            if r.fuel_type in LOW_CARBON_FUELS:
                low_carbon_generation += r.generation_twh

    low_carbon_pct = None
    if total_generation_except_imports > 0:
        low_carbon_pct = (low_carbon_generation / total_generation_except_imports) * 100

    return {
        "latest_total": country_latest,
        "previous_total": country_previous,
        "low_carbon_pct": low_carbon_pct,
    }

def _transform_fuel_metrics(
    fuel_records,
    latest_12_dates: list[date],
    previous_12_dates: list[date]
) -> dict:
    """Calculate per-fuel metrics: generation totals, average share, and growth."""
    fuel_by_date = {r.date: r.generation_twh for r in fuel_records}
    share_by_date = {r.date: r.share_of_generation_pct for r in fuel_records}

    fuel_latest = sum(fuel_by_date.get(d, 0.0) for d in latest_12_dates)
    fuel_previous = sum(fuel_by_date.get(d, 0.0) for d in previous_12_dates)

    avg_share = 0.0
    if latest_12_dates:
        avg_share = sum(share_by_date.get(d, 0.0) for d in latest_12_dates) / len(latest_12_dates)

    # Annual YoY Growth (%)
    annual_growth = None
    if fuel_previous > 0:
        annual_growth = ((fuel_latest / fuel_previous) - 1) * 100

    # Month YoY Growth (%)
    month_growth = None
    if latest_12_dates:
        latest_month_date = latest_12_dates[-1]
        try:
            # Same month in previous year
            prev_year_date = latest_month_date.replace(year=latest_month_date.year - 1)
            latest_month_gen = fuel_by_date.get(latest_month_date, 0.0)
            prev_year_month_gen = fuel_by_date.get(prev_year_date, 0.0)

            if prev_year_month_gen > 0:
                month_growth = ((latest_month_gen / prev_year_month_gen) - 1) * 100
        except (ValueError, IndexError):
            # Handle edge cases like leap years or missing data
            pass

    return {
        "latest_total": fuel_latest,
        "previous_total": fuel_previous,
        "avg_share": avg_share,
        "annual_yoy_growth": annual_growth,
        "month_yoy_growth": month_growth,
        "latest_month_gen": fuel_by_date.get(latest_12_dates[-1], 0.0) if latest_12_dates else 0.0,
        "latest_month_share": share_by_date.get(latest_12_dates[-1], 0.0) if latest_12_dates else 0.0,
    }

def _load_country(code: str, country_name: str, metrics: dict, latest_month: date) -> Country:
    """Persist transformed country metrics to the database (Load)."""
    country_obj, _ = Country.objects.update_or_create(
        code=code,
        defaults={
            "name": country_name,
            "generation_latest_12_months": metrics["latest_total"],
            "generation_previous_12_months": metrics["previous_total"],
            "latest_month": latest_month,
            "low_carbon_pct": metrics["low_carbon_pct"],
            "electricity_rank": 0,  # Ranked in post-processing
        },
    )
    return country_obj

def _load_fuel_data(
    country_obj: Country,
    fuel_type: str,
    metrics: dict,
    latest_month: date
) -> None:
    """Persist transformed fuel metrics and associations to the database (Load)."""
    fuel_obj, _ = Fuel.objects.update_or_create(
        type=fuel_type,
        defaults={"rank": 0},  # Rank is updated in a separate post-processing step
    )

    CountryFuel.objects.update_or_create(
        country=country_obj,
        fuel=fuel_obj,
        defaults={
            "share": metrics["avg_share"],
            "latest_month": latest_month,
            "generation_latest_12_months": metrics["latest_total"],
            "generation_previous_12_months": metrics["previous_total"],
            "month_yoy_growth": metrics["month_yoy_growth"],
            "annual_yoy_growth": metrics["annual_yoy_growth"],
            "generation_latest_month": metrics["latest_month_gen"],
            "share_latest_month": metrics["latest_month_share"],
        },
    )


def _apply_rankings(stdout) -> None:
    """
    Post-processing phase of Load: Update electricity ranks for countries
    and global ranks for fuel types.
    """
    stdout.write("\nRanking countries by total generation...")
    countries = Country.objects.order_by("-generation_latest_12_months")
    for rank, country in enumerate(countries, start=1):
        country.electricity_rank = rank
        country.save(update_fields=["electricity_rank"])

    stdout.write("Ranking fuel types by total global generation...")
    fuel_totals = (
        CountryFuel.objects
        .values("fuel__type")
        .annotate(total=Sum("generation_latest_12_months"))
        .order_by("-total")
    )
    for rank, row in enumerate(fuel_totals, start=1):
        Fuel.objects.filter(type=row["fuel__type"]).update(
            rank=rank,
            generation_latest_12_months=row["total"] or 0.0
        )

    stdout.write("Calculating all-time generation for fuel types...")
    all_time_totals = (
        MonthlyGenerationData.objects
        .values("fuel_type")
        .annotate(total=Sum("generation_twh"))
    )
    for row in all_time_totals:
        Fuel.objects.filter(type=row["fuel_type"]).update(generation_all_time=row["total"] or 0.0)


def _load_annual_data(country_obj: Country, records) -> None:
    """
    Calculate and persist annual aggregation for each fuel type.
    """
    annual_country_totals = defaultdict(float)
    annual_fuel_totals = defaultdict(float)
    year_months = defaultdict(set)
    fuel_types = set()

    for r in records:
        year = r.date.year
        # Use only non-aggregate series for the country total to avoid double counting
        if not r.is_aggregate_series:
            annual_country_totals[year] += r.generation_twh

        # Track generation for all fuel types (including aggregates like "Renewables")
        annual_fuel_totals[(year, r.fuel_type)] += r.generation_twh
        year_months[year].add(r.date.month)
        if r.fuel_type:
            fuel_types.add(r.fuel_type)

    years = sorted(annual_country_totals.keys())

    for year in years:
        is_complete = len(year_months[year]) == 12
        total_gen = annual_country_totals[year]

        for fuel_type in fuel_types:
            # Check if we have data for this fuel/year
            if (year, fuel_type) not in annual_fuel_totals:
                continue

            gen = annual_fuel_totals[(year, fuel_type)]
            share = (gen / total_gen * 100) if total_gen > 0 else 0.0

            # Growth calculation
            # "A value of zero is used if no data are available for the previous year."
            yoy_growth = 0.0
            if (year - 1, fuel_type) in annual_fuel_totals:
                prev_year_gen = annual_fuel_totals[(year - 1, fuel_type)]
                if prev_year_gen > 0:
                    yoy_growth = ((gen / prev_year_gen) - 1) * 100

            fuel_obj = Fuel.objects.get(type=fuel_type)

            CountryFuelYear.objects.update_or_create(
                country=country_obj,
                fuel=fuel_obj,
                year=year,
                defaults={
                    "is_complete": is_complete,
                    "share": share,
                    "generation": gen,
                    "yoy_growth": yoy_growth,
                },
            )
