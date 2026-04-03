"""
Management command: load_monthly_records

Backfills the MonthlyGenerationRecord table from MonthlyGenerationData by
identifying new monthly records for each (country, fuel) pair.

Usage:
    python manage.py load_monthly_records
    python manage.py load_monthly_records --country GBR DEU FRA
"""

from __future__ import annotations

import logging

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import (
    Country,
    Fuel,
    MonthlyGenerationData,
    MonthlyGenerationRecord,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Backfill the MonthlyGenerationRecord table by scanning "
        "MonthlyGenerationData for new monthly records in generation and share."
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
            except Exception as exc:  # noqa: BLE001
                raise CommandError(str(exc)) from exc
        else:
            country_codes = list(MonthlyGenerationData.objects.values_list("country_code", flat=True).distinct())

        total_countries = len(country_codes)
        if total_countries == 0:
            self.stdout.write("No countries found in MonthlyGenerationData. Nothing to do.")
            return

        self.stdout.write(f"Starting backfill of MonthlyGenerationRecord for {total_countries} countries...")

        total_created = 0

        for idx, code in enumerate(country_codes, start=1):
            self.stdout.write(f"[{idx}/{total_countries}] Processing {code}...")

            country_obj = Country.objects.filter(code=code).first()
            if country_obj is None:
                self.stderr.write(self.style.WARNING(f"  Skipping {code}: no matching Country record found."))
                continue

            records = MonthlyGenerationData.objects.filter(country_code=code).order_by("date")

            if not records.exists():
                self.stdout.write(self.style.WARNING(f"  No data found in MonthlyGenerationData for {code}."))
                continue

            with transaction.atomic():
                # Always remove any existing records for this country first.
                deleted_count, _ = MonthlyGenerationRecord.objects.filter(country=country_obj).delete()
                if deleted_count:
                    self.stdout.write(f"  Deleted {deleted_count} existing MonthlyGenerationRecord rows for {code}.")

                created_for_country = self._backfill_country_records(
                    country_obj=country_obj,
                    records=records,
                )

            total_created += created_for_country
            self.stdout.write(f"  Created {created_for_country} MonthlyGenerationRecord rows for {code}.")

        self.stdout.write(
            self.style.SUCCESS(f"\nBackfill complete. Created {total_created} MonthlyGenerationRecord rows.")
        )

    def _backfill_country_records(self, *, country_obj: Country, records) -> int:
        """
        For a given country and its MonthlyGenerationData records, identify
        all monthly records (generation and share) per fuel.
        """
        created_count = 0

        fuel_types = set[str](records.values_list("fuel_type", flat=True))
        for fuel_type in fuel_types:
            if not fuel_type:
                continue

            fuel_records = records.filter(
                fuel_type=fuel_type,
                is_aggregate_entity=False,
                is_aggregate_series=False,
            ).order_by("date")

            if not fuel_records.exists():
                continue

            fuel_obj, _ = Fuel.objects.get_or_create(
                type=fuel_type,
                defaults={"rank": 0},
            )

            to_create: list[MonthlyGenerationRecord] = []
            max_generation = None
            max_share = None

            for r in fuel_records:
                generation = r.generation_twh
                share = r.share_of_generation_pct

                # New record for absolute generation
                if max_generation is None or generation > max_generation:
                    max_generation = generation
                    to_create.append(
                        MonthlyGenerationRecord(
                            country=country_obj,
                            fuel=fuel_obj,
                            date=r.date,
                            record_type="generation",
                            generation_twh=generation,
                            share_of_generation_pct=share,
                        )
                    )

                # New record for share of generation
                if max_share is None or share > max_share:
                    max_share = share
                    to_create.append(
                        MonthlyGenerationRecord(
                            country=country_obj,
                            fuel=fuel_obj,
                            date=r.date,
                            record_type="share",
                            generation_twh=generation,
                            share_of_generation_pct=share,
                        )
                    )

            if to_create:
                MonthlyGenerationRecord.objects.bulk_create(to_create)
                created_count += len(to_create)

        return created_count
