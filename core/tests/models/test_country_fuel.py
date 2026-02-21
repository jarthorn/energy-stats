from datetime import date
from django.test import TestCase
from django.core.management import call_command
from core.models import Country, CountryFuel, Fuel, MonthlyGenerationData


class CountryFuelTransformTests(TestCase):
    def setUp(self):
        # We'll use MonthlyGenerationData as the staging table for transform_and_load
        self.country_code = "FRA"
        self.country_name = "France"
        self.fuel_type = "Nuclear"

        # Create 24 months of data to test annual and monthly YoY calculations
        # previous 12 months: 2023-01 to 2023-12
        # latest 12 months: 2024-01 to 2024-12

        records = []
        for year in [2023, 2024]:
            for month in range(1, 13):
                # We'll set generation to 1 per month for 2023 and 10.0 for 2024
                gen = month if year == 2023 else 10.0

                records.append(MonthlyGenerationData(
                    country=self.country_name,
                    country_code=self.country_code,
                    date=date(year, month, 1),
                    fuel_type=self.fuel_type,
                    is_aggregate_entity=False,
                    is_aggregate_series=False,
                    generation_twh=gen,
                    share_of_generation_pct=70.0
                ))

        MonthlyGenerationData.objects.bulk_create(records)

    def test_transform_and_load_growth_calculations(self):
        """
        The transform_and_load command should calculate YoY growth metrics correctly
        from the staging data.
        """
        # Run the ETL command
        call_command('transform_and_load', country=[self.country_code])

        # Check that Country and Fuel objects were created/updated
        self.assertTrue(Country.objects.filter(code=self.country_code).exists())
        self.assertTrue(Fuel.objects.filter(type=self.fuel_type).exists())

        # Verify CountryFuel stats
        cf = CountryFuel.objects.get(
            country__code=self.country_code,
            fuel__type=self.fuel_type
        )

        # Latest 12 months (2024): 12 months * 10.0 = 120.0
        # Previous 12 months (2023): Sum(1-12) = 78.0
        # Annual YoY Growth: ((120 / 78) - 1) * 100 = 53.85%
        self.assertEqual(cf.generation_latest_12_months, 120.0)
        self.assertEqual(cf.generation_previous_12_months, 78.0)
        self.assertAlmostEqual(cf.annual_yoy_growth, 53.8461538)

        # Latest month (2024-12): 10.0
        # Previous year same month (2023-12): 12
        # Month YoY Growth: ((10.0 / 12) - 1) * 100 = -16.67%
        self.assertEqual(cf.latest_month, date(2024, 12, 1))
        self.assertAlmostEqual(cf.month_yoy_growth, -16.66666667)
        self.assertEqual(cf.generation_latest_month, 10.0)
        self.assertEqual(cf.share_latest_month, 70.0)

    def test_country_fuel_pair_is_unique(self):
        """The transform_and_load command stays idempotent and unique constraints hold."""
        # Running it twice should not create duplicate CountryFuel records
        call_command('transform_and_load', country=[self.country_code])
        call_command('transform_and_load', country=[self.country_code])

        count = CountryFuel.objects.filter(
            country__code=self.country_code,
            fuel__type=self.fuel_type
        ).count()
        self.assertEqual(count, 1)
