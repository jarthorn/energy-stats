from datetime import date, datetime
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from core.models import FuelMonth, MonthlyGenerationData


class FuelMonthTransformTests(TestCase):
    def setUp(self):
        # Boundary fixture for the cutoff:
        # - cutoff is Jan 1, (current year - 3)
        # - with "today" fixed at 2026-05-04, cutoff is 2023-01-01
        # - staging includes 2022-01..2024-12; we should only persist 2023+ into FuelMonth
        self.country_code = "FRA"
        self.country_name = "France"
        self.fuel_type = "Nuclear"

        records = []
        for year in [2022, 2023, 2024]:
            for month in range(1, 13):
                records.append(
                    MonthlyGenerationData(
                        country=self.country_name,
                        country_code=self.country_code,
                        date=date(year, month, 1),
                        fuel_type=self.fuel_type,
                        is_aggregate_entity=False,
                        is_aggregate_series=False,
                        generation_twh=10.0,
                        share_of_generation_pct=70.0,
                    )
                )

        MonthlyGenerationData.objects.bulk_create(records)

    def test_fuel_month_backfill_respects_three_year_cutoff(self):
        fixed_now = timezone.make_aware(datetime(2026, 5, 4, 12, 0, 0))
        with patch("core.management.commands.transform_and_load.timezone.now", return_value=fixed_now):
            call_command("transform_and_load", country=[self.country_code])

        # Exclude 2022 and earlier
        self.assertFalse(FuelMonth.objects.filter(month__year=2022).exists())

        # Include 2023-01..2024-12 => 24 months for this fuel
        self.assertEqual(FuelMonth.objects.filter(fuel__type=self.fuel_type).count(), 24)

        jan_2023 = FuelMonth.objects.get(fuel__type=self.fuel_type, month=date(2023, 1, 1))
        self.assertEqual(jan_2023.generation, 10.0)
        self.assertEqual(jan_2023.share, 100.0)
