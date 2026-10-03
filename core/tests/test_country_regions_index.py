from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import Country, Fuel, GenerationUnitRegionFuelYear, GenerationUnitRegionYear
from core.templatetags.core_extras import region_display_name, region_term


@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
)
class CountryRegionsIndexTests(TestCase):
    def setUp(self):
        self.country = Country.objects.create(
            name="Canada",
            code="CAN",
            summary="Canada summary",
            electricity_rank=1,
            generation_latest_12_months=100.0,
            generation_previous_12_months=90.0,
        )
        self.other_country = Country.objects.create(
            name="Testland",
            code="TST",
            summary="No region data",
            electricity_rank=2,
            generation_latest_12_months=1.0,
            generation_previous_12_months=1.0,
        )
        self.solar = Fuel.objects.create(type="Solar", rank=1, summary="Solar")
        self.hydro = Fuel.objects.create(type="Hydro", rank=2, summary="Hydro")

    def test_regions_index_shows_table_with_top_fuel(self):
        GenerationUnitRegionYear.objects.create(
            country=self.country,
            region="AB",
            year=2025,
            effective_capacity_mw=18.0,
            average_annual_energy_gwh=38.0,
        )
        GenerationUnitRegionFuelYear.objects.create(
            country=self.country,
            region="AB",
            fuel=self.solar,
            year=2025,
            effective_capacity_mw=15.0,
            average_annual_energy_gwh=30.0,
        )
        GenerationUnitRegionFuelYear.objects.create(
            country=self.country,
            region="AB",
            fuel=self.hydro,
            year=2025,
            effective_capacity_mw=3.0,
            average_annual_energy_gwh=8.0,
        )

        response = self.client.get(reverse("country_regions_index", args=["CAN"]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Alberta")
        self.assertContains(response, "Provinces")
        self.assertContains(response, "Provincial")
        self.assertContains(response, "Solar")
        self.assertNotContains(response, "not available")

    def test_regions_index_shows_banner_when_no_data(self):
        response = self.client.get(reverse("country_regions_index", args=["TST"]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Regional generation unit data is not available for Testland.")
        self.assertNotContains(response, "<table")

    def test_top_fuel_uses_average_annual_energy(self):
        GenerationUnitRegionYear.objects.create(
            country=self.country,
            region="BC",
            year=2025,
            effective_capacity_mw=10.0,
            average_annual_energy_gwh=20.0,
        )
        GenerationUnitRegionFuelYear.objects.create(
            country=self.country,
            region="BC",
            fuel=self.solar,
            year=2025,
            effective_capacity_mw=9.0,
            average_annual_energy_gwh=5.0,
        )
        GenerationUnitRegionFuelYear.objects.create(
            country=self.country,
            region="BC",
            fuel=self.hydro,
            year=2025,
            effective_capacity_mw=1.0,
            average_annual_energy_gwh=15.0,
        )

        response = self.client.get(reverse("country_regions_index", args=["CAN"]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "British Columbia")
        self.assertContains(response, "Hydro")
        self.assertNotContains(response, "Solar")

    def test_region_display_name_maps_canadian_provinces(self):
        self.assertEqual(region_display_name("QC", self.country), "Quebec")
        self.assertEqual(region_display_name("XX", self.country), "XX")
        self.assertEqual(region_display_name("AB", self.other_country), "AB")

    def test_region_term_uses_province_wording_for_canada(self):
        self.assertEqual(region_term(self.country, "Regions"), "Provinces")
        self.assertEqual(region_term(self.country, "Regional"), "Provincial")
        self.assertEqual(region_term(self.country, "region"), "province")
        self.assertEqual(region_term(self.other_country, "Regions"), "Regions")
        self.assertEqual(region_term(self.other_country, "regional"), "regional")

    def test_region_detail_lists_fuels_sorted_by_average_annual_energy(self):
        GenerationUnitRegionYear.objects.create(
            country=self.country,
            region="AB",
            year=2025,
            effective_capacity_mw=18.0,
            average_annual_energy_gwh=38.0,
        )
        GenerationUnitRegionFuelYear.objects.create(
            country=self.country,
            region="AB",
            fuel=self.solar,
            year=2025,
            effective_capacity_mw=15.0,
            average_annual_energy_gwh=30.0,
        )
        GenerationUnitRegionFuelYear.objects.create(
            country=self.country,
            region="AB",
            fuel=self.hydro,
            year=2025,
            effective_capacity_mw=3.0,
            average_annual_energy_gwh=8.0,
        )

        response = self.client.get(reverse("country_region_detail", args=["CAN", "AB"]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Alberta")
        self.assertContains(response, "18")
        self.assertContains(response, "38")
        content = response.content.decode()
        self.assertLess(content.index("Solar"), content.index("Hydro"))

    def test_region_detail_returns_404_when_missing(self):
        response = self.client.get(reverse("country_region_detail", args=["CAN", "AB"]))
        self.assertEqual(response.status_code, 404)
