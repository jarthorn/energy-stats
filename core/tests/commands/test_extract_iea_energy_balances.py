"""
Tests for extract_iea_energy_balances management command.
"""

from django.conf import settings
from django.core.management import call_command
from django.test import TestCase

from core.models import Country, CountryEnergyBalanceYear

class ExtractIeaEnergyBalancesCommandTests(TestCase):
    """Backfill CountryEnergyBalanceYear from IEA CSV (Canada fixture)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.fixture_path = settings.BASE_DIR / "data" / "iea-test-energy-balances-2025.csv"
        if not cls.fixture_path.is_file():
            raise AssertionError(f"Missing test fixture: {cls.fixture_path}")

    def setUp(self):
        self.canada = Country.objects.create(
            name="Canada",
            code="CAN",
            summary="Canada test country for IEA energy balance extraction.",
            electricity_rank=1,
            generation_latest_12_months=0.0,
            generation_previous_12_months=0.0,
        )

    def test_extract_iea_energy_balances_canada_matches_fixture(self):

        call_command("extract_iea_energy_balances", file=str(self.fixture_path))

        stored = {
            row.year: row for row in CountryEnergyBalanceYear.objects.filter(country=self.canada).order_by("year")
        }
        # Expect 25 years
        self.assertEqual(set(stored.keys()), set(range(2000, 2025)))

        # Spot-check literals from the fixture 
        self.assertEqual(stored[2000].coal_supply, 1327)
        self.assertEqual(stored[2000].oil_supply, 4048)

        # 2024 has no electricity data so we test 2023 instead
        self.assertAlmostEqual(stored[2023].share_electricity, 17.31, places=2)

        coal_2024 = 375
        oil_2024 = 4838
        gas_2024 = 4977
        nuclear_2024 = 939
        renewable_2024 = 2010
        total_2024 = coal_2024 + oil_2024 + gas_2024 + nuclear_2024 + renewable_2024

        self.assertEqual(stored[2024].coal_supply, coal_2024)
        self.assertEqual(stored[2024].oil_supply, oil_2024)
        self.assertEqual(stored[2024].gas_supply, gas_2024)
        self.assertEqual(stored[2024].nuclear_supply, nuclear_2024)
        self.assertEqual(stored[2024].renewable_supply, renewable_2024)

        self.assertEqual(stored[2024].total_supply, total_2024)
        self.assertEqual(stored[2024].share_electricity, 0.0)
        self.assertEqual(stored[2024].share_low_carbon, (nuclear_2024 + renewable_2024) / total_2024 * 100.0)
        self.assertEqual(stored[2024].share_renewable, renewable_2024 / total_2024 * 100.0)
