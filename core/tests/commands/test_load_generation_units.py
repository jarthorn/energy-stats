from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from core.models import (
    Country,
    Fuel,
    GenerationUnit,
    GenerationUnitRegionFuelYear,
    GenerationUnitRegionYear,
)


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
        GenerationUnitRegionYear.objects.create(
            country=self.country,
            region="AB",
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
                "generation_unit_name": "Bow Falls",
                "province": "AB",
                "gen_type": "hydro_run",
                "unit_effective_capacity": "3.0",
                "unit_average_annual_energy": "8.0",
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
        self.assertEqual(len(units), 4)
        self.assertFalse(GenerationUnit.objects.filter(generation_unit_name="Old Unit").exists())

        big_sky = units[0]
        self.assertEqual(big_sky.generation_unit_name, "Big Sky")
        self.assertEqual(big_sky.region, "AB")
        self.assertEqual(big_sky.fuel, self.solar)
        self.assertEqual(big_sky.unit_effective_capacity_mw, 10.5)
        self.assertEqual(big_sky.unit_average_annual_energy_gwh, 20.25)

        river = units[3]
        self.assertEqual(river.generation_unit_name, "River Run")
        self.assertEqual(river.fuel, self.hydro)

        fuel_aggregates = list(
            GenerationUnitRegionFuelYear.objects.filter(country=self.country, year=2025).order_by(
                "region", "fuel__type"
            )
        )
        self.assertEqual(len(fuel_aggregates), 3)

        ab_hydro = fuel_aggregates[0]
        self.assertEqual(ab_hydro.region, "AB")
        self.assertEqual(ab_hydro.fuel, self.hydro)
        self.assertEqual(ab_hydro.effective_capacity_mw, 3.0)
        self.assertEqual(ab_hydro.average_annual_energy_gwh, 8.0)

        ab_solar = fuel_aggregates[1]
        self.assertEqual(ab_solar.region, "AB")
        self.assertEqual(ab_solar.fuel, self.solar)
        self.assertEqual(ab_solar.effective_capacity_mw, 15.0)
        self.assertEqual(ab_solar.average_annual_energy_gwh, 30.0)

        bc_hydro = fuel_aggregates[2]
        self.assertEqual(bc_hydro.region, "BC")
        self.assertEqual(bc_hydro.fuel, self.hydro)
        self.assertEqual(bc_hydro.effective_capacity_mw, 5.0)
        self.assertEqual(bc_hydro.average_annual_energy_gwh, 12.5)

        region_aggregates = list(
            GenerationUnitRegionYear.objects.filter(country=self.country, year=2025).order_by("region")
        )
        self.assertEqual(len(region_aggregates), 2)

        ab_total = region_aggregates[0]
        self.assertEqual(ab_total.region, "AB")
        self.assertEqual(ab_total.effective_capacity_mw, 18.0)
        self.assertEqual(ab_total.average_annual_energy_gwh, 38.0)

        bc_total = region_aggregates[1]
        self.assertEqual(bc_total.region, "BC")
        self.assertEqual(bc_total.effective_capacity_mw, 5.0)
        self.assertEqual(bc_total.average_annual_energy_gwh, 12.5)

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
