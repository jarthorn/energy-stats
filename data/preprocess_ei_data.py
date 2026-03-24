import csv
import sys



# Hard-coded lists for filtering. Feel free to modify these.
ALLOWED_COUNTRIES = {
    "Argentina",
    "Armenia",
    "Australia",
    "Austria",
    "Azerbaijan",
    "Bangladesh",
    "Belarus",
    "Belgium",
    "Bolivia",
    "Bosnia Herzegovina",
    "Brazil",
    "Bulgaria",
    "Canada",
    "Chile",
    "China",
    "Colombia",
    "Costa Rica",
    "Croatia",
    "Cyprus",
    "Czechia",
    "Denmark",
    "Dominican Republic",
    "Ecuador",
    "Egypt",
    "El Salvador",
    "Estonia",
    "Finland",
    "France",
    "Georgia",
    "Germany",
    "Greece",
    "Hungary",
    "Iceland",
    "India",
    "Iran",
    "Ireland",
    "Israel",
    "Italy",
    "Japan",
    "Kazakhstan",
    "Kenya",
    "Kosovo",
    "Kuwait",
    "Kyrgyzstan",
    "Latvia",
    "Lithuania",
    "Luxembourg",
    "Malaysia",
    "Malta",
    "Mexico",
    "Moldova",
    "Mongolia",
    "Montenegro",
    "Morocco",
    "Myanmar",
    "Netherlands",
    "New Zealand",
    "Nigeria",
    "North Macedonia",
    "Norway",
    "Oman",
    "Pakistan",
    "Peru",
    "Poland",
    "Portugal",
    "Puerto Rico",
    "Qatar",
    "Romania",
    "Russia",
    "Serbia",
    "Singapore",
    "Slovakia",
    "Slovenia",
    "South Africa",
    "South Korea",
    "Spain",
    "Sri Lanka",
    "Sweden",
    "Switzerland",
    "Taiwan (China)",
    "Tajikistan",
    "Thailand",
    "The Philippines",
    "Tunisia",
    "Türkiye",
    "Ukraine",
    "United Kingdom",
    "United States",
    "Uruguay",
    "Viet Nam",
}

# Mapping to rename countries to standard names.
# Feel free to add more mappings.
COUNTRY_MAPPING = {
    "Czech Republic": "Czechia",
    "Turkiye": "Türkiye",
    "US": "United States",
    "Vietnam": "Viet Nam",
    "Russian Federation": "Russia",
    "Taiwan": "Taiwan (China)",
    "Philippines": "The Philippines",
}

HEADER_MAPPING = {
    "biodiesel_cons_pj": "biodiesel_cons_ej",
    "biofuels_cons_pj": "biofuels_cons_ej",
    "ethanol_cons_pj": "ethanol_cons_ej",
    "elect_twh": "electricity_ej",
}

COLUMNS_TO_KEEP = [
    "Country",
    "Year",
    "ISO3166_alpha3",
    "biodiesel_cons_pj",
    "biofuels_cons_pj",
    "ethanol_cons_pj",
    "coalcons_ej",
    "gascons_ej",
    "oilcons_ej",
    "nuclear_ej",
    "biogeo_ej",
    "hydro_ej",
    "solar_ej",
    "wind_ej",
    "tes_ej",
    "elect_twh",
]

MIN_YEAR = 2000

def process_csv(input_filepath, output_filepath):
    """
    Processes a CSV representation of the Energy Institute's Statistical Review of World Energy dataset.
    https://www.energyinst.org/statistical-review/resources-and-data-downloads

    Filtering Rules:
    - Omit rows where Country (Column A) is not in ALLOWED_COUNTRIES
    - Omit columns that we don't need
    - Omit all year rows before MIN_YEAR
    """
    with open(input_filepath, 'r', newline='', encoding='utf-8-sig') as infile, \
         open(output_filepath, 'w', newline='', encoding='utf-8') as outfile:

        reader = csv.reader(infile)
        writer = csv.writer(outfile, lineterminator='\n')

        # Read the header line
        header = next(reader, None)
        if not header:
            return

        # Find indices of columns to keep
        indices_to_keep = [header.index(col) for col in COLUMNS_TO_KEEP]

        # Write the filtered header
        writer.writerow([HEADER_MAPPING.get(header[i], header[i]) for i in indices_to_keep])

        # Process data rows
        rows_processed = 0
        rows_kept = 0
        columns = len(header)

        for row in reader:
            if not row or len(row) < columns:
                continue

            rows_processed += 1
            country = row[0]
            year = int(row[1])

            # Map the country name if it exists in our mapping
            country = COUNTRY_MAPPING.get(country, country)
            if country not in ALLOWED_COUNTRIES:
                continue

            if year >= MIN_YEAR:
                # Make sure we write the mapped country name
                row[0] = country
                filtered_row = [_transform_value(header[i], row[i]) for i in indices_to_keep]
                writer.writerow(filtered_row)
                rows_kept += 1

        print(f"Processed {rows_processed} data rows.")
        print(f"Kept {rows_kept} data rows.")

def _transform_value(header, value):
    """
    Normalize all values to Exajoules
    """
    if (header in ("biodiesel_cons_pj", "biofuels_cons_pj", "ethanol_cons_pj")):
        # Convert Petajoules to Exajoules
        return float(value) / 1000.0
    elif header == "elect_twh":
        # Use conversion factor of 1 kWh = 3600 kJ used by the Energy Institute
        return float(value) * 0.0036
    return value

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python preprocess_ei_data.py <input_file> <output_file>")
        print(
            "Example: python preprocess_ei_data.py"
            " data/ei-world-consolidated-panel-2024.csv"
            " data/filtered_ei_data.csv"
        )
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]

    print(f"Loading '{input_file}' to process...")
    process_csv(input_file, output_file)
    print(f"Successfully saved filtered data to '{output_file}'.")
