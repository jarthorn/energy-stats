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


class Country(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=3, unique=True, help_text="3-letter ISO country code")
    summary = models.TextField(help_text="A short paragraph summarizing the electricity generation for this country")
    electricity_rank = models.IntegerField(help_text="The country's rank as an electricity producer")
    generation_latest_12_months = models.FloatField(help_text="Sum of electricity generation in the most recent 12 months (TWh)")
    generation_previous_12_months = models.FloatField(help_text="Sum of electricity generation from 24-13 months ago (TWh)")

    class Meta:
        verbose_name_plural = "countries"
        ordering = ["electricity_rank"]

    def __str__(self):
        return f"{self.name} ({self.code})"


class Fuel(models.Model):
    type = models.CharField(max_length=100, unique=True, help_text="A unique string representing a particular type of fuel")
    rank = models.IntegerField(help_text="This fuel type's rank in total generation across all countries")
    summary = models.TextField(help_text="A paragraph describing this fuel type")

    class Meta:
        ordering = ["rank"]

    def __str__(self):
        return self.type


class CountryFuel(models.Model):
    country = models.ForeignKey(Country, on_delete=models.CASCADE, related_name="country_fuels")
    fuel = models.ForeignKey(Fuel, on_delete=models.CASCADE, related_name="country_fuels")
    share = models.FloatField(help_text="Percentage of this country's electricity supplied by this fuel over the most recent 12 months")
    latest_month = models.DateField(help_text="The latest date for which generation data is available (always the first day of the month)")
    generation_latest_12_months = models.FloatField(help_text="Sum of electricity generation in the most recent 12 months (TWh)")
    generation_previous_12_months = models.FloatField(help_text="Sum of electricity generation from 24-13 months ago (TWh)")

    class Meta:
        unique_together = [("country", "fuel")]

    def __str__(self):
        return f"{self.country} - {self.fuel}"
