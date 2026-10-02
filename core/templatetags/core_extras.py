from django import template

register = template.Library()

CANADA_REGION_DISPLAY_NAMES: dict[str, str] = {
    "AB": "Alberta",
    "BC": "British Columbia",
    "MB": "Manitoba",
    "NB": "New Brunswick",
    "NL": "Newfoundland and Labrador",
    "NS": "Nova Scotia",
    "NT": "Northwest Territories",
    "NU": "Nunavut",
    "ON": "Ontario",
    "PE": "Prince Edward Island",
    "QC": "Quebec",
    "SK": "Saskatchewan",
    "YT": "Yukon",
}


@register.filter
def region_display_name(region: str, country) -> str:
    """
    Convert a region code into a display name for the given country.

    Currently understands Canadian provinces and territories; returns the raw
    region value unchanged for all other countries or unrecognized codes.
    """
    if getattr(country, "code", None) == "CAN":
        return CANADA_REGION_DISPLAY_NAMES.get(region, region)
    return region
