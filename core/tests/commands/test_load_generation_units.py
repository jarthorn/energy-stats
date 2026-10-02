from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from core.models import Country, Fuel, GenerationUnit, GenerationUnitRegionFuelYear


class LoadGenerationUnitsCommandTests(TestCase):
    def setUp(self):
        self.country = Country.objects.create(
            name="Canada",
            code="CAN",
            summary="Canada summary",
            electricity_rank=1,
            generation_latest_12_months=0.0,
            generation_previous_12_months=0.0,
        )
        self.solar = Fuel.objects.create(type="Solar", rank=1, summary="Solar")
        self.hydro = Fuel.objects.create(type="Hydro", rank=2, summary="Hydro")
        self.other_fossil = Fuel.objects.create(type="Other fossil", rank=3, summary="Other fossil")

    def test_load_generation_units_replaces_snapshot_for_year(self):
        GenerationUnit.objects.create(
            country=self.country,
            region="AB",
            fuel=self.solar,
            year=2025,
            generation_unit_name="Old Unit",
            unit_effective_capacity_mw=1.0,
            unit_average_annual_energy_gwh=2.0,
        )
        GenerationUnitRegionFuelYear.objects.create(
            country=self.country,
            region="AB",
            fuel=self.solar,
            year=2025,
            effective_capacity_mw=1.0,
            average_annual_energy_gwh=2.0,
        )

        api_payload = [
            {
                "generation_unit_name": "Big Sky",
                "province": "AB",
                "gen_type": "solar_PV",
                "unit_effective_capacity": "10.5",
                "unit_average_annual_energy": "20.25",
            },
            {
                "generation_unit_name": "Prairie Solar",
                "province": "AB",
                "gen_type": "solar_PV",
                "unit_effective_capacity": "4.5",
                "unit_average_annual_energy": "9.75",
            },
            {
                "generation_unit_name": "River Run",
                "province": "BC",
                "gen_type": "hydro_run",
                "unit_effective_capacity": 5,
                "unit_average_annual_energy": 12.5,
            },
            {
                # Missing province — should be skipped
                "generation_unit_name": "Incomplete",
                "province": "",
                "gen_type": "solar_PV",
                "unit_effective_capacity": "1",
                "unit_average_annual_energy": "1",
            },
        ]

        with patch("energystats.tasks.load_coders.requests.get") as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.raise_for_status = lambda: None
            mock_get.return_value.json.return_value = api_payload

            with patch.dict("os.environ", {"CODERS_API_KEY": "test-key"}):
                call_command("load_generation_units", year=2025)

        units = list(GenerationUnit.objects.filter(country=self.country, year=2025).order_by("generation_unit_name"))
        self.assertEqual(len(units), 3)
        self.assertFalse(GenerationUnit.objects.filter(generation_unit_name="Old Unit").exists())

        big_sky = units[0]
        self.assertEqual(big_sky.generation_unit_name, "Big Sky")
        self.assertEqual(big_sky.region, "AB")
        self.assertEqual(big_sky.fuel, self.solar)
        self.assertEqual(big_sky.unit_effective_capacity_mw, 10.5)
        self.assertEqual(big_sky.unit_average_annual_energy_gwh, 20.25)

        river = units[2]
        self.assertEqual(river.generation_unit_name, "River Run")
        self.assertEqual(river.fuel, self.hydro)

        aggregates = list(
            GenerationUnitRegionFuelYear.objects.filter(country=self.country, year=2025).order_by(
                "region", "fuel__type"
            )
        )
        self.assertEqual(len(aggregates), 2)

        ab_solar = aggregates[0]
        self.assertEqual(ab_solar.region, "AB")
        self.assertEqual(ab_solar.fuel, self.solar)
        self.assertEqual(ab_solar.effective_capacity_mw, 15.0)
        self.assertEqual(ab_solar.average_annual_energy_gwh, 30.0)

        bc_hydro = aggregates[1]
        self.assertEqual(bc_hydro.region, "BC")
        self.assertEqual(bc_hydro.fuel, self.hydro)
        self.assertEqual(bc_hydro.effective_capacity_mw, 5.0)
        self.assertEqual(bc_hydro.average_annual_energy_gwh, 12.5)

    def test_oil_gen_types_map_to_other_fossil(self):
        api_payload = [
            {
                "generation_unit_name": "Diesel Peak",
                "province": "NT",
                "gen_type": "diesel_CT",
                "unit_effective_capacity": "2.0",
                "unit_average_annual_energy": "3.0",
            },
            {
                "generation_unit_name": "Oil Steam",
                "province": "NS",
                "gen_type": "oil_ST",
                "unit_effective_capacity": "4.0",
                "unit_average_annual_energy": "5.0",
            },
        ]

        with patch("energystats.tasks.load_coders.requests.get") as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.raise_for_status = lambda: None
            mock_get.return_value.json.return_value = api_payload

            with patch.dict("os.environ", {"CODERS_API_KEY": "test-key"}):
                call_command("load_generation_units", year=2025)

        units = list(GenerationUnit.objects.filter(country=self.country, year=2025).order_by("generation_unit_name"))
        self.assertEqual(len(units), 2)
        self.assertEqual(units[0].fuel, self.other_fossil)
        self.assertEqual(units[1].fuel, self.other_fossil)

    def test_load_generation_units_requires_api_key(self):
        with patch("energystats.tasks.load_coders.load_dotenv"):
            with patch.dict("os.environ", {"CODERS_API_KEY": ""}, clear=False):
                with self.assertRaises(CommandError) as ctx:
                    call_command("load_generation_units")
        self.assertIn("CODERS_API_KEY", str(ctx.exception))
