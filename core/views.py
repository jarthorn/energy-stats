from django.shortcuts import render, get_object_or_404
from .models import Country, CountryFuel, CountryFuelYear, Fuel, FuelYear
import datetime
import plotly.graph_objects as go
from plotly.subplots import make_subplots

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

def fuel_index(request):
    fuels = Fuel.objects.all().order_by('rank')
    return render(request, 'core/fuel_index.html', {'fuels': fuels})

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

def country_fuel_detail(request, code, fuel_type):
    country = get_object_or_404(Country, code=code)
    country_fuel = get_object_or_404(CountryFuel, country=country, fuel__type=fuel_type)

    # Fetch annual data for the graph
    annual_data = CountryFuelYear.objects.filter(
        country=country, fuel__type=fuel_type
    ).order_by('year')

    years = [d.year for d in annual_data]
    generations = [d.generation for d in annual_data]
    shares = [d.share for d in annual_data]

    graph_html = None
    if years:
        # Create figure with secondary y-axis
        fig = make_subplots(specs=[[{"secondary_y": True}]])

        # Add traces
        fig.add_trace(
            go.Bar(x=years, y=generations, name="Generation (TWh)", marker_color='#3498db'),
            secondary_y=False,
        )
        fig.add_trace(
            go.Scatter(x=years, y=shares, name="Share (%)", line=dict(color='#e74c3c', width=3)),
            secondary_y=True,
        )

        # Add figure title and layout properties
        fig.update_layout(
            title_text="Generation and Share over Time",
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )

        # Set y-axes titles
        fig.update_yaxes(title_text="<b>Generation</b> (TWh)", secondary_y=False, showgrid=True, gridcolor='lightgray')
        fig.update_yaxes(title_text="<b>Share</b> (%)", secondary_y=True, showgrid=False)
        fig.update_xaxes(type='category', showgrid=False) # Ensure years aren't displayed as floats

        graph_html = fig.to_html(full_html=False, include_plotlyjs='cdn')

    context = {
        'country': country,
        'country_fuel': country_fuel,
        'fuel': country_fuel.fuel,
        'graph_html': graph_html,
    }
    return render(request, 'core/country_fuel_detail.html', context)

def fuel_detail(request, fuel_type):
    fuel = get_object_or_404(Fuel, type=fuel_type)

    # Fetch annual global data for the graph
    annual_data = FuelYear.objects.filter(fuel=fuel).order_by('year')

    years = [d.year for d in annual_data]
    generations = [d.generation for d in annual_data]
    shares = [d.share for d in annual_data]

    graph_html = None
    if years:
        # Create figure with secondary y-axis
        fig = make_subplots(specs=[[{"secondary_y": True}]])

        # Add traces
        fig.add_trace(
            go.Bar(x=years, y=generations, name="Global Gen (TWh)", marker_color='#3498db'),
            secondary_y=False,
        )
        fig.add_trace(
            go.Scatter(x=years, y=shares, name="Global Share (%)", line=dict(color='#e74c3c', width=3)),
            secondary_y=True,
        )

        fig.update_layout(
            title_text=f"Global {fuel.type} Generation and Share over Time",
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )

        fig.update_yaxes(title_text="<b>Generation</b> (TWh)", secondary_y=False, showgrid=True, gridcolor='lightgray')
        fig.update_yaxes(title_text="<b>Share</b> (%)", secondary_y=True, showgrid=False)
        fig.update_xaxes(type='category', showgrid=False)

        graph_html = fig.to_html(full_html=False, include_plotlyjs='cdn')

    # Fetch country distribution
    country_fuels = CountryFuel.objects.filter(fuel=fuel).order_by('-generation_latest_12_months')

    context = {
        'fuel': fuel,
        'graph_html': graph_html,
        'country_fuels': country_fuels,
    }
    return render(request, 'core/fuel_detail.html', context)

def _growth_rate(latest, previous):
    if previous > 0:
        increase = latest - previous
        growth = increase / previous
        return growth * 100
    return 0
