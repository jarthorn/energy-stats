import csv
import os
from collections import defaultdict
from collections.abc import Iterable

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Country, CountryEnergyBalanceYear

# CSV "Product" values for total energy supply (PJ) — not included in total_supply sum.
TES_FLOW = "Total energy supply (PJ)"

SUPPLY_PRODUCT_TO_FIELD = {
    "Coal, peat and oil shale": "coal_supply",
    "Crude, NGL and feedstocks": "oil_supply",
    "Natural gas": "gas_supply",
    "Nuclear": "nuclear_supply",
    "Renewables and waste": "renewable_supply",
}

ELECTRICITY_PRODUCT = "Electricity"
ELECTRICITY_FLOW_PREFIX = "Electricity, CHP and heat plants"


def _parse_pj_cell(raw: str) -> int | None:
    """Return PJ as int, or None if missing / non-numeric (e.g. '..')."""
    if raw is None:
        return None
    value = raw.strip()
    if not value or value in {"..", "-", "…"}:
        return None
    try:
        # IEA values are usually integers; allow decimals defensively.
        return int(round(float(value)))
    except ValueError:
        return None


def _classify_row(product: str, flow: str) -> str | None:
    """
    Return a key: one of coal_supply, oil_supply, ... renewable_supply, or 'electricity'.
    """
    product = product.strip()
    flow = flow.strip()
    if product == ELECTRICITY_PRODUCT and flow.startswith(ELECTRICITY_FLOW_PREFIX):
        return "electricity"
    if flow == TES_FLOW:
        return SUPPLY_PRODUCT_TO_FIELD.get(product)
    return None


def _iter_year_indices(header: list[str]) -> Iterable[tuple[int, int]]:
    """Yield (column_index, year) for year columns after Country, Product, Flow."""
    for idx, label in enumerate(header[3:], start=3):
        label = label.strip()
        if not label:
            continue
        try:
            year = int(label)
        except ValueError:
            continue
        yield idx, year


class Command(BaseCommand):
    help = (
        "Load IEA World Energy Balances (filtered CSV) into CountryEnergyBalanceYear: "
        "one row per country per year. Electricity (CHP/heat plants) is excluded from "
        "total_supply and used only for share_electricity."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            type=str,
            default="data/iea-world-energy-balances-2025-filtered.csv",
            help="Path to the filtered IEA CSV file",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse and report counts only; do not write to the database",
        )

    def handle(self, *args, **options):
        file_path = options["file"]
        dry_run = options["dry_run"]

        if not os.path.exists(file_path):
            self.stderr.write(self.style.ERROR(f"File not found: {file_path}"))
            return

        with open(file_path, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            first_line = next(reader)
            if first_line and len(first_line) > 0 and "Source:" in first_line[0]:
                header = next(reader)
            else:
                header = first_line

            country_col = header.index("Country")
            product_col = header.index("Product")
            flow_col = header.index("Flow")
            year_specs = list(_iter_year_indices(header))

            rows_by_country: dict[str, list[list[str]]] = defaultdict(list)
            for row in reader:
                if row:
                    row_country = row[country_col].strip()
                    rows_by_country[row_country].append(row)

        unmapped_iea: list[str] = []
        written = 0
        skipped_years = 0
        skipped_unmapped_countries = 0
        skipped_invalid_csv_countries = 0

        objects_to_create: list[CountryEnergyBalanceYear] = []

        for iea_country in sorted(rows_by_country):
            country_rows = rows_by_country[iea_country]
            country_obj = Country.objects.filter(name=iea_country).first()
            if country_obj is None:
                unmapped_iea.append(iea_country)
                skipped_unmapped_countries += 1
                continue

            # Map supply key -> full CSV row
            row_by_key: dict[str, list[str]] = {}
            for row in country_rows:
                if len(row) <= flow_col:
                    continue
                key = _classify_row(row[product_col], row[flow_col])
                if key is None:
                    continue
                row_by_key[key] = row

            required_supply_keys = set(SUPPLY_PRODUCT_TO_FIELD.values())
            missing_keys = required_supply_keys - set(row_by_key)
            if missing_keys:
                self.stderr.write(
                    self.style.WARNING(
                        f"{iea_country}: missing expected rows {sorted(missing_keys)}; skipping country."
                    )
                )
                skipped_invalid_csv_countries += 1
                continue

            electricity_row = row_by_key.get("electricity")
            if electricity_row is None:
                self.stderr.write(
                    self.style.WARNING(
                        f"{iea_country}: missing electricity row; share_electricity will be 0 where unknown."
                    )
                )

            for col_idx, year in year_specs:
                supplies: dict[str, int] = {}
                ok = True
                for field_name in sorted(required_supply_keys):
                    row = row_by_key[field_name]
                    if col_idx >= len(row):
                        ok = False
                        break
                    parsed = _parse_pj_cell(row[col_idx])
                    if parsed is None:
                        ok = False
                        break
                    supplies[field_name] = parsed
                if not ok:
                    skipped_years += 1
                    self.stderr.write(self.style.WARNING(f"Skipped incomplete year: {year} for country: {iea_country}"))
                    continue

                coal = supplies["coal_supply"]
                oil = supplies["oil_supply"]
                gas = supplies["gas_supply"]
                nuclear = supplies["nuclear_supply"]
                renewable = supplies["renewable_supply"]
                total_supply = coal + oil + gas + nuclear + renewable

                if total_supply <= 0:
                    skipped_years += 1
                    self.stderr.write(self.style.WARNING(
                        f"Skipped year: {year} for country: {iea_country} because total supply is 0"
                    ))
                    continue

                electricity_pj = 0
                if electricity_row is not None and col_idx < len(electricity_row):
                    electricity_pj = _parse_pj_cell(electricity_row[col_idx]) or 0

                share_low_carbon = (nuclear + renewable) / total_supply * 100.0
                share_renewable = renewable / total_supply * 100.0
                share_electricity = electricity_pj / total_supply * 100.0

                if dry_run:
                    written += 1
                    continue

                objects_to_create.append(
                    CountryEnergyBalanceYear(
                        country=country_obj,
                        year=year,
                        coal_supply=coal,
                        oil_supply=oil,
                        gas_supply=gas,
                        nuclear_supply=nuclear,
                        renewable_supply=renewable,
                        total_supply=total_supply,
                        share_low_carbon=share_low_carbon,
                        share_renewable=share_renewable,
                        share_electricity=share_electricity,
                    )
                )
                written += 1

        self.stdout.write(f"Skipped incomplete years: {skipped_years}")
        self.stdout.write(f"Skipped (no Country row for IEA name): {skipped_unmapped_countries}")
        self.stdout.write(f"Skipped (invalid / incomplete CSV for country): {skipped_invalid_csv_countries}")
        if unmapped_iea:
            self.stdout.write(self.style.WARNING(f"No Country match for: {', '.join(unmapped_iea)}"))

        if dry_run:
            self.stdout.write(self.style.SUCCESS(f"Dry run: would write {written} country-year rows."))
            return

        if not objects_to_create:
            self.stderr.write(self.style.ERROR("No rows to load (nothing written). Database unchanged."))
            return

        with transaction.atomic():
            CountryEnergyBalanceYear.objects.all().delete()
            CountryEnergyBalanceYear.objects.bulk_create(objects_to_create, batch_size=500)

        self.stdout.write(
            self.style.SUCCESS(
                f"Loaded {len(objects_to_create)} CountryEnergyBalanceYear rows "
                f"({len(rows_by_country)} IEA countries in file)."
            )
        )
