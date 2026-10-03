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

# Display nouns/adjectives for subnational areas. Canada uses province terminology.
REGION_TERMS_BY_COUNTRY: dict[str, dict[str, str]] = {
    "CAN": {
        "region": "province",
        "regions": "provinces",
        "regional": "provincial",
    },
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


@register.filter
def region_term(country, kind: str) -> str:
    """
    Return the country-appropriate label for a region term.

    ``kind`` should be one of: region, regions, regional (any capitalization).
    For Canada this becomes province / provinces / provincial; otherwise the
    input kind is returned with its original capitalization style preserved.
    """
    key = kind.lower()
    defaults = {
        "region": "region",
        "regions": "regions",
        "regional": "regional",
    }
    if key not in defaults:
        return kind

    country_code = getattr(country, "code", None)
    value = REGION_TERMS_BY_COUNTRY.get(country_code, defaults).get(key, defaults[key])
    if kind[:1].isupper():
        value = value[:1].upper() + value[1:]
    return value
