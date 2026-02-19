from django.test import TestCase
from core.models import Country


class CountryModelTests(TestCase):
    def test_create_country(self):
        """A Country can be created and its fields retrieved correctly."""
        country = Country.objects.create(
            name="Germany",
            code="DEU",
            summary="Germany has a diverse electricity mix with significant renewable capacity.",
            electricity_rank=5,
            generation_latest_12_months=542.3,
            generation_previous_12_months=558.1,
        )
        self.assertEqual(country.name, "Germany")
        self.assertEqual(country.code, "DEU")
        self.assertEqual(country.electricity_rank, 5)
        self.assertEqual(country.generation_latest_12_months, 542.3)
        self.assertEqual(country.generation_previous_12_months, 558.1)
        self.assertEqual(str(country), "Germany (DEU)")

    def test_country_code_is_unique(self):
        """Two countries cannot share the same ISO code."""
        Country.objects.create(
            name="Germany",
            code="DEU",
            summary="Summary.",
            electricity_rank=5,
            generation_latest_12_months=542.3,
            generation_previous_12_months=558.1,
        )
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            Country.objects.create(
                name="Duplicate",
                code="DEU",
                summary="Duplicate summary.",
                electricity_rank=99,
                generation_latest_12_months=1.0,
                generation_previous_12_months=1.0,
            )
