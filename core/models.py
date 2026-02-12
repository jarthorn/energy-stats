from django.db import models
from .country_codes import CountryCode

class MonthlyGenerationData(models.Model):
    country = models.CharField(max_length=100)
    country_code = models.CharField(max_length=3, choices=[(tag.value, tag.value) for tag in CountryCode])
    is_aggregate_entity = models.BooleanField()
    date = models.DateField()
    fuel_type = models.CharField(max_length=100)
    is_aggregate_series = models.BooleanField()
    generation_twh = models.FloatField()
    share_of_generation_pct = models.FloatField()

    def __str__(self):
        return f"{self.country} - {self.fuel_type} ({self.date})"
