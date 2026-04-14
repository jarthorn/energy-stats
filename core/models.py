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
    generation_latest_12_months = models.FloatField(
        help_text="Sum of electricity generation in the most recent 12 months (TWh)"
    )
    generation_previous_12_months = models.FloatField(
        help_text="Sum of electricity generation from 24-13 months ago (TWh)"
    )
    latest_month = models.DateField(
        null=True, blank=True, help_text="The most recent month for which data is available"
    )
    share_low_carbon = models.FloatField(
        null=True,
        blank=True,
        help_text="Share of this country's electricity generation from low-carbon sources (%)",
    )

    class Meta:
        verbose_name_plural = "countries"
        ordering = ["electricity_rank"]

    def __str__(self):
        return f"{self.name} ({self.code})"


class Fuel(models.Model):
    type = models.CharField(
        max_length=100, unique=True, help_text="A unique string representing a particular type of fuel"
    )
    rank = models.IntegerField(help_text="This fuel type's rank in total generation across all countries")
    summary = models.TextField(help_text="A paragraph describing this fuel type")
    generation_all_time = models.FloatField(
        default=0.0, help_text="Total electricity generation from this fuel source across all recorded data (TWh)"
    )
    generation_latest_12_months = models.FloatField(
        default=0.0,
        help_text="Total global electricity generation from this fuel source in the most recent 12 months (TWh)",
    )
    top_country_generation = models.ForeignKey(
        Country,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="top_generation_fuels",
        help_text="The country with the most generation from this fuel over the latest 12 months",
    )
    top_country_share = models.ForeignKey(
        Country,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="top_share_fuels",
        help_text="The country with the largest generation share from this fuel over 12 months",
    )

    class Meta:
        ordering = ["rank"]

    def __str__(self):
        return self.type


class CountryFuel(models.Model):
    country = models.ForeignKey(Country, on_delete=models.CASCADE, related_name="country_fuels")
    fuel = models.ForeignKey(Fuel, on_delete=models.CASCADE, related_name="country_fuels")
    share = models.FloatField(
        help_text="Percentage of this country's electricity supplied by this fuel over the most recent 12 months"
    )
    latest_month = models.DateField(
        help_text="The latest date for which generation data is available (always the first day of the month)"
    )
    generation_latest_12_months = models.FloatField(
        help_text="Sum of electricity generation in the most recent 12 months (TWh)"
    )
    generation_latest_month = models.FloatField(
        null=True, blank=True, help_text="Electricity generation in the most recent month (TWh)"
    )
    share_latest_month = models.FloatField(
        null=True,
        blank=True,
        help_text="Percentage of this country's electricity supplied by this fuel in the most recent month (%)",
    )
    generation_previous_12_months = models.FloatField(
        help_text="Sum of electricity generation from 24-13 months ago (TWh)"
    )
    month_yoy_growth = models.FloatField(
        null=True,
        blank=True,
        help_text="Growth rate between the latest month, and the same month in the previous year (%)",
    )
    annual_yoy_growth = models.FloatField(
        null=True, blank=True, help_text="Growth rate between the latest 12 months and the previous 12 months (%)"
    )

    class Meta:
        unique_together = [("country", "fuel")]

    def previous_12_months_start(self):
        if self.latest_month is None:
            return None
        year = self.latest_month.year
        month = self.latest_month.month - 11
        while month <= 0:
            month += 12
            year -= 1
        return self.latest_month.replace(year=year, month=month, day=1)

    def __str__(self):
        return f"{self.country} - {self.fuel}"


class CountryFuelYear(models.Model):
    country = models.ForeignKey(Country, on_delete=models.CASCADE, related_name="annual_data")
    fuel = models.ForeignKey(Fuel, on_delete=models.CASCADE, related_name="annual_data")
    year = models.IntegerField()
    is_complete = models.BooleanField(help_text="Indicates if we have data for the entire year.")
    share = models.FloatField(help_text="Share of this country's total fuel generation that came from this fuel")
    generation = models.FloatField(help_text="Total electricity generation from this fuel for this year and country")
    yoy_growth = models.FloatField(
        help_text="Percent growth since the previous year. "
        "A value of zero is used if no data are available for the previous year."
    )

    class Meta:
        unique_together = [("country", "fuel", "year")]

    def __str__(self):
        return f"{self.country} - {self.fuel} ({self.year})"


class FuelYear(models.Model):
    fuel = models.ForeignKey(Fuel, on_delete=models.CASCADE, related_name="global_annual_data")
    year = models.IntegerField()
    share = models.FloatField(help_text="Share of total global generation for this fuel in this calendar year")
    generation = models.FloatField(help_text="Total global generation for this fuel in this year")

    class Meta:
        unique_together = [("fuel", "year")]

    def __str__(self):
        return f"{self.fuel} - {self.year}"


class CountryEnergyBalanceYear(models.Model):
    """
    Total energy supply (TES) by source for one country and one calendar year.
    Sourced from IEA World Energy Balances.
    Note that energy supply is production + imports - exports.
    See https://www.iea.org/data-and-statistics/data-product/world-energy-balances for more details.
    """

    country = models.ForeignKey(
        Country,
        on_delete=models.CASCADE,
        related_name="energy_balance_years",
        help_text="Country this balance applies to",
    )
    year = models.IntegerField(help_text="Calendar year")
    coal_supply = models.IntegerField(help_text="Total energy supply from coal, peat and oil shale (PJ)")
    oil_supply = models.IntegerField(help_text="Total energy supply from crude oil, NGL and feedstocks (PJ)")
    gas_supply = models.IntegerField(help_text="Total energy supply from natural gas (PJ)")
    nuclear_supply = models.IntegerField(help_text="Total energy supply from nuclear (PJ)")
    renewable_supply = models.IntegerField(help_text="Total energy supply from renewables and waste (PJ)")
    total_supply = models.IntegerField(help_text="Sum of coal, oil, gas, nuclear and renewable supply (PJ)")
    share_low_carbon = models.FloatField(
        help_text="Percentage share of total energy supply from nuclear and renewable sources"
    )
    share_renewable = models.FloatField(help_text="Percentage share of total energy supply from renewable sources")
    share_electricity = models.FloatField(
        help_text="Total electricity production as a percentage of total energy supply"
    )

    class Meta:
        verbose_name = "country energy balance year"
        verbose_name_plural = "country energy balance years"
        unique_together = [("country", "year")]
        ordering = ["country", "year"]

    def __str__(self):
        return f"{self.country} - {self.year}"


class CountryTrackerYear(models.Model):
    """
    Memoized tracker metrics for one country and one calendar year.
    """

    country = models.ForeignKey(
        Country,
        on_delete=models.CASCADE,
        related_name="tracker_years",
        help_text="Country this tracker row applies to",
    )
    year = models.IntegerField(help_text="Calendar year")
    generation_twh = models.FloatField(
        null=True,
        blank=True,
        help_text="Total electricity generation for this country and year (TWh)",
    )
    electricity_rank = models.IntegerField(help_text="The country's rank as an electricity producer")
    electricity_share_low_carbon = models.FloatField(
        help_text="Share of electricity generation from low-carbon sources (%)"
    )
    share_electricity = models.FloatField(help_text="Share of primary energy that is generating electricity (%)")
    energy_share_low_carbon = models.FloatField(help_text="Share of primary energy from low-carbon sources (%)")

    class Meta:
        verbose_name = "country tracker year"
        verbose_name_plural = "country tracker years"
        unique_together = [("country", "year")]
        ordering = ["country", "year"]

    def __str__(self):
        return f"{self.country} - {self.year}"


class MonthlyGenerationRecord(models.Model):
    country = models.ForeignKey(
        Country,
        on_delete=models.CASCADE,
        related_name="monthly_generation_records",
        help_text="Country for which this record was set",
    )
    fuel = models.ForeignKey(
        Fuel,
        on_delete=models.CASCADE,
        related_name="monthly_generation_records",
        help_text="Fuel type for which this record was set",
    )
    date = models.DateField(help_text="Month for which this record applies (first day of the month)")
    record_type = models.CharField(
        max_length=32,
        help_text="Type of record, e.g. 'generation' or 'share'",
    )
    generation_twh = models.FloatField(
        help_text="Electricity generation from this fuel in this month (TWh) at the time of the record"
    )
    share_of_generation_pct = models.FloatField(
        help_text="Share of total generation from this fuel in this month (%) at the time of the record"
    )

    class Meta:
        verbose_name = "monthly generation record"
        verbose_name_plural = "monthly generation records"
        ordering = ["country", "fuel", "date", "record_type"]

    def __str__(self):
        return f"{self.country} - {self.fuel} ({self.date}, {self.record_type})"
