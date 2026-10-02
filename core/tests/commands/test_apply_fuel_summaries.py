from __future__ import annotations

import json
import tempfile
from datetime import date
from io import StringIO
from pathlib import Path

from django.test import TestCase, override_settings

from core.management.commands.transform_and_load import _apply_fuel_summaries
from core.models import Country, CountryFuel, Fuel


class ApplyFuelSummariesTests(TestCase):
    def setUp(self):
        self.country = Country.objects.create(
            name="Testland",
            code="TST",
            summary="Test country",
            electricity_rank=1,
            generation_latest_12_months=100.0,
            generation_previous_12_months=90.0,
        )
        self.fuel = Fuel.objects.create(
            type="Other",
            rank=1,
            summary="Stale summary that must be cleared on reload.",
            top_country_generation=self.country,
            top_country_share=self.country,
        )
        CountryFuel.objects.create(
            country=self.country,
            fuel=self.fuel,
            share=42.5,
            latest_month=date(2024, 12, 1),
            generation_latest_12_months=1234.5,
            generation_previous_12_months=1000.0,
        )

    def _write_summaries(self, base_dir: Path, summaries: dict[str, str]) -> None:
        data_dir = base_dir / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / "fuel-summaries.json").write_text(json.dumps(summaries), encoding="utf-8")

    def test_missing_json_summary_does_not_accumulate_on_reload(self):
        """When the JSON has no entry for a fuel, reloads must not append country stats again."""
        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp)
            self._write_summaries(base_dir, {})

            with override_settings(BASE_DIR=base_dir):
                _apply_fuel_summaries(StringIO())
                first = Fuel.objects.get(pk=self.fuel.pk).summary
                _apply_fuel_summaries(StringIO())
                second = Fuel.objects.get(pk=self.fuel.pk).summary

        self.assertEqual(first, second)
        self.assertNotIn("Stale summary", first)
        self.assertEqual(first.count("The country with the most generation"), 1)
        self.assertEqual(first.count("The country with the largest share"), 1)

    def test_json_summary_is_reset_before_appending_country_stats(self):
        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp)
            self._write_summaries(base_dir, {"Other": "Base fuel summary."})

            with override_settings(BASE_DIR=base_dir):
                _apply_fuel_summaries(StringIO())
                first = Fuel.objects.get(pk=self.fuel.pk).summary
                _apply_fuel_summaries(StringIO())
                second = Fuel.objects.get(pk=self.fuel.pk).summary

        self.assertEqual(first, second)
        self.assertTrue(first.startswith("Base fuel summary."))
        self.assertEqual(first.count("Base fuel summary."), 1)
        self.assertEqual(first.count("The country with the most generation"), 1)
