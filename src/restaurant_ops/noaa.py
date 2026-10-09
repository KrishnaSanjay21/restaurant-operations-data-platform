from __future__ import annotations

from datetime import date
from typing import Any

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential


class NOAAClient:
    def __init__(self, timeout_seconds: int = 120) -> None:
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "restaurant-operations-data-platform/0.1",
                "Accept": "application/json",
            }
        )

    @retry(
        retry=retry_if_exception_type(requests.RequestException),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    def daily_summaries(
        self,
        endpoint: str,
        station: str,
        start_date: str,
        end_date: str | None = None,
    ) -> list[dict[str, Any]]:
        params = {
            "dataset": "daily-summaries",
            "stations": station,
            "startDate": start_date,
            "endDate": end_date or date.today().isoformat(),
            "format": "json",
            "units": "standard",
            "includeAttributes": "false",
        }
        response = self.session.get(endpoint, params=params, timeout=self.timeout_seconds)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise RuntimeError("Expected a JSON array from NOAA NCEI")
        return payload

