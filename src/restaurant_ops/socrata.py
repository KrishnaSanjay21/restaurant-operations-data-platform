from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential


class PublicAPIError(RuntimeError):
    """Raised when a public data API returns an unusable response."""


INSPECTION_COLUMNS = (
    "camis,dba,boro,building,street,zipcode,phone,cuisine_description,"
    "inspection_date,action,violation_code,violation_description,critical_flag,"
    "score,grade,grade_date,record_date,inspection_type,latitude,longitude,"
    "community_board,council_district,census_tract,bin,bbl,nta"
)

COMPLAINT_COLUMNS = (
    "unique_key,created_date,closed_date,agency,agency_name,complaint_type,descriptor,"
    "location_type,incident_zip,incident_address,street_name,city,"
    "status,resolution_description,borough,latitude,longitude,open_data_channel_type"
)


@dataclass(frozen=True)
class Page:
    source: str
    offset: int
    rows: list[dict[str, Any]]


class SocrataClient:
    def __init__(
        self,
        app_token: str | None = None,
        timeout_seconds: int = 120,
        session: requests.Session | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "restaurant-operations-data-platform/0.1",
                "Accept": "application/json",
            }
        )
        if app_token:
            self.session.headers["X-App-Token"] = app_token

    @retry(
        retry=retry_if_exception_type((requests.RequestException, PublicAPIError)),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    def _get(self, endpoint: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        response = self.session.get(endpoint, params=params, timeout=self.timeout_seconds)
        if response.status_code in {429, 500, 502, 503, 504}:
            raise PublicAPIError(f"Retryable response {response.status_code}: {response.text[:300]}")
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise PublicAPIError("Expected a JSON array from the Socrata endpoint")
        return payload

    def pages(
        self,
        *,
        source: str,
        endpoint: str,
        columns: str,
        order_by: str,
        where: str | None,
        page_size: int,
        max_rows: int,
    ) -> Iterator[Page]:
        offset = 0
        while True:
            remaining = max_rows - offset if max_rows > 0 else page_size
            if max_rows > 0 and remaining <= 0:
                break
            limit = min(page_size, remaining) if max_rows > 0 else page_size
            params: dict[str, Any] = {
                "$select": columns,
                "$order": order_by,
                "$limit": limit,
                "$offset": offset,
            }
            if where:
                params["$where"] = where
            rows = self._get(endpoint, params)
            if not rows:
                break
            yield Page(source=source, offset=offset, rows=rows)
            offset += len(rows)
            if len(rows) < limit:
                break

    def count(self, endpoint: str, where: str | None = None) -> int:
        params: dict[str, Any] = {"$select": "count(*)"}
        if where:
            params["$where"] = where
        payload = self._get(endpoint, params)
        return int(payload[0]["count"])

