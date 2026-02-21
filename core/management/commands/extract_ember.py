"""
Management command: extract_ember

Extracts monthly electricity generation data from the Ember API and loads it
into the MonthlyGenerationData model. This is the 'Extract' phase of our ETL
pipeline.

Usage:
    python manage.py extract_ember
    python manage.py extract_ember --start-date 2022-01
    python manage.py extract_ember --country GBR DEU FRA
"""

from __future__ import annotations

import logging
from datetime import date, datetime

from django.core.management.base import BaseCommand, CommandError

from core.country_codes import CountryCode
from core.models import MonthlyGenerationData
from energystats.tasks.load_ember import EmberApiClient

logger = logging.getLogger(__name__)


def _parse_date(date_str: str) -> date:
    """Convert 'YYYY-MM' or 'YYYY-MM-DD' from the API into a date object.

    Ember returns dates as 'YYYY-MM-DD', but we normalise to the 1st of the
    month regardless.
    """
    dt = datetime.strptime(date_str[:7], "%Y-%m")
    return dt.date().replace(day=1)


class Command(BaseCommand):
    help = (
        "Extract electricity generation data from the Ember API and load it "
        "into the MonthlyGenerationData table."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--start-date",
            default="2023-01",
            help="Earliest month to fetch data for (YYYY-MM). Default: 2023-01",
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

        total_countries = len(country_codes)
        self.stdout.write(f"Starting Extraction from Ember API for {total_countries} countries...")

        for idx, country_code in enumerate(country_codes, start=1):
            self.stdout.write(
                f"[{idx}/{total_countries}] Extracting {country_code}..."
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

            monthly_created = monthly_updated = 0
            for r in raw_records:
                row_date = _parse_date(r["date"])
                fuel_type = r.get("series", "")

                # Load into MonthlyGenerationData
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

        self.stdout.write(self.style.SUCCESS("Extraction complete."))
