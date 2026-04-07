from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import render, get_object_or_404
from django.db.models import OuterRef, Subquery
from .models import (
    Country,
    CountryEnergyBalanceYear,
    CountryFuel,
    CountryFuelYear,
    Fuel,
    FuelYear,
    MonthlyGenerationData,
    MonthlyGenerationRecord,
)
import datetime
import plotly.graph_objects as go
from plotly.subplots import make_subplots

BAR_CHART_COLOR = "#2ecc71"
SCATTER_CHART_COLOR = "#cc2e89"


def index(request):
    return render(request, "core/index.html")


def tracker_index(request):
    return render(request, "core/tracker_index.html")


def about(request):
    return render(request, "core/about.html")


def country_index(request):
    latest_energy_balance = CountryEnergyBalanceYear.objects.filter(country=OuterRef("pk")).order_by("-year")

    countries = list(
        Country.objects.order_by("electricity_rank").annotate(
            pes_supply_pj=Subquery(latest_energy_balance.values("total_supply")[:1]),
            pes_low_carbon_pct=Subquery(latest_energy_balance.values("share_low_carbon")[:1]),
            pes_electrification_pct=Subquery(latest_energy_balance.values("share_electricity")[:1]),
        )
    )

    for country in countries:
        country.yoy_growth_pct = _growth_rate(
            country.generation_latest_12_months, country.generation_previous_12_months
        )

    return render(request, "core/country_index.html", {"countries": countries})


def fuel_index(request):
    fuels = Fuel.objects.all().order_by("rank")
    return render(request, "core/fuel_index.html", {"fuels": fuels})


def country_detail(request, code):
    country = get_object_or_404(Country, code=code)
    primary_energy_balance = CountryEnergyBalanceYear.objects.filter(country=country).order_by("-year").first()
    primary_energy_balance_yoy_growth_pct = None
    primary_energy_supply_donut_html = None
    primary_energy_supply_area_html = None
    energy_supply_colors = {
        "Coal": "#5a6a76",
        "Oil": "#ee9847",
        "Gas": "#4c94ca",
        "Nuclear": "#a261c4",
        "Renewables": "#5ad794",
    }

    if primary_energy_balance:
        previous_primary_energy_balance = CountryEnergyBalanceYear.objects.filter(
            country=country,
            year=primary_energy_balance.year - 1,
        ).first()
        if (
            previous_primary_energy_balance
            and previous_primary_energy_balance.total_supply is not None
            and previous_primary_energy_balance.total_supply > 0
            and primary_energy_balance.total_supply is not None
        ):
            primary_energy_balance_yoy_growth_pct = _growth_rate(
                primary_energy_balance.total_supply,
                previous_primary_energy_balance.total_supply,
            )

    if primary_energy_balance and primary_energy_balance.total_supply > 0:
        values = [
            primary_energy_balance.coal_supply,
            primary_energy_balance.oil_supply,
            primary_energy_balance.gas_supply,
            primary_energy_balance.nuclear_supply,
            primary_energy_balance.renewable_supply,
        ]
        labels = ["Coal", "Oil", "Gas", "Nuclear", "Renewables"]
        colors = [energy_supply_colors[label] for label in labels]

        fig = go.Figure(
            data=[
                go.Pie(
                    labels=labels,
                    values=values,
                    hole=0.55,
                    sort=False,
                    marker=dict(colors=colors),
                    hovertemplate="%{label}<br>%{value} PJ<br>%{percent} of supply<extra></extra>",
                    showlegend=True,
                )
            ]
        )
        fig.update_layout(
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=20, r=20, t=20, b=20),
            legend=dict(orientation="h", yanchor="middle", y=-0.1, xanchor="center", x=0.5),
        )
        primary_energy_supply_donut_html = fig.to_html(full_html=False, include_plotlyjs="cdn")

    # Stacked area chart: energy supply mix (%) over time
    balance_years = list(CountryEnergyBalanceYear.objects.filter(country=country).order_by("year"))
    if balance_years:
        years = []
        coal_pct = []
        oil_pct = []
        gas_pct = []
        nuclear_pct = []
        renewable_pct = []

        for row in balance_years:
            denom = (
                (row.coal_supply or 0)
                + (row.oil_supply or 0)
                + (row.gas_supply or 0)
                + (row.nuclear_supply or 0)
                + (row.renewable_supply or 0)
            )
            if denom <= 0:
                continue
            years.append(row.year)
            coal_pct.append((row.coal_supply / denom) * 100)
            oil_pct.append((row.oil_supply / denom) * 100)
            gas_pct.append((row.gas_supply / denom) * 100)
            nuclear_pct.append((row.nuclear_supply / denom) * 100)
            renewable_pct.append((row.renewable_supply / denom) * 100)

        if years:
            fig_area = go.Figure()
            fig_area.add_trace(
                go.Scatter(
                    x=years,
                    y=coal_pct,
                    mode="lines",
                    name="Coal",
                    stackgroup="one",
                    line=dict(width=0.5, color=energy_supply_colors["Coal"]),
                    fillcolor=energy_supply_colors["Coal"],
                    hovertemplate="Coal<br>%{x}: %{y:.1f}%<extra></extra>",
                )
            )
            fig_area.add_trace(
                go.Scatter(
                    x=years,
                    y=oil_pct,
                    mode="lines",
                    name="Oil",
                    stackgroup="one",
                    line=dict(width=0.5, color=energy_supply_colors["Oil"]),
                    fillcolor=energy_supply_colors["Oil"],
                    hovertemplate="Oil<br>%{x}: %{y:.1f}%<extra></extra>",
                )
            )
            fig_area.add_trace(
                go.Scatter(
                    x=years,
                    y=gas_pct,
                    mode="lines",
                    name="Gas",
                    stackgroup="one",
                    line=dict(width=0.5, color=energy_supply_colors["Gas"]),
                    fillcolor=energy_supply_colors["Gas"],
                    hovertemplate="Gas<br>%{x}: %{y:.1f}%<extra></extra>",
                )
            )
            fig_area.add_trace(
                go.Scatter(
                    x=years,
                    y=nuclear_pct,
                    mode="lines",
                    name="Nuclear",
                    stackgroup="one",
                    line=dict(width=0.5, color=energy_supply_colors["Nuclear"]),
                    fillcolor=energy_supply_colors["Nuclear"],
                    hovertemplate="Nuclear<br>%{x}: %{y:.1f}%<extra></extra>",
                )
            )
            fig_area.add_trace(
                go.Scatter(
                    x=years,
                    y=renewable_pct,
                    mode="lines",
                    name="Renewables",
                    stackgroup="one",
                    line=dict(width=0.5, color=energy_supply_colors["Renewables"]),
                    fillcolor=energy_supply_colors["Renewables"],
                    hovertemplate="Renewables<br>%{x}: %{y:.1f}%<extra></extra>",
                )
            )

            fig_area.update_layout(
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=40, r=20, t=10, b=40),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
            )
            fig_area.update_yaxes(
                title_text="<b>Share of supply</b> (%)",
                range=[0, 100],
                ticksuffix="%",
                showgrid=True,
                gridcolor="lightgray",
            )
            fig_area.update_xaxes(type="category", showgrid=False, title_text="<b>Year</b>")

            include_js = "cdn" if not primary_energy_supply_donut_html else False
            primary_energy_supply_area_html = fig_area.to_html(full_html=False, include_plotlyjs=include_js)

    yoy_growth_pct = _growth_rate(country.generation_latest_12_months, country.generation_previous_12_months)

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
        largest_source = country_fuels.order_by("-generation_latest_12_months").first()

    fastest_growing_source = None
    max_growth = float("-inf")

    for cf in country_fuels:
        growth = _growth_rate(cf.generation_latest_12_months, cf.generation_previous_12_months)
        if growth > max_growth:
            max_growth = growth
            fastest_growing_source = cf

    if max_growth == float("-inf"):
        max_growth = None

    fastest_growing_pct = max_growth

    # Build monthly generation record rows: most recent two "generation" records per fuel
    monthly_record_rows = []
    ordered_country_fuels = country_fuels.order_by("-generation_latest_12_months")

    for cf in ordered_country_fuels:
        record_qs = MonthlyGenerationRecord.objects.filter(
            country=country,
            fuel=cf.fuel,
            record_type="generation",
        ).order_by("-date")

        latest_record = record_qs.first()
        if not latest_record:
            continue

        previous_record = record_qs[1] if record_qs.count() > 1 else None

        monthly_record_rows.append(
            {
                "fuel": cf.fuel,
                "peak_month": latest_record.date,
                "peak_generation": latest_record.generation_twh,
                "previous_peak_month": previous_record.date if previous_record else None,
                "previous_peak_generation": (previous_record.generation_twh if previous_record else None),
            }
        )

    context = {
        "country": country,
        "primary_energy_balance": primary_energy_balance,
        "primary_energy_balance_yoy_growth_pct": primary_energy_balance_yoy_growth_pct,
        "primary_energy_supply_donut_html": primary_energy_supply_donut_html,
        "primary_energy_supply_area_html": primary_energy_supply_area_html,
        "country_fuels": ordered_country_fuels,
        "yoy_growth_pct": yoy_growth_pct,
        "start_date": start_date,
        "largest_source": largest_source,
        "fastest_growing_source": fastest_growing_source,
        "fastest_growing_pct": fastest_growing_pct,
        "monthly_generation_records": monthly_record_rows,
    }
    return render(request, "core/country_detail.html", context)


def country_fuel_detail(request, code, fuel_type):
    country = get_object_or_404(Country, code=code)
    country_fuel = get_object_or_404(CountryFuel, country=country, fuel__type=fuel_type)

    # Fetch annual data for the graph
    annual_data = CountryFuelYear.objects.filter(country=country, fuel__type=fuel_type).order_by("year")

    years = [d.year for d in annual_data]
    generations = [d.generation for d in annual_data]
    shares = [d.share for d in annual_data]

    graph_html = None
    if years:
        # Create figure with secondary y-axis
        fig = make_subplots(specs=[[{"secondary_y": True}]])

        # Add traces
        fig.add_trace(
            go.Bar(x=years, y=generations, name="Generation (TWh)", marker_color=BAR_CHART_COLOR),
            secondary_y=False,
        )
        fig.add_trace(
            go.Scatter(x=years, y=shares, name="Share (%)", line=dict(color=SCATTER_CHART_COLOR, width=3)),
            secondary_y=True,
        )

        # Add figure title and layout properties
        fig.update_layout(
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )

        # Set y-axes titles
        fig.update_yaxes(title_text="<b>Generation</b> (TWh)", secondary_y=False, showgrid=True, gridcolor="lightgray")
        fig.update_yaxes(title_text="<b>Share</b> (%)", secondary_y=True, showgrid=False)
        fig.update_xaxes(type="category", showgrid=False)  # Ensure years aren't displayed as floats

        graph_html = fig.to_html(full_html=False, include_plotlyjs="cdn")

    # Monthly generation comparison graph (latest 12 months vs previous 12 months)
    monthly_graph_html = None
    if country_fuel.latest_month:
        # Get up to 24 months of data ending at the latest month
        latest_month = country_fuel.latest_month
        # Compute the date 23 months before latest_month (start of 24-month window)
        start_year = latest_month.year
        start_month = latest_month.month - 23
        while start_month <= 0:
            start_month += 12
            start_year -= 1
        window_start = datetime.date(start_year, start_month, 1)

        monthly_qs = MonthlyGenerationData.objects.filter(
            country_code=country.code,
            fuel_type=fuel_type,
            is_aggregate_entity=False,
            is_aggregate_series=False,
            date__gte=window_start,
            date__lte=latest_month,
        ).order_by("date")

        # We need at least 12 months to draw the latest-year line
        if monthly_qs.count() >= 12:
            data_points = list(monthly_qs)
            # Latest 12 months
            recent_data = data_points[-12:]
            months_labels = [d.date.strftime("%b %Y") for d in recent_data]
            recent_values = [d.generation_twh for d in recent_data]

            # Previous 12 months (if available) for comparison
            previous_values = None
            if len(data_points) >= 24:
                previous_data = data_points[-24:-12]
                previous_values = [d.generation_twh for d in previous_data]

            fig_monthly = go.Figure()
            fig_monthly.add_trace(
                go.Scatter(
                    x=months_labels,
                    y=recent_values,
                    mode="lines+markers",
                    name="Latest 12 months",
                    line=dict(color=SCATTER_CHART_COLOR, width=3),
                )
            )

            if previous_values:
                fig_monthly.add_trace(
                    go.Scatter(
                        x=months_labels,
                        y=previous_values,
                        mode="lines+markers",
                        name="Previous 12 months",
                        line=dict(color=SCATTER_CHART_COLOR, width=2, dash="dash"),
                    )
                )

            fig_monthly.update_layout(
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                margin=dict(l=40, r=20, t=60, b=40),
            )
            fig_monthly.update_yaxes(title_text="<b>Generation</b> (TWh)", showgrid=True, gridcolor="lightgray")
            fig_monthly.update_xaxes(showgrid=False)

            monthly_graph_html = fig_monthly.to_html(full_html=False, include_plotlyjs=False)

    context = {
        "country": country,
        "country_fuel": country_fuel,
        "fuel": country_fuel.fuel,
        "graph_html": graph_html,
        "monthly_graph_html": monthly_graph_html,
    }
    return render(request, "core/country_fuel_detail.html", context)


def fuel_detail(request, fuel_type):
    fuel = get_object_or_404(Fuel, type=fuel_type)

    # Fetch annual global data for the graph
    annual_data = FuelYear.objects.filter(fuel=fuel).order_by("year")

    years = [d.year for d in annual_data]
    generations = [d.generation for d in annual_data]
    shares = [d.share for d in annual_data]

    graph_html = None
    if years:
        # Create figure with secondary y-axis
        fig = make_subplots(specs=[[{"secondary_y": True}]])

        # Add traces
        fig.add_trace(
            go.Bar(x=years, y=generations, name="Global Gen (TWh)", marker_color=BAR_CHART_COLOR),
            secondary_y=False,
        )
        fig.add_trace(
            go.Scatter(x=years, y=shares, name="Global Share (%)", line=dict(color=SCATTER_CHART_COLOR, width=3)),
            secondary_y=True,
        )

        fig.update_layout(
            title_text=f"Global {fuel.type} Generation and Share over Time",
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )

        fig.update_yaxes(title_text="<b>Generation</b> (TWh)", secondary_y=False, showgrid=True, gridcolor="lightgray")
        fig.update_yaxes(title_text="<b>Share</b> (%)", secondary_y=True, showgrid=False)
        fig.update_xaxes(type="category", showgrid=False)

        graph_html = fig.to_html(full_html=False, include_plotlyjs="cdn")

    # Fetch country distribution (and also build "Top Countries" slices from it).
    #
    # We materialize once so we can reuse the same dataset for:
    # - the full country table (ordered by generation)
    # - the three top-ten lists (generation/share/annual YoY growth).
    country_fuels = list(
        CountryFuel.objects.filter(fuel=fuel).select_related("country").order_by("-generation_latest_12_months")
    )

    top_generation_countries = country_fuels[:10]

    top_share_countries = sorted(
        country_fuels,
        key=lambda cf: cf.share if cf.share is not None else float("-inf"),
        reverse=True,
    )[:10]

    top_fastest_growing_countries = sorted(
        country_fuels,
        key=lambda cf: cf.annual_yoy_growth if cf.annual_yoy_growth is not None else float("-inf"),
        reverse=True,
    )[:10]

    context = {
        "fuel": fuel,
        "graph_html": graph_html,
        "country_fuels": country_fuels,
        "top_generation_countries": top_generation_countries,
        "top_share_countries": top_share_countries,
        "top_fastest_growing_countries": top_fastest_growing_countries,
    }
    return render(request, "core/fuel_detail.html", context)


def monthly_generation_records_index(request):
    """
    Paginated explorer for MonthlyGenerationRecord objects with optional filters.
    """
    qs = MonthlyGenerationRecord.objects.select_related("country", "fuel").order_by("-date", "country__name")

    country_code = request.GET.get("country")
    fuel_type = request.GET.get("fuel_type")
    record_type = request.GET.get("record_type")
    date_from = request.GET.get("date_from")
    date_to = request.GET.get("date_to")

    if country_code:
        qs = qs.filter(country__code=country_code.upper())

    if fuel_type:
        qs = qs.filter(fuel__type=fuel_type)

    if record_type:
        qs = qs.filter(record_type=record_type)

    if date_from:
        try:
            parsed_from = datetime.date.fromisoformat(date_from)
            qs = qs.filter(date__gte=parsed_from)
        except ValueError:
            pass

    if date_to:
        try:
            parsed_to = datetime.date.fromisoformat(date_to)
            qs = qs.filter(date__lte=parsed_to)
        except ValueError:
            pass

    paginator = Paginator(qs, 100)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # Build dropdown choices from records in the database
    country_choices = [
        (c["country__code"], f"{c['country__name']} ({c['country__code']})")
        for c in MonthlyGenerationRecord.objects.values("country__code", "country__name")
        .distinct()
        .order_by("country__name")
    ]
    fuel_type_choices = list(
        MonthlyGenerationRecord.objects.values_list("fuel__type", flat=True).distinct().order_by("fuel__type")
    )
    record_type_choices = [
        ("generation", "Generation"),
        ("share", "Share"),
    ]

    context = {
        "page_obj": page_obj,
        "filters": {
            "country": country_code.upper() if country_code else "",
            "fuel_type": fuel_type or "",
            "record_type": record_type or "",
            "date_from": date_from or "",
            "date_to": date_to or "",
        },
        "country_choices": country_choices,
        "fuel_type_choices": fuel_type_choices,
        "record_type_choices": record_type_choices,
    }
    return render(request, "core/monthly_generation_records_index.html", context)


def monthly_generation_records_detail(request, country_code, fuel_type, record_type):
    """
    All MonthlyGenerationRecord rows for one country, fuel, and record type, newest first.
    """
    if record_type not in ("generation", "share"):
        raise Http404("Invalid record type")
    country = get_object_or_404(Country, code=country_code.upper())
    fuel = get_object_or_404(Fuel, type=fuel_type)
    records = list(
        MonthlyGenerationRecord.objects.filter(country=country, fuel=fuel, record_type=record_type)
        .select_related("country", "fuel")
        .order_by("-date")
    )

    graph_html = None
    if records:
        chronological = list(reversed(records))
        dates = [r.date for r in chronological]
        if record_type == "generation":
            quantities = [r.generation_twh for r in chronological]
            y_axis_title = "<b>Generation</b> (TWh)"
            hover_suffix = " TWh"
        else:
            quantities = [r.share_of_generation_pct for r in chronological]
            y_axis_title = "<b>Share of generation</b> (%)"
            hover_suffix = " %"

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=dates,
                y=quantities,
                mode="lines+markers",
                line=dict(color=BAR_CHART_COLOR, width=3),
                marker=dict(size=7),
                hovertemplate="%{x|%b %Y}<br>%{y:.2f}" + hover_suffix + "<extra></extra>",
            )
        )
        fig.update_layout(
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=50, r=20, t=20, b=50),
            showlegend=False,
        )
        fig.update_xaxes(
            type="date",
            title_text="<b>Month</b>",
            showgrid=True,
            gridcolor="lightgray",
            tickformat="%b %Y",
        )
        yaxis_kwargs = {
            "title_text": y_axis_title,
            "showgrid": True,
            "gridcolor": "lightgray",
        }
        if record_type == "generation":
            yaxis_kwargs["rangemode"] = "tozero"
        fig.update_yaxes(**yaxis_kwargs)
        graph_html = fig.to_html(full_html=False, include_plotlyjs="cdn")

    context = {
        "country": country,
        "fuel": fuel,
        "record_type": record_type,
        "records": records,
        "graph_html": graph_html,
    }
    return render(request, "core/monthly_generation_records_detail.html", context)


def _growth_rate(latest, previous):
    if previous > 0:
        increase = latest - previous
        growth = increase / previous
        return growth * 100
    return 0
