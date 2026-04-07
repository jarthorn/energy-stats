"""
Management command: load_country_energy_balance

Loads CountryEnergyBalanceYear rows from the Energy Institute filtered panel CSV
(ei-world-consolidated-panel-filtered-2024.csv). Rows are keyed to Country via the
ISO3166_alpha3 column. Energy values in the CSV are in exajoules (EJ);
model fields are petajoules (PJ), 1 EJ = 1000 PJ.

renewable_supply is the sum of biodiesel, biofuels, ethanol, biogeo, hydro,
solar, and wind (EJ columns), converted to PJ. electricity_ej is used only for
share_electricity, not for total_supply.

Usage:
    uv run python manage.py load_country_energy_balance
    uv run python manage.py load_country_energy_balance --csv path/to/file.csv
"""

from __future__ import annotations

import csv
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import Country, CountryEnergyBalanceYear

ISO3166_ALPHA3_COLUMN = "ISO3166_alpha3"

RENEWABLE_EJ_COLUMNS = (
    "biodiesel_cons_ej",
    "biofuels_cons_ej",
    "ethanol_cons_ej",
    "biogeo_ej",
    "hydro_ej",
    "solar_ej",
    "wind_ej",
)

REQUIRED_COLUMNS = (
    "Year",
    ISO3166_ALPHA3_COLUMN,
    "coalcons_ej",
    "gascons_ej",
    "oilcons_ej",
    "nuclear_ej",
    *RENEWABLE_EJ_COLUMNS,
    "electbyfuel_coal",
    "electbyfuel_gas",
    "electbyfuel_oil",
)


def _ej_to_pj_int(value: str) -> int:
    """Parse an EJ string from the CSV and return integer PJ (1 EJ = 1000 PJ)."""
    return int(round(float(value) * 1000))


def _twh_to_pj_int(value: str, *, thermal_efficiency: float) -> int:
    """
    Use conversion factor of 1 kWh = 3600 kJ (1 TWh = 3.6 PJ) used by the Energy Institute.

    To calculate primary energy equivalent from electricity generation, we account for thermal efficiency.
    We use fuel-specific thermal efficiencies (gas 45%, coal 32%, oil 32%) based on EIA (2019 U.S. plants):
    https://www.eia.gov/todayinenergy/detail.php?id=44436
    """
    return int(round(float(value) * 3.6 / thermal_efficiency))


def _parse_ej_float(value: str) -> float:
    return float(value)


class Command(BaseCommand):
    help = (
        "Load CountryEnergyBalanceYear from the Energy Institute filtered panel CSV "
        "(EJ in file -> PJ in database). renewable_supply excludes electricity_ej; "
        "electricity_ej is only used for share_electricity."
    )

    def add_arguments(self, parser):
        default_csv = Path(settings.BASE_DIR) / "data" / "ei-world-consolidated-panel-filtered-2024.csv"
        parser.add_argument(
            "--csv",
            type=Path,
            default=default_csv,
            help=f"Path to filtered EI panel CSV (default: {default_csv})",
        )

    def handle(self, *args, **options):
        csv_path: Path = options["csv"]
        if not csv_path.is_file():
            raise CommandError(f"CSV file not found: {csv_path}")

        countries_by_code = {c.code: c for c in Country.objects.all()}
        skipped_country_rows = 0
        skipped_missing_iso_rows = 0
        missing_db_codes: set[str] = set()

        with csv_path.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
            if missing:
                raise CommandError(f"CSV missing required columns: {', '.join(missing)}")

            rows: list[tuple[Country, int, dict]] = []

            for row in reader:
                iso3 = (row.get(ISO3166_ALPHA3_COLUMN) or "").strip().upper()
                if not iso3:
                    skipped_missing_iso_rows += 1
                    continue
                country = countries_by_code.get(iso3)
                if country is None:
                    skipped_country_rows += 1
                    missing_db_codes.add(iso3)
                    continue

                year = int(row["Year"])
                coal_pj = _ej_to_pj_int(row["coalcons_ej"])
                oil_pj = _ej_to_pj_int(row["oilcons_ej"])
                gas_pj = _ej_to_pj_int(row["gascons_ej"])
                nuclear_pj = _ej_to_pj_int(row["nuclear_ej"])
                renewable_ej = sum(_parse_ej_float(row[col]) for col in RENEWABLE_EJ_COLUMNS)
                renewable_pj = int(round(renewable_ej * 1000))
                total_pj = coal_pj + oil_pj + gas_pj + nuclear_pj + renewable_pj

                # To calculate electricity share, we need to include the energy used by fossil fuels for electricity
                # generation and we assume that all renewable and nuclear energy is used for electricity generation.
                electricity_pj = (
                    _twh_to_pj_int(row["electbyfuel_coal"], thermal_efficiency=0.32)
                    + _twh_to_pj_int(row["electbyfuel_gas"], thermal_efficiency=0.45)
                    + _twh_to_pj_int(row["electbyfuel_oil"], thermal_efficiency=0.32)
                    + nuclear_pj
                    + renewable_pj
                )

                if total_pj > 0:
                    share_low_carbon = (nuclear_pj + renewable_pj) / total_pj * 100
                    share_renewable = renewable_pj / total_pj * 100
                    share_electricity = electricity_pj / total_pj * 100
                else:
                    share_low_carbon = 0.0
                    share_renewable = 0.0
                    share_electricity = 0.0

                rows.append(
                    (
                        country,
                        year,
                        {
                            "coal_supply": coal_pj,
                            "oil_supply": oil_pj,
                            "gas_supply": gas_pj,
                            "nuclear_supply": nuclear_pj,
                            "renewable_supply": renewable_pj,
                            "total_supply": total_pj,
                            "share_low_carbon": share_low_carbon,
                            "share_renewable": share_renewable,
                            "share_electricity": share_electricity,
                        },
                    )
                )

        with transaction.atomic():
            for country, year, defaults in rows:
                CountryEnergyBalanceYear.objects.update_or_create(
                    country=country,
                    year=year,
                    defaults=defaults,
                )

        if missing_db_codes:
            self.stderr.write(
                self.style.WARNING(
                    "No Country row in database for ISO3 code(s): " + ", ".join(sorted(missing_db_codes))
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Upserted {len(rows)} CountryEnergyBalanceYear row(s) from {csv_path}. "
                f"Skipped {skipped_country_rows} row(s) with no matching Country, "
                f"{skipped_missing_iso_rows} row(s) with missing or empty {ISO3166_ALPHA3_COLUMN}."
            )
        )
