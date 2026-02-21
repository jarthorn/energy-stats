from django.shortcuts import render, get_object_or_404
from .models import Country, CountryFuel
import datetime

def index(request):
    return render(request, 'core/index.html')

def country_index(request):
    countries = list(Country.objects.order_by('electricity_rank'))

    for country in countries:
        country.yoy_growth_pct = _growth_rate(
            country.generation_latest_12_months,
            country.generation_previous_12_months
        )

    return render(request, 'core/country_index.html', {'countries': countries})

def country_detail(request, code):
    country = get_object_or_404(Country, code=code)

    yoy_growth_pct = _growth_rate(
        country.generation_latest_12_months,
        country.generation_previous_12_months
    )

    start_date = None
    if country.latest_month:
        month = country.latest_month.month - 11
        year = country.latest_month.year
        if month <= 0:
            month += 12
            year -= 1
        start_date = datetime.date(year, month, 1)

    country_fuels = CountryFuel.objects.filter(country=country)

    largest_source = None
    if country_fuels.exists():
        largest_source = country_fuels.order_by('-generation_latest_12_months').first()

    fastest_growing_source = None
    max_growth = float('-inf')

    for cf in country_fuels:
        growth = _growth_rate(cf.generation_latest_12_months, cf.generation_previous_12_months)
        if growth > max_growth:
            max_growth = growth
            fastest_growing_source = cf

    if max_growth == float('-inf'):
        max_growth = None

    fastest_growing_pct = max_growth

    context = {
        'country': country,
        'country_fuels': country_fuels.order_by('-generation_latest_12_months'),
        'yoy_growth_pct': yoy_growth_pct,
        'start_date': start_date,
        'largest_source': largest_source,
        'fastest_growing_source': fastest_growing_source,
        'fastest_growing_pct': fastest_growing_pct,
    }
    return render(request, 'core/country_detail.html', context)

def _growth_rate(latest, previous):
    if previous > 0:
        increase = latest - previous
        growth = increase / previous
        return growth * 100
    return 0
