from __future__ import annotations

from datetime import date

from django.test import TestCase

from core.management.commands.backfill_country_tracker_years import backfill_country_tracker_years
from core.models import (
    Country,
    CountryEnergyBalanceYear,
    CountryFuelYear,
    CountryTrackerYear,
    Fuel,
    MonthlyGenerationData,
)


class BackfillCountryTrackerYearsTests(TestCase):
    def setUp(self):
        self.country = Country.objects.create(
            name="Testland",
            code="TST",
            summary="Test country",
            electricity_rank=1,
            generation_latest_12_months=0.0,
            generation_previous_12_months=0.0,
        )
        self.fuel_coal = Fuel.objects.create(type="Coal", rank=1, summary="Coal")
        self.fuel_hydro = Fuel.objects.create(type="Hydro", rank=2, summary="Hydro")
        self.fuel_net_imports = Fuel.objects.create(type="Net imports", rank=999, summary="Net imports")

    def test_basic_backfill_all_sources_present(self):
        """
        All required inputs exist:
        - CountryEnergyBalanceYear provides energy shares
        - CountryFuelYear provides electricity rank + low-carbon share (via LOW_CARBON_ELECTRICITY_FUELS)
        - MonthlyGenerationData provides annual generation_twh (summed from months)
        """
        CountryEnergyBalanceYear.objects.create(
            country=self.country,
            year=2024,
            coal_supply=1,
            oil_supply=1,
            gas_supply=1,
            nuclear_supply=1,
            renewable_supply=1,
            total_supply=5,
            share_low_carbon=40.0,
            share_renewable=20.0,
            share_electricity=30.0,
        )

        # Total generation (all fuels) = 100. Low-carbon fuels include Hydro = 30.
        CountryFuelYear.objects.create(
            country=self.country,
            fuel=self.fuel_coal,
            year=2024,
            is_complete=True,
            share=70.0,
            generation=70.0,
            yoy_growth=0.0,
        )
        CountryFuelYear.objects.create(
            country=self.country,
            fuel=self.fuel_hydro,
            year=2024,
            is_complete=True,
            share=30.0,
            generation=30.0,
            yoy_growth=0.0,
        )

        MonthlyGenerationData.objects.bulk_create(
            [
                MonthlyGenerationData(
                    country=self.country.name,
                    country_code=self.country.code,
                    is_aggregate_entity=False,
                    date=date(2024, 1, 1),
                    fuel_type="Coal",
                    is_aggregate_series=False,
                    generation_twh=10.0,
                    share_of_generation_pct=0.0,
                ),
                MonthlyGenerationData(
                    country=self.country.name,
                    country_code=self.country.code,
                    is_aggregate_entity=False,
                    date=date(2024, 2, 1),
                    fuel_type="Coal",
                    is_aggregate_series=False,
                    generation_twh=15.0,
                    share_of_generation_pct=0.0,
                ),
                MonthlyGenerationData(
                    country=self.country.name,
                    country_code=self.country.code,
                    is_aggregate_entity=False,
                    date=date(2024, 1, 1),
                    fuel_type="Hydro",
                    is_aggregate_series=False,
                    generation_twh=5.0,
                    share_of_generation_pct=0.0,
                ),
                MonthlyGenerationData(
                    country=self.country.name,
                    country_code=self.country.code,
                    is_aggregate_entity=False,
                    date=date(2024, 2, 1),
                    fuel_type="Hydro",
                    is_aggregate_series=False,
                    generation_twh=7.0,
                    share_of_generation_pct=0.0,
                ),
                # Should be excluded from annual totals (aggregate series)
                MonthlyGenerationData(
                    country=self.country.name,
                    country_code=self.country.code,
                    is_aggregate_entity=False,
                    date=date(2024, 1, 1),
                    fuel_type="Renewables",
                    is_aggregate_series=True,
                    generation_twh=999.0,
                    share_of_generation_pct=0.0,
                ),
            ]
        )

        upserts = backfill_country_tracker_years(country_codes=[self.country.code])
        self.assertEqual(upserts, 1)

        tracker = CountryTrackerYear.objects.get(country=self.country, year=2024)
        self.assertEqual(tracker.electricity_rank, 1)
        self.assertAlmostEqual(tracker.electricity_share_low_carbon, 30.0, places=6)  # 30 / (70+30) * 100
        self.assertEqual(tracker.share_electricity, 30.0)
        self.assertEqual(tracker.energy_share_low_carbon, 40.0)
        self.assertAlmostEqual(tracker.generation_twh, 37.0, places=6)  # 10+15+5+7, aggregate excluded

    def test_backfill_energy_present_but_no_monthly_for_year(self):
        """
        When energy + fuel-year inputs exist but monthly generation does not,
        tracker rows are still created and generation_twh remains NULL.
        """
        CountryEnergyBalanceYear.objects.create(
            country=self.country,
            year=2024,
            coal_supply=1,
            oil_supply=1,
            gas_supply=1,
            nuclear_supply=1,
            renewable_supply=1,
            total_supply=5,
            share_low_carbon=10.0,
            share_renewable=5.0,
            share_electricity=25.0,
        )
        CountryFuelYear.objects.create(
            country=self.country,
            fuel=self.fuel_coal,
            year=2024,
            is_complete=True,
            share=100.0,
            generation=50.0,
            yoy_growth=0.0,
        )

        upserts = backfill_country_tracker_years(country_codes=[self.country.code])
        self.assertEqual(upserts, 1)

        tracker = CountryTrackerYear.objects.get(country=self.country, year=2024)
        self.assertIsNone(tracker.generation_twh)

    def test_backfill_monthly_present_but_no_energy_for_year(self):
        """
        If MonthlyGenerationData exists but there is no CountryEnergyBalanceYear row,
        no CountryTrackerYear row should be created for that year (command keys off energy rows).
        """
        # Fuel-year data exists for ranking (doesn't matter without energy row)
        CountryFuelYear.objects.create(
            country=self.country,
            fuel=self.fuel_coal,
            year=2024,
            is_complete=True,
            share=100.0,
            generation=50.0,
            yoy_growth=0.0,
        )
        MonthlyGenerationData.objects.create(
            country=self.country.name,
            country_code=self.country.code,
            is_aggregate_entity=False,
            date=date(2024, 1, 1),
            fuel_type="Coal",
            is_aggregate_series=False,
            generation_twh=12.0,
            share_of_generation_pct=0.0,
        )

        upserts = backfill_country_tracker_years(country_codes=[self.country.code])
        self.assertEqual(upserts, 0)
        self.assertFalse(CountryTrackerYear.objects.filter(country=self.country, year=2024).exists())

    def test_low_carbon_share_excludes_net_imports_from_denominator(self):
        """
        Ember fuel-year data includes a "Net imports" series which can be negative.
        It should not be included in the total-generation denominator; otherwise shares
        can exceed 100%.
        """
        CountryEnergyBalanceYear.objects.create(
            country=self.country,
            year=2024,
            coal_supply=1,
            oil_supply=1,
            gas_supply=1,
            nuclear_supply=1,
            renewable_supply=1,
            total_supply=5,
            share_low_carbon=40.0,
            share_renewable=20.0,
            share_electricity=30.0,
        )

        # Domestic generation: Coal=70, Hydro=30 => low-carbon share should be 30%.
        CountryFuelYear.objects.create(
            country=self.country,
            fuel=self.fuel_coal,
            year=2024,
            is_complete=True,
            share=70.0,
            generation=70.0,
            yoy_growth=0.0,
        )
        CountryFuelYear.objects.create(
            country=self.country,
            fuel=self.fuel_hydro,
            year=2024,
            is_complete=True,
            share=30.0,
            generation=30.0,
            yoy_growth=0.0,
        )
        # If included, this would inflate the low-carbon share above 30%.
        CountryFuelYear.objects.create(
            country=self.country,
            fuel=self.fuel_net_imports,
            year=2024,
            is_complete=True,
            share=-20.0,
            generation=-20.0,
            yoy_growth=0.0,
        )

        upserts = backfill_country_tracker_years(country_codes=[self.country.code])
        self.assertEqual(upserts, 1)

        tracker = CountryTrackerYear.objects.get(country=self.country, year=2024)
        self.assertAlmostEqual(tracker.electricity_share_low_carbon, 30.0, places=6)
