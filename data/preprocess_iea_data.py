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

PRIMARY_ENERGY_PRODUCTS = {
    "Coal, peat and oil shale",
    "Crude, NGL and feedstocks",
    "Natural gas",
    "Nuclear",
    "Renewables and waste"
}

MIN_YEAR = 2000

def process_csv(input_filepath, output_filepath):
    """
    Processes a CSV representation of IEA World Energy Balances dataset.
    https://www.iea.org/data-and-statistics/data-product/world-energy-balances
    
    Filtering Rules:
    - Omit rows where Country (Column A) is not in ALLOWED_COUNTRIES
    - Omit secondary energy products
    - Omit flows other than total energy supply
    - Omit all year columns before MIN_YEAR
    """
    with open(input_filepath, 'r', newline='', encoding='utf-8') as infile, \
         open(output_filepath, 'w', newline='', encoding='utf-8') as outfile:
        
        reader = csv.reader(infile)
        writer = csv.writer(outfile, lineterminator='\n')
        
        # Read the first line (source info) and keep it as is
        source_line = next(reader, None)
        if source_line:
            writer.writerow(source_line)
            
        # Read the header line
        header = next(reader, None)
        if not header:
            return

        # Find indices of columns to keep
        # Keeping Country, Product, Flow, (indices 0-2)
        # Discarding NoCountry, NoProduct, NoFlow (indices 3-5)
        # We assume the columns starting from index 6 are the year columns
        indices_to_keep = list(range(3))
        
        for i, col in enumerate(header[6:], start=6):
            # Normal year columns like "2000"
            if col.isdigit() and int(col) >= MIN_YEAR:
                indices_to_keep.append(i)
            # Provisional/estimated columns like "2024 Provisional"
            elif "Provisional" in col and int(col.split()[0]) >= MIN_YEAR:
                indices_to_keep.append(i)
                
        # Write the filtered header
        writer.writerow([header[i] for i in indices_to_keep])
        
        # Process data rows
        rows_processed = 0
        rows_kept = 0
        
        for row in reader:
            if not row or len(row) < 3:
                continue
                
            rows_processed += 1
            country = row[0]
            product = row[1]
            flow = row[2]
            
            # Map the country name if it exists in our mapping
            if country in COUNTRY_MAPPING:
                country = COUNTRY_MAPPING[country]
            
            # Check filtering conditions
            if country in ALLOWED_COUNTRIES and _is_flow_allowed(product, flow):
                # Update the country name in the row that will be written
                row[0] = country
                filtered_row = [row[i] for i in indices_to_keep if i < len(row)]
                writer.writerow(filtered_row)
                rows_kept += 1
                
        print(f"Processed {rows_processed} data rows.")
        print(f"Kept {rows_kept} data rows.")

def _is_flow_allowed(product, flow):
    if product == "Electricity" and flow == "Electricity, CHP and heat plants (PJ)":
        return True
    elif _is_primary_energy(product) and flow == "Total energy supply (PJ)":
        return True
    elif product == "Total" and flow == "Total energy supply (PJ)":
        return True
    return False

def _is_primary_energy(product):
    # Exclude secondary energy products such as refined oil and heat
    return product in PRIMARY_ENERGY_PRODUCTS

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python preprocess_iea_data.py <input_file> <output_file>")
        print("Example: python preprocess_iea_data.py data/iea-world-energy-balances-2025.csv data/filtered_iea_data.csv")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    
    print(f"Loading '{input_file}' to process...")
    process_csv(input_file, output_file)
    print(f"Successfully saved filtered data to '{output_file}'.")
