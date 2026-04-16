from __future__ import annotations

from collections.abc import Iterable

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import F, FloatField, Sum
from django.db.models.expressions import ExpressionWrapper

from core.models import (
    Country,
    CountryEnergyBalanceYear,
    CountryFuelYear,
    CountryTrackerYear,
    MonthlyGenerationData,
    TrackerYear,
)

LOW_CARBON_ELECTRICITY_FUELS = {
    "Hydro",
    "Nuclear",
    "Wind",
    "Solar",
    "Bioenergy",
    "Other renewables",
}


def backfill_tracker_years(*, stdout=None) -> int:
    """
    Create or update TrackerYear rows (global aggregates) for all available years.

    Weighting rules:
    - electricity_share_low_carbon is weighted by CountryTrackerYear.generation_twh
    - share_electricity and energy_share_low_carbon are weighted by CountryEnergyBalanceYear.total_supply
    """

    gen_weighted = list(
        CountryTrackerYear.objects.filter(generation_twh__gt=0)
        .values("year")
        .annotate(
            generation_twh_sum=Sum("generation_twh"),
            electricity_share_low_carbon_weighted=Sum(
                ExpressionWrapper(
                    F("electricity_share_low_carbon") * F("generation_twh"),
                    output_field=FloatField(),
                )
            ),
        )
    )
    gen_by_year = {r["year"]: r for r in gen_weighted}

    supply_weighted = list(
        CountryEnergyBalanceYear.objects.filter(total_supply__gt=0)
        .values("year")
        .annotate(
            total_supply_sum=Sum("total_supply"),
            share_electricity_weighted=Sum(
                ExpressionWrapper(
                    F("share_electricity") * F("total_supply"),
                    output_field=FloatField(),
                )
            ),
            energy_share_low_carbon_weighted=Sum(
                ExpressionWrapper(
                    F("share_low_carbon") * F("total_supply"),
                    output_field=FloatField(),
                )
            ),
        )
    )
    supply_by_year = {r["year"]: r for r in supply_weighted}

    years = sorted(set(gen_by_year.keys()) | set(supply_by_year.keys()))
    if not years:
        return 0

    if stdout is not None:
        stdout.write(f"Backfilling TrackerYear for {len(years)} year(s)...")

    upserts = 0
    with transaction.atomic():
        for year in years:
            gen_row = gen_by_year.get(year)
            supply_row = supply_by_year.get(year)

            generation_twh = gen_row["generation_twh_sum"] if gen_row else None
            total_supply = supply_row["total_supply_sum"] if supply_row else None

            electricity_share_low_carbon = 0.0
            if gen_row and generation_twh and generation_twh > 0:
                electricity_share_low_carbon = (
                    gen_row["electricity_share_low_carbon_weighted"] or 0.0
                ) / generation_twh

            share_electricity = 0.0
            energy_share_low_carbon = 0.0
            if supply_row and total_supply and total_supply > 0:
                share_electricity = (supply_row["share_electricity_weighted"] or 0.0) / total_supply
                energy_share_low_carbon = (supply_row["energy_share_low_carbon_weighted"] or 0.0) / total_supply

            TrackerYear.objects.update_or_create(
                year=year,
                defaults={
                    "generation_twh": generation_twh,
                    "electricity_share_low_carbon": electricity_share_low_carbon,
                    "share_electricity": share_electricity,
                    "energy_share_low_carbon": energy_share_low_carbon,
                },
            )
            upserts += 1

    return upserts


def backfill_country_tracker_years(*, country_codes: Iterable[str] | None = None, stdout=None) -> int:
    """
    Create or update CountryTrackerYear rows for all available calendar years.

    - energy_share_low_carbon and share_electricity come from CountryEnergyBalanceYear
    - electricity_rank and electricity_share_low_carbon are derived from CountryFuelYear
      (aggregated across fuel types for each country+year)

    Returns the number of CountryTrackerYear rows upserted.
    """

    countries_qs = Country.objects.all()
    if country_codes is not None:
        normalized = [c.strip().upper() for c in country_codes if c and c.strip()]
        countries_qs = countries_qs.filter(code__in=normalized)

    countries = list(countries_qs.values("id", "code"))
    country_ids = [c["id"] for c in countries]
    if not country_ids:
        return 0
    country_id_by_code = {c["code"]: c["id"] for c in countries}

    energy_rows = list(
        CountryEnergyBalanceYear.objects.filter(country_id__in=country_ids).values(
            "country_id",
            "year",
            "share_low_carbon",
            "share_electricity",
        )
    )
    energy_by_key = {(r["country_id"], r["year"]): r for r in energy_rows}

    totals_rows = list(
        CountryFuelYear.objects.filter(country_id__in=country_ids)
        .values("country_id", "year")
        .annotate(total_generation=Sum("generation"))
    )
    totals_by_key = {(r["country_id"], r["year"]): (r["total_generation"] or 0.0) for r in totals_rows}

    low_carbon_rows = list(
        CountryFuelYear.objects.filter(country_id__in=country_ids, fuel__type__in=LOW_CARBON_ELECTRICITY_FUELS)
        .values("country_id", "year")
        .annotate(low_carbon_generation=Sum("generation"))
    )
    low_carbon_by_key = {(r["country_id"], r["year"]): (r["low_carbon_generation"] or 0.0) for r in low_carbon_rows}

    monthly_generation_rows = list(
        MonthlyGenerationData.objects.filter(
            country_code__in=list(country_id_by_code.keys()),
            is_aggregate_series=False,
        )
        .values("country_code", "date__year")
        .annotate(total_generation_twh=Sum("generation_twh"))
    )
    annual_gen_by_country = {
        (country_id_by_code[r["country_code"]], r["date__year"]): (r["total_generation_twh"] or 0.0)
        for r in monthly_generation_rows
        if r["country_code"] in country_id_by_code and r["date__year"] is not None
    }

    years = sorted({year for (_, year) in totals_by_key.keys()})
    rank_by_year_and_country: dict[tuple[int, int], int] = {}
    for year in years:
        rows_for_year = [r for r in totals_rows if r["year"] == year]
        rows_for_year.sort(key=lambda r: r["total_generation"] or 0.0, reverse=True)
        for rank, r in enumerate(rows_for_year, start=1):
            rank_by_year_and_country[(r["country_id"], year)] = rank

    upserts: list[tuple[int, int, dict]] = []
    for (country_id, year), energy_row in energy_by_key.items():
        total_generation = totals_by_key.get((country_id, year))
        if total_generation is None:
            continue

        rank = rank_by_year_and_country.get((country_id, year))
        if rank is None:
            continue

        low_carbon_generation = low_carbon_by_key.get((country_id, year), 0.0)
        electricity_share_low_carbon = (low_carbon_generation / total_generation * 100) if total_generation > 0 else 0.0

        upserts.append(
            (
                country_id,
                year,
                {
                    "generation_twh": annual_gen_by_country.get((country_id, year)),
                    "electricity_rank": rank,
                    "electricity_share_low_carbon": electricity_share_low_carbon,
                    "share_electricity": energy_row["share_electricity"],
                    "energy_share_low_carbon": energy_row["share_low_carbon"],
                },
            )
        )

    if stdout is not None:
        stdout.write(f"Backfilling CountryTrackerYear for {len(upserts)} country-year(s)...")

    with transaction.atomic():
        for country_id, year, defaults in upserts:
            CountryTrackerYear.objects.update_or_create(
                country_id=country_id,
                year=year,
                defaults=defaults,
            )

    backfill_tracker_years(stdout=stdout)

    return len(upserts)


class Command(BaseCommand):
    help = (
        "Backfill CountryTrackerYear from CountryEnergyBalanceYear and CountryFuelYear. "
        "Creates/updates tracker rows for country-years where both sources exist."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--country",
            nargs="*",
            metavar="CODE",
            help="Optional ISO-3 country codes to backfill (e.g. GBR DEU FRA). Defaults to all countries.",
        )

    def handle(self, *args, **options):
        requested: list[str] | None = options["country"]
        upserts = backfill_country_tracker_years(country_codes=requested, stdout=self.stdout)
        self.stdout.write(self.style.SUCCESS(f"Upserted {upserts} CountryTrackerYear row(s)."))
