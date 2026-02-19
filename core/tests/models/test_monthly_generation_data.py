from django.test import TestCase
from datetime import date
from core.models import MonthlyGenerationData
from core.country_codes import CountryCode


class MonthlyGenerationDataModelTests(TestCase):
    def test_create_monthly_generation_data(self):
        """A MonthlyGenerationData record can be created and retrieved."""
        data = MonthlyGenerationData.objects.create(
            country="United States",
            country_code=CountryCode.USA,
            is_aggregate_entity=False,
            date=date(2023, 1, 1),
            fuel_type="Solar",
            is_aggregate_series=False,
            generation_twh=10.5,
            share_of_generation_pct=5.2,
        )
        self.assertEqual(data.country, "United States")
        self.assertEqual(data.generation_twh, 10.5)
        self.assertEqual(str(data), "United States - Solar (2023-01-01)")
