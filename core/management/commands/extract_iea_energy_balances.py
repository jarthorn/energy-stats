import csv
import os
from django.core.management.base import BaseCommand
from core.models import Country

class Command(BaseCommand):
    help = 'Identify countries in the database that are missing from the IEA energy balances CSV.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            default='data/iea-world-energy-balances-2025-filtered.csv',
            help='Path to the filtered IEA CSV file'
        )

    def handle(self, *args, **options):
        file_path = options['file']

        if not os.path.exists(file_path):
            self.stderr.write(self.style.ERROR(f"File not found: {file_path}"))
            return

        iea_countries = set()
        
        try:
            with open(file_path, 'r', newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                # Skip the source/rights line if present
                first_line = next(reader)
                if first_line and len(first_line) > 0 and "Source:" in first_line[0]:
                    header = next(reader)
                else:
                    header = first_line
                
                # Header format assumed from filtered file: Country,Product,Flow,2000,2001...
                for row in reader:
                    if row:
                        iea_countries.add(row[0].strip())
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error reading CSV: {e}"))
            return

        db_countries = set(Country.objects.values_list('name', flat=True))
        
        missing_countries = sorted(list(db_countries - iea_countries))

        if not missing_countries:
            self.stdout.write(self.style.SUCCESS("All countries in the database are present in the IEA data."))
        else:
            self.stdout.write(self.style.WARNING(f"Found {len(missing_countries)} countries in the database missing from IEA data:"))
            for country in missing_countries:
                self.stdout.write(f"- {country}")

        # Summary counts
        self.stdout.write(f"\nTotal countries in DB: {len(db_countries)}")
        self.stdout.write(f"Total countries in IEA file: {len(iea_countries)}")
