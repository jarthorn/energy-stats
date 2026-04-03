from datetime import date

from django.core.management import call_command
from django.test import TestCase

from core.models import Country, MonthlyGenerationData, MonthlyGenerationRecord, Fuel


class LoadMonthlyRecordsCommandTests(TestCase):
    def setUp(self):
        # Create a single country
        self.country = Country.objects.create(
            name="Testland",
            code="TST",
            summary="Test country for monthly record backfill.",
            electricity_rank=1,
            generation_latest_12_months=0.0,
            generation_previous_12_months=0.0,
        )

        # Three fuel types with non-monotonic values across 12 months
        fuel_series = {
            "Coal": {
                "generation": [5, 3, 6, 4, 7, 2, 8, 7, 9, 6, 10, 9],
                "share": [10, 9, 11, 8, 12, 7, 13, 12, 14, 10, 15, 14],
            },
            "Wind": {
                "generation": [1, 2, 1.5, 3, 2.5, 4, 3.5, 5, 4.5, 6, 5.5, 7],
                "share": [2, 1.5, 2.5, 2, 3, 2.8, 3.2, 3.1, 3.5, 3.4, 3.8, 4],
            },
            "Solar": {
                "generation": [0.5, 0.7, 0.6, 0.9, 0.8, 1.1, 1.0, 1.3, 1.2, 1.5, 1.4, 1.6],
                "share": [1, 1.2, 1.1, 1.4, 1.3, 1.6, 1.5, 1.8, 1.7, 2.0, 1.9, 2.1],
            },
        }

        records = []
        year = 2024
        for month_index in range(12):
            month = month_index + 1
            for fuel_type, series in fuel_series.items():
                records.append(
                    MonthlyGenerationData(
                        country=self.country.name,
                        country_code=self.country.code,
                        is_aggregate_entity=False,
                        date=date(year, month, 1),
                        fuel_type=fuel_type,
                        is_aggregate_series=False,
                        generation_twh=series["generation"][month_index],
                        share_of_generation_pct=series["share"][month_index],
                    )
                )

        MonthlyGenerationData.objects.bulk_create(records)

    def test_load_monthly_records_creates_expected_records(self):
        """
        Running load_monthly_records should create record rows whenever
        generation or share hit a new maximum for a (country, fuel) pair.
        """
        # Sanity check: we created 12 * 3 = 36 MonthlyGenerationData rows
        self.assertEqual(
            MonthlyGenerationData.objects.filter(country_code=self.country.code).count(),
            36,
        )

        # Run the backfill command for our test country only
        call_command("load_monthly_records", country=[self.country.code])

        # For each fuel, the series are mostly increasing but not strictly monotonic.
        # Count the expected number of "generation" and "share" records by simulating
        # the same logic used in the management command.
        expected_records = 0
        fuel_types = ["Coal", "Wind", "Solar"]
        for fuel in fuel_types:
            fuel_rows = MonthlyGenerationData.objects.filter(
                country_code=self.country.code,
                fuel_type=fuel,
                is_aggregate_entity=False,
                is_aggregate_series=False,
            ).order_by("date")

            max_generation = None
            max_share = None

            for row in fuel_rows:
                gen = row.generation_twh
                share = row.share_of_generation_pct

                if max_generation is None or gen > max_generation:
                    max_generation = gen
                    expected_records += 1

                if max_share is None or share > max_share:
                    max_share = share
                    expected_records += 1

        # Assert that the command created exactly the number of records we expect
        created_records = MonthlyGenerationRecord.objects.filter(country=self.country).count()
        self.assertEqual(created_records, expected_records)
        fuel_generation_records = MonthlyGenerationRecord.objects.filter(
            country=self.country, fuel=Fuel.objects.get(type="Coal"), record_type="generation"
        )
        self.assertEqual(6, fuel_generation_records.count())
        wind_share_records = MonthlyGenerationRecord.objects.filter(
            country=self.country, fuel=Fuel.objects.get(type="Wind"), record_type="share"
        )
        self.assertEqual(7, wind_share_records.count())
