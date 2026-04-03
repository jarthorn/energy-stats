from django.contrib import admin
from .models import (
    Country,
    CountryFuel,
    CountryFuelYear,
    Fuel,
    FuelYear,
    MonthlyGenerationData,
    MonthlyGenerationRecord,
    CountryEnergyBalanceYear,
)


@admin.register(MonthlyGenerationData)
class MonthlyGenerationDataAdmin(admin.ModelAdmin):
    list_display = ("country", "fuel_type", "date", "generation_twh", "share_of_generation_pct")
    list_filter = ("country", "fuel_type", "date")
    search_fields = ("country", "country_code", "fuel_type")


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "electricity_rank", "generation_latest_12_months")
    search_fields = ("name", "code")
    ordering = ("name",)


@admin.register(Fuel)
class FuelAdmin(admin.ModelAdmin):
    list_display = ("type", "rank", "generation_latest_12_months", "top_country_generation", "top_country_share")
    search_fields = ("type",)
    ordering = ("rank",)


@admin.register(CountryFuel)
class CountryFuelAdmin(admin.ModelAdmin):
    list_display = ("country", "fuel", "share", "generation_latest_12_months")
    list_filter = ("fuel",)
    search_fields = ("country__name", "country__code", "fuel__type")


@admin.register(CountryFuelYear)
class CountryFuelYearAdmin(admin.ModelAdmin):
    list_display = ("country", "fuel", "year", "generation", "share", "is_complete")
    list_filter = ("fuel", "year", "is_complete")
    search_fields = ("country__name", "country__code", "fuel__type")


@admin.register(FuelYear)
class FuelYearAdmin(admin.ModelAdmin):
    list_display = ("fuel", "year", "generation", "share")
    list_filter = ("fuel", "year")
    search_fields = ("fuel__type",)


@admin.register(MonthlyGenerationRecord)
class MonthlyGenerationRecordAdmin(admin.ModelAdmin):
    list_display = ("country", "fuel", "date", "generation_twh", "share_of_generation_pct")
    list_filter = ("country", "fuel", "date")
    search_fields = ("country__name", "country__code", "fuel__type")


@admin.register(CountryEnergyBalanceYear)
class CountryEnergyBalanceYearAdmin(admin.ModelAdmin):
    list_display = ("country", "year", "total_supply", "share_low_carbon", "share_renewable", "share_electricity")
    list_filter = (
        "country",
        "year",
    )
    search_fields = ("country__name", "country__code")
