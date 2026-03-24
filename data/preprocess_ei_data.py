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
    "Korea",
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
    "People's Republic of China": "China",
    "Republic of Turkiye": "Türkiye",
    "Slovak Republic": "Slovakia",
    "Korea": "South Korea",
}

HEADER_MAPPING = {
    "biodiesel_cons_pj": "biodiesel_consumption_ej",
    "biofuels_cons_pj": "biofuels_consumption_ej",
    "ethanol_cons_pj": "ethanol_consumption_ej",
    "elect_twh": "electricity_ej",
}

COLUMNS_TO_KEEP = [
    "Country",
    "Year",
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
    - Omit all year columns before MIN_YEAR
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

        for row in reader:
            if not row or len(row) < 3:
                continue

            rows_processed += 1
            country = row[0]
            year = int(row[1])

            # Map the country name if it exists in our mapping
            if country in COUNTRY_MAPPING:
                country = COUNTRY_MAPPING[country]

            # Check filtering conditions
            if country in ALLOWED_COUNTRIES and year >= MIN_YEAR:
                # Update the country name in the row that will be written
                row[0] = country
                filtered_row = [row[i] for i in indices_to_keep if i < len(row)]
                writer.writerow(filtered_row)
                rows_kept += 1

        print(f"Processed {rows_processed} data rows.")
        print(f"Kept {rows_kept} data rows.")

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
