"""
Management command: load_generation_units

Loads GenerationUnit rows from the CODERS generators API for Canada.
Replaces all existing GenerationUnit rows for the target country and year,
then rebuilds GenerationUnitRegionFuelYear and GenerationUnitRegionYear
aggregates from those units.

CODERS gen_type values are mapped onto Ember Fuel.type names. The snapshot year
is hard-coded (override with --year).

Usage:
    uv run python manage.py load_generation_units
    uv run python manage.py load_generation_units --year 2025
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Sum

from core.models import (
    Country,
    Fuel,
    GenerationUnit,
    GenerationUnitRegionFuelYear,
    GenerationUnitRegionYear,
)
from energystats.tasks.load_coders import CodersApiClient

COUNTRY_CODE = "CAN"
DEFAULT_YEAR = 2025

# Map CODERS gen_type codes onto Ember Fuel.type names used elsewhere in this app.
GEN_TYPE_TO_FUEL: dict[str, str] = {
    "hydro_daily": "Hydro",
    "hydro_run": "Hydro",
    "hydro_monthly": "Hydro",
    "wind_ons": "Wind",
    "solar_PV": "Solar",
    "NG_SC": "Gas",
    "NG_CG": "Gas",
    "NG_CC": "Gas",
    "biomass": "Bioenergy",
    "biogas": "Bioenergy",
    "MSW": "Bioenergy",
    "coal": "Coal",
    "coal_CCS": "Coal",
    "nuclear": "Nuclear",
    "diesel_CT": "Other fossil",
    "oil_CT": "Other fossil",
    "oil_ST": "Other fossil",
    "gasoline_CT": "Other fossil",
}


def _parse_float(value: Any, *, field_name: str) -> float:
    if value is None or value == "" or value == "NULL":
        raise ValueError(f"missing {field_name}")
    return float(value)


def _build_units(
    records: list[dict[str, Any]],
    *,
    country: Country,
    year: int,
    fuels_by_type: dict[str, Fuel],
) -> tuple[list[GenerationUnit], int, set[str]]:
    """
    Convert CODERS API records into GenerationUnit instances.

    Returns (units, skipped_count, unknown_gen_types).
    """
    units: list[GenerationUnit] = []
    skipped = 0
    unknown_gen_types: set[str] = set()

    for record in records:
        name = str(record.get("generation_unit_name") or "").strip()
        region = str(record.get("province") or "").strip()
        gen_type = str(record.get("gen_type") or "").strip()

        if not name or not region or not gen_type:
            skipped += 1
            continue

        fuel_type = GEN_TYPE_TO_FUEL.get(gen_type)
        if fuel_type is None:
            unknown_gen_types.add(gen_type)
            skipped += 1
            continue

        fuel = fuels_by_type.get(fuel_type)
        if fuel is None:
            raise CommandError(
                f"Fuel type '{fuel_type}' (from CODERS gen_type '{gen_type}') "
                "does not exist in the database. Run the Ember transform/load first."
            )

        try:
            capacity_mw = _parse_float(record.get("unit_effective_capacity"), field_name="unit_effective_capacity")
            energy_gwh = _parse_float(record.get("unit_average_annual_energy"), field_name="unit_average_annual_energy")
        except (TypeError, ValueError):
            skipped += 1
            continue

        units.append(
            GenerationUnit(
                country=country,
                region=region,
                fuel=fuel,
                year=year,
                generation_unit_name=name,
                unit_effective_capacity_mw=capacity_mw,
                unit_average_annual_energy_gwh=energy_gwh,
            )
        )

    return units, skipped, unknown_gen_types


def _build_region_fuel_year_aggregates(
    *,
    country: Country,
    year: int,
) -> list[GenerationUnitRegionFuelYear]:
    """Sum GenerationUnit capacity/energy by country, region, fuel, and year."""
    rows = (
        GenerationUnit.objects.filter(country=country, year=year)
        .values("region", "fuel_id")
        .annotate(
            effective_capacity_mw=Sum("unit_effective_capacity_mw"),
            average_annual_energy_gwh=Sum("unit_average_annual_energy_gwh"),
        )
    )
    return [
        GenerationUnitRegionFuelYear(
            country=country,
            region=row["region"],
            fuel_id=row["fuel_id"],
            year=year,
            effective_capacity_mw=row["effective_capacity_mw"] or 0.0,
            average_annual_energy_gwh=row["average_annual_energy_gwh"] or 0.0,
        )
        for row in rows
    ]


def _build_region_year_aggregates(
    *,
    country: Country,
    year: int,
) -> list[GenerationUnitRegionYear]:
    """Sum GenerationUnit capacity/energy by country, region, and year (all fuels)."""
    rows = (
        GenerationUnit.objects.filter(country=country, year=year)
        .values("region")
        .annotate(
            effective_capacity_mw=Sum("unit_effective_capacity_mw"),
            average_annual_energy_gwh=Sum("unit_average_annual_energy_gwh"),
        )
    )
    return [
        GenerationUnitRegionYear(
            country=country,
            region=row["region"],
            year=year,
            effective_capacity_mw=row["effective_capacity_mw"] or 0.0,
            average_annual_energy_gwh=row["average_annual_energy_gwh"] or 0.0,
        )
        for row in rows
    ]


class Command(BaseCommand):
    help = (
        "Load GenerationUnit rows for Canada from the CODERS generators API, "
        "then rebuild GenerationUnitRegionFuelYear and GenerationUnitRegionYear aggregates."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--year",
            type=int,
            default=DEFAULT_YEAR,
            help=f"Snapshot year to store on each GenerationUnit (default: {DEFAULT_YEAR})",
        )

    def handle(self, *args, **options):
        year: int = options["year"]

        try:
            country = Country.objects.get(code=COUNTRY_CODE)
        except Country.DoesNotExist as exc:
            raise CommandError(f"Country with code {COUNTRY_CODE} not found. Load Ember country data first.") from exc

        try:
            client = CodersApiClient()
            records = client.fetch_generators()
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        except Exception as exc:
            raise CommandError(f"Failed to fetch CODERS generators: {exc}") from exc

        fuels_by_type = {fuel.type: fuel for fuel in Fuel.objects.filter(type__in=set(GEN_TYPE_TO_FUEL.values()))}
        units, skipped, unknown_gen_types = _build_units(
            records,
            country=country,
            year=year,
            fuels_by_type=fuels_by_type,
        )

        if unknown_gen_types:
            self.stderr.write(
                self.style.WARNING("Skipped unknown CODERS gen_type value(s): " + ", ".join(sorted(unknown_gen_types)))
            )

        with transaction.atomic():
            deleted_units, _ = GenerationUnit.objects.filter(country=country, year=year).delete()
            GenerationUnit.objects.bulk_create(units)

            fuel_aggregates = _build_region_fuel_year_aggregates(country=country, year=year)
            deleted_fuel_aggregates, _ = GenerationUnitRegionFuelYear.objects.filter(
                country=country, year=year
            ).delete()
            GenerationUnitRegionFuelYear.objects.bulk_create(fuel_aggregates)

            region_aggregates = _build_region_year_aggregates(country=country, year=year)
            deleted_region_aggregates, _ = GenerationUnitRegionYear.objects.filter(country=country, year=year).delete()
            GenerationUnitRegionYear.objects.bulk_create(region_aggregates)

        self.stdout.write(
            self.style.SUCCESS(
                f"Loaded {len(units)} GenerationUnit row(s) for {country.code} year {year} "
                f"(replaced {deleted_units} existing unit row(s); skipped {skipped} API row(s)). "
                f"Rebuilt {len(fuel_aggregates)} GenerationUnitRegionFuelYear row(s) "
                f"(replaced {deleted_fuel_aggregates}) and "
                f"{len(region_aggregates)} GenerationUnitRegionYear row(s) "
                f"(replaced {deleted_region_aggregates})."
            )
        )
