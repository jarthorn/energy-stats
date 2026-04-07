"""
Management command: railway_etl_pipeline

Thin wrapper intended for Railway one-off jobs.

Runs the full ETL/backfill pipeline for production.
This will backfill the entire database from upstream sources.
"""

from __future__ import annotations

from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Run migrations and the full ETL/backfill pipeline for Production (thin wrapper)."

    def add_arguments(self, parser):
        parser.add_argument("--start-date", default="2025-01", help="Start date used for data backfills (YYYY-MM).")

    def handle(self, *args, **options):
        start_date: str = options["start_date"]

        self.stdout.write("Running ETL pipeline...")
        call_command("extract_ember", start_date=start_date)
        call_command("transform_and_load")
        call_command("load_monthly_records")
        call_command("load_country_energy_balance")
        call_command("backfill_country_tracker_years")

        self.stdout.write(self.style.SUCCESS("Production ETL pipeline complete."))
