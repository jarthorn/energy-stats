"""
Fetches raw monthly electricity generation data from the Ember API.
"""

from __future__ import annotations

import os
from typing import Any

import requests
from dotenv import load_dotenv

from core.country_codes import CountryCode


class EmberApiClient:
    """
    Thin wrapper around the Ember electricity generation API.

    Fetches monthly generation data for a single country and returns
    the parsed JSON response. All interpretation of the data is left
    to the caller.
    """

    BASE_URL = "https://api.ember-energy.org"

    def __init__(self, start_date: str = "2000-01") -> None:
        load_dotenv()
        self.api_key = os.getenv("EMBER_API_KEY")
        if not self.api_key:
            raise ValueError(
                "EMBER_API_KEY environment variable is not set. "
                "Add it to your .env file."
            )
        self.start_date = start_date

    def fetch_country(
        self,
        country_code: CountryCode,
        is_aggregate_series: bool = False,
    ) -> list[dict[str, Any]]:
        """
        Fetch all monthly generation rows for a single country.

        Returns the list of data records from the API response, where each
        record represents one month/fuel-type combination for the given country.
        """
        url = (
            f"{self.BASE_URL}/v1/electricity-generation/monthly"
            f"?entity_code={country_code}"
            f"&is_aggregate_series={'true' if is_aggregate_series else 'false'}"
            "&is_aggregate_entity=false"
            f"&start_date={self.start_date}"
            f"&api_key={self.api_key}"
        )
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.json().get("data", [])
