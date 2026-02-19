from django.shortcuts import render
from .models import Country

def index(request):
    return render(request, 'core/index.html')

def country_index(request):
    countries = list(Country.objects.order_by('electricity_rank'))

    for country in countries:
        if country.generation_previous_12_months > 0:
            growth = (country.generation_latest_12_months - country.generation_previous_12_months) / country.generation_previous_12_months
            country.yoy_growth_pct = growth * 100
        else:
            country.yoy_growth_pct = None

    return render(request, 'core/country_index.html', {'countries': countries})
