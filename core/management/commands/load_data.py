"""
Management command: load_data

Fetches monthly electricity generation data from the Ember API for every
known country and populates (or updates) the following models:

    - MonthlyGenerationData  (one row per country / month / fuel type)
    - Country                (one row per country — aggregated stats)
    - Fuel                   (one row per fuel type — aggregated stats)
    - CountryFuel            (one row per country+fuel pair — aggregated stats)

The command is fully idempotent: existing rows are updated in-place and only
missing rows are inserted.

Usage:
    python manage.py load_data
    python manage.py load_data --start-date 2022-01
    python manage.py load_data --country GBR DEU FRA
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, datetime

from django.core.management.base import BaseCommand, CommandError

from core.country_codes import CountryCode
from core.models import Country, CountryFuel, Fuel, MonthlyGenerationData
from energystats.tasks.load_ember import EmberApiClient

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_date(date_str: str) -> date:
    """Convert 'YYYY-MM' or 'YYYY-MM-DD' from the API into a date object.

    Ember returns dates as 'YYYY-MM-DD', but we normalise to the 1st of the
    month regardless.
    """
    dt = datetime.strptime(date_str[:7], "%Y-%m")
    return dt.date().replace(day=1)


def _rolling_12_months(
    records: list[dict],
    all_dates: list[date],
    fuel_type: str,
) -> tuple[float, float]:
    """
    Return (latest_12_months_sum, previous_12_months_sum) for a given fuel type.

    ``all_dates`` must be the sorted, deduplicated list of dates present in
    ``records`` so we can identify the most recent 12-month window.
    """
    if not all_dates:
        return 0.0, 0.0

    by_date: dict[date, float] = {
        _parse_date(r["date"]): r.get("generation_twh") or 0.0
        for r in records
        if r.get("series") == fuel_type or r.get("fuel_type") == fuel_type
    }

    sorted_dates = sorted(all_dates)
    latest_12 = sorted_dates[-12:]
    previous_12 = sorted_dates[-24:-12]

    latest_sum = sum(by_date.get(d, 0.0) for d in latest_12)
    previous_sum = sum(by_date.get(d, 0.0) for d in previous_12)
    return latest_sum, previous_sum


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------

class Command(BaseCommand):
    help = (
        "Fetch electricity generation data from the Ember API and populate "
        "MonthlyGenerationData, Country, Fuel, and CountryFuel tables."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--start-date",
            default="2000-01",
            help="Earliest month to fetch data for (YYYY-MM). Default: 2000-01",
        )
        parser.add_argument(
            "--country",
            nargs="*",
            metavar="CODE",
            help=(
                "ISO-3 country codes to load (e.g. GBR DEU). "
                "Defaults to all known countries."
            ),
        )

    def handle(self, *args, **options):
        start_date: str = options["start_date"]
        requested: list[str] | None = options["country"]

        # Resolve the list of CountryCode values to process
        if requested:
            try:
                country_codes = [CountryCode(c.upper()) for c in requested]
            except ValueError as exc:
                raise CommandError(str(exc)) from exc
        else:
            country_codes = list(CountryCode)

        try:
            client = EmberApiClient(start_date=start_date)
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        # Accumulate cross-country fuel stats for Fuel model population
        # fuel_type -> list of generation_twh for latest/previous windows
        fuel_all_latest: dict[str, list[float]] = defaultdict(list)
        fuel_all_previous: dict[str, list[float]] = defaultdict(list)
        fuel_country_count: dict[str, int] = defaultdict(int)

        total_countries = len(country_codes)

        for idx, country_code in enumerate(country_codes, start=1):
            self.stdout.write(
                f"[{idx}/{total_countries}] Fetching {country_code}..."
            )

            try:
                raw_records = client.fetch_country(country_code)
            except Exception as exc:  # noqa: BLE001
                self.stderr.write(
                    self.style.WARNING(
                        f"  Skipping {country_code}: API error — {exc}"
                    )
                )
                continue

            if not raw_records:
                self.stdout.write(
                    self.style.WARNING(f"  No data returned for {country_code}.")
                )
                continue

            # ------------------------------------------------------------------
            # 1. Upsert MonthlyGenerationData rows
            # ------------------------------------------------------------------
            monthly_created = monthly_updated = 0
            all_dates_for_country: list[date] = []

            for r in raw_records:
                row_date = _parse_date(r["date"])
                all_dates_for_country.append(row_date)

                fuel_type = r.get("series", "")
                obj, created = MonthlyGenerationData.objects.update_or_create(
                    country_code=str(country_code),
                    date=row_date,
                    fuel_type=fuel_type,
                    defaults={
                        "country": r.get("entity", ""),
                        "is_aggregate_entity": r.get("is_aggregate_entity", False),
                        "is_aggregate_series": r.get("is_aggregate_series", False),
                        "generation_twh": r.get("generation_twh") or 0.0,
                        "share_of_generation_pct": r.get("share_of_generation_pct") or 0.0,
                    },
                )
                if created:
                    monthly_created += 1
                else:
                    monthly_updated += 1

            self.stdout.write(
                f"  MonthlyGenerationData: {monthly_created} created, "
                f"{monthly_updated} updated."
            )

            # ------------------------------------------------------------------
            # 2. Compute per-country aggregates from what we just upserted
            # ------------------------------------------------------------------
            unique_dates = sorted(set(all_dates_for_country))
            latest_12_dates = unique_dates[-12:]
            previous_12_dates = unique_dates[-24:-12]

            country_name = raw_records[0].get("entity", str(country_code))
            latest_month = latest_12_dates[-1] if latest_12_dates else date.today()

            # Total generation across all fuel types per month, then sum windows
            total_by_date: dict[date, float] = defaultdict(float)
            for r in raw_records:
                total_by_date[_parse_date(r["date"])] += r.get("generation_twh") or 0.0

            country_latest = sum(total_by_date.get(d, 0.0) for d in latest_12_dates)
            country_previous = sum(total_by_date.get(d, 0.0) for d in previous_12_dates)

            # ------------------------------------------------------------------
            # 3. Upsert Country (rank is set in a second pass below)
            # ------------------------------------------------------------------
            country_obj, created = Country.objects.update_or_create(
                code=str(country_code),
                defaults={
                    "name": country_name,
                    "summary": "",  # populated externally / future AI step
                    "electricity_rank": 0,  # ranked in post-processing below
                    "generation_latest_12_months": country_latest,
                    "generation_previous_12_months": country_previous,
                },
            )
            action = "created" if created else "updated"
            self.stdout.write(f"  Country '{country_name}': {action}.")

            # ------------------------------------------------------------------
            # 4. Per-fuel aggregates for this country → CountryFuel
            # ------------------------------------------------------------------
            fuel_types_in_country = {r.get("series", "") for r in raw_records}

            for fuel_type in fuel_types_in_country:
                if not fuel_type:
                    continue

                fuel_records = [r for r in raw_records if r.get("series") == fuel_type]

                fuel_by_date: dict[date, float] = {
                    _parse_date(r["date"]): r.get("generation_twh") or 0.0
                    for r in fuel_records
                }
                share_by_date: dict[date, float] = {
                    _parse_date(r["date"]): r.get("share_of_generation_pct") or 0.0
                    for r in fuel_records
                }

                fuel_latest = sum(fuel_by_date.get(d, 0.0) for d in latest_12_dates)
                fuel_previous = sum(fuel_by_date.get(d, 0.0) for d in previous_12_dates)
                avg_share = (
                    sum(share_by_date.get(d, 0.0) for d in latest_12_dates) / len(latest_12_dates)
                    if latest_12_dates else 0.0
                )

                # Accumulate globally for Fuel model ranking
                fuel_all_latest[fuel_type].append(fuel_latest)
                fuel_all_previous[fuel_type].append(fuel_previous)
                fuel_country_count[fuel_type] += 1

                # Upsert Fuel (rank computed after all countries are processed)
                fuel_obj, _ = Fuel.objects.update_or_create(
                    type=fuel_type,
                    defaults={
                        "rank": 0,  # ranked in post-processing below
                        "summary": "",  # populated externally / future AI step
                    },
                )

                # Upsert CountryFuel
                CountryFuel.objects.update_or_create(
                    country=country_obj,
                    fuel=fuel_obj,
                    defaults={
                        "share": avg_share,
                        "latest_month": latest_month,
                        "generation_latest_12_months": fuel_latest,
                        "generation_previous_12_months": fuel_previous,
                    },
                )

        # ----------------------------------------------------------------------
        # 5. Post-processing: assign electricity_rank to Country rows
        # ----------------------------------------------------------------------
        self.stdout.write("\nRanking countries by total generation...")
        countries_by_generation = Country.objects.order_by("-generation_latest_12_months")
        for rank, country_obj in enumerate(countries_by_generation, start=1):
            country_obj.electricity_rank = rank
            country_obj.save(update_fields=["electricity_rank"])

        # ----------------------------------------------------------------------
        # 6. Post-processing: assign rank to Fuel rows
        # ----------------------------------------------------------------------
        self.stdout.write("Ranking fuel types by total global generation...")
        fuels_by_generation = Fuel.objects.order_by(
            # We rank by the sum of latest-12-month generation across all countries
            # stored on CountryFuel. This avoids keeping a separate in-memory dict.
        )
        # Use DB aggregation for correctness
        from django.db.models import Sum
        fuel_totals = (
            CountryFuel.objects
            .values("fuel__type")
            .annotate(total=Sum("generation_latest_12_months"))
            .order_by("-total")
        )
        for rank, row in enumerate(fuel_totals, start=1):
            Fuel.objects.filter(type=row["fuel__type"]).update(rank=rank)

        self.stdout.write(self.style.SUCCESS("\nDone. All models updated successfully."))
