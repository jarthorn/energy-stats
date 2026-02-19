from datetime import date
from django.test import TestCase
from core.models import Country, CountryFuel, Fuel


class CountryFuelModelTests(TestCase):
    def setUp(self):
        self.country = Country.objects.create(
            name="France",
            code="FRA",
            summary="France generates the majority of its electricity from nuclear power.",
            electricity_rank=7,
            generation_latest_12_months=445.0,
            generation_previous_12_months=451.2,
        )
        self.fuel = Fuel.objects.create(
            type="Nuclear",
            rank=2,
            summary="Nuclear power produces electricity through nuclear fission.",
        )

    def test_create_country_fuel(self):
        """A CountryFuel can be created and its fields retrieved correctly."""
        cf = CountryFuel.objects.create(
            country=self.country,
            fuel=self.fuel,
            share=70.5,
            latest_month=date(2024, 12, 1),
            generation_latest_12_months=313.7,
            generation_previous_12_months=320.4,
        )
        self.assertEqual(cf.country, self.country)
        self.assertEqual(cf.fuel, self.fuel)
        self.assertEqual(cf.share, 70.5)
        self.assertEqual(cf.latest_month, date(2024, 12, 1))
        self.assertEqual(cf.generation_latest_12_months, 313.7)
        self.assertEqual(cf.generation_previous_12_months, 320.4)
        self.assertEqual(str(cf), "France (FRA) - Nuclear")

    def test_country_fuel_pair_is_unique(self):
        """The same country/fuel combination cannot appear more than once."""
        CountryFuel.objects.create(
            country=self.country,
            fuel=self.fuel,
            share=70.5,
            latest_month=date(2024, 12, 1),
            generation_latest_12_months=313.7,
            generation_previous_12_months=320.4,
        )
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            CountryFuel.objects.create(
                country=self.country,
                fuel=self.fuel,
                share=50.0,
                latest_month=date(2024, 12, 1),
                generation_latest_12_months=200.0,
                generation_previous_12_months=210.0,
            )
