"""
Fetches data from the CODERS API.
"""

from __future__ import annotations

import os
from typing import Any

import requests
from dotenv import load_dotenv


class CodersApiClient:
    """
    Thin wrapper around the CODERS API.

    Tables are fetched via https://api.sesit.ca/{table_name}?key=...
    All interpretation of the data is left to the caller.
    """

    BASE_URL = "https://api.sesit.ca"

    def __init__(self) -> None:
        load_dotenv()
        self.api_key = os.getenv("CODERS_API_KEY")
        if not self.api_key:
            raise ValueError("CODERS_API_KEY environment variable is not set. Add it to your .env file.")

    def fetch_generators(self) -> list[dict[str, Any]]:
        """
        Fetch all generation unit rows from CODERS.

        Returns the list of generator records from the API response.
        """
        return self._fetch_table("generators")

    def _fetch_table(self, table_name: str) -> list[dict[str, Any]]:
        """
        Fetch all rows for a CODERS table.

        Returns the list of records from the API response.
        """
        url = f"{self.BASE_URL}/{table_name}?key={self.api_key}"
        response = requests.get(url, timeout=120)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise ValueError(f"Unexpected CODERS API payload type for '{table_name}': {type(payload).__name__}")
        return payload
