"""
Convert Energy Institute Statistical Review data from narrow (long) to panel (wide) format.

Source format: one row per (Country, Year, Var) with a Value column.
Destination format: one row per (Country, Year) with each Var as its own column.
See ei-world-consolidated-panel-2024.csv for the expected column layout.
"""

import csv
import sys
from collections import defaultdict

METADATA_COLUMNS = [
    "ISO3166_alpha3",
    "ISO3166_numeric",
    "Region",
    "SubRegion",
    "OPEC",
    "EU",
    "OECD",
    "CIS",
]

# Placed immediately after Year in the panel layout (matches the 2024 panel).
POP_COLUMN = "pop"

# Map 2024 panel variable names to their 2025 narrow equivalents.
# In 2025, EI renamed several consumption (*_cons_*) / energy (*_ej) series to
# total energy supply (*_tes_*). Values are written using the 2024 names.
MAPPING_2024_TO_2025_VAR_NAMES = {
    "biodiesel_cons_pj": "biodiesel_tes_pj",
    "biofuels_cons_ej": "biofuels_tes_ej",
    "biofuels_cons_pj": "biofuels_tes_pj",
    "biogeo_ej": "biogeo_tes_ej",
    "co2_combust_per_ej": "co2_combust_per_tes_ej",
    "coalcons_ej": "coal_tes_ej",
    "ethanol_cons_pj": "ethanol_tes_pj",
    "gascons_ej": "gas_tes_ej",
    "hydro_ej": "hydro_tes_ej",
    "nuclear_ej": "nuclear_tes_ej",
    "oilcons_ej": "oil_tes_ej",
    "ren_power_ej": "ren_power_tes_ej",
    "renewables_ej": "renewables_tes_ej",
    "solar_ej": "solar_tes_ej",
    "wind_ej": "wind_tes_ej",
}

MAPPING_2025_TO_2024_VAR_NAMES = {new: old for old, new in MAPPING_2024_TO_2025_VAR_NAMES.items()}


def _canonicalize_var_name(var_name):
    """Rename 2025 variable names to their 2024 panel equivalents when known."""
    return MAPPING_2025_TO_2024_VAR_NAMES.get(var_name, var_name)


def convert_narrow_to_panel(input_filepath, output_filepath):
    with open(input_filepath, "r", newline="", encoding="utf-8-sig") as infile:
        reader = csv.DictReader(infile)
        if not reader.fieldnames:
            return

        required = {"Country", "Year", "Var", "Value", *METADATA_COLUMNS}
        missing = required - set(reader.fieldnames)
        if missing:
            raise ValueError(f"Input CSV missing required columns: {sorted(missing)}")

        # (Country, Year) -> {var: value}
        values_by_key = defaultdict(dict)
        # (Country, Year) -> metadata dict (taken from the first row seen)
        metadata_by_key = {}
        var_names = set()

        for row in reader:
            if not row.get("Country") or not row.get("Year") or not row.get("Var"):
                continue

            key = (row["Country"], row["Year"])
            var_name = _canonicalize_var_name(row["Var"])
            var_names.add(var_name)
            values_by_key[key][var_name] = row["Value"]

            if key not in metadata_by_key:
                metadata_by_key[key] = {col: row.get(col, "") for col in METADATA_COLUMNS}

    other_vars = sorted(var_names - {POP_COLUMN})
    header = ["Country", "Year", POP_COLUMN, *METADATA_COLUMNS, *other_vars]

    with open(output_filepath, "w", newline="", encoding="utf-8") as outfile:
        writer = csv.writer(outfile, lineterminator="\n")
        writer.writerow(header)

        for country, year in sorted(values_by_key.keys(), key=lambda k: (k[0], int(k[1]))):
            key = (country, year)
            values = values_by_key[key]
            metadata = metadata_by_key[key]
            row = [
                country,
                year,
                values.get(POP_COLUMN, ""),
                *[metadata[col] for col in METADATA_COLUMNS],
                *[values.get(var, "") for var in other_vars],
            ]
            writer.writerow(row)

    print(f"Wrote {len(values_by_key)} country-year rows with {len(other_vars) + 1} variable columns.")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python convert_ei_narrow_to_panel.py <input_file> <output_file>")
        print(
            "Example: python convert_ei_narrow_to_panel.py "
            "data/ei-world-consolidated-narrow-2025.csv "
            "data/ei-world-consolidated-panel-2025.csv"
        )
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]

    print(f"Converting '{input_file}' from narrow to panel format...")
    convert_narrow_to_panel(input_file, output_file)
    print(f"Successfully saved panel data to '{output_file}'.")
