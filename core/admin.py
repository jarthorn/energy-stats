from django.contrib import admin
from .models import MonthlyGenerationData, Country, Fuel, CountryFuel, CountryFuelYear

@admin.register(MonthlyGenerationData)
class MonthlyGenerationDataAdmin(admin.ModelAdmin):
    list_display = ('country', 'fuel_type', 'date', 'generation_twh', 'share_of_generation_pct')
    list_filter = ('country', 'fuel_type', 'date')
    search_fields = ('country', 'country_code', 'fuel_type')

@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'electricity_rank', 'generation_latest_12_months')
    search_fields = ('name', 'code')
    ordering = ('electricity_rank',)

@admin.register(Fuel)
class FuelAdmin(admin.ModelAdmin):
    list_display = ('type', 'rank', 'generation_latest_12_months', 'generation_all_time')
    search_fields = ('type',)
    ordering = ('rank',)

@admin.register(CountryFuel)
class CountryFuelAdmin(admin.ModelAdmin):
    list_display = ('country', 'fuel', 'share', 'generation_latest_12_months')
    list_filter = ('fuel',)
    search_fields = ('country__name', 'country__code', 'fuel__type')

@admin.register(CountryFuelYear)
class CountryFuelYearAdmin(admin.ModelAdmin):
    list_display = ('country', 'fuel', 'year', 'generation', 'share', 'is_complete')
    list_filter = ('fuel', 'year', 'is_complete')
    search_fields = ('country__name', 'country__code', 'fuel__type')
