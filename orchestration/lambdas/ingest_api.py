"""Lambda handler for paginated public-API ingestion into partitioned S3 raw storage."""

from __future__ import annotations

import gzip
import json
import os
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from typing import Any

import boto3

S3 = boto3.client("s3")

INSPECTION_COLUMNS = (
    "camis,dba,boro,building,street,zipcode,phone,cuisine_description,inspection_date,"
    "action,violation_code,violation_description,critical_flag,score,grade,grade_date,"
    "record_date,inspection_type,latitude,longitude,community_board,council_district,"
    "census_tract,bin,bbl,nta"
)
COMPLAINT_COLUMNS = (
    "unique_key,created_date,closed_date,agency,agency_name,complaint_type,descriptor,"
    "location_type,incident_zip,incident_address,street_name,city,"
    "status,resolution_description,borough,latitude,longitude,open_data_channel_type"
)


def request_json(url: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    headers = {"User-Agent": "restaurant-operations-data-platform/0.1"}
    token = os.getenv("NYC_APP_TOKEN")
    if token:
        headers["X-App-Token"] = token
    query = urllib.parse.urlencode(params)
    request = urllib.request.Request(f"{url}?{query}", headers=headers)
    with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310
        payload = json.load(response)
    if not isinstance(payload, list):
        raise ValueError("Expected a JSON array from the public API")
    return payload


def upload_rows(bucket: str, key: str, source: str, batch_id: str, rows: list[dict[str, Any]]) -> None:
    retrieved_at = datetime.now(UTC).isoformat()
    body = "".join(
        json.dumps(
            {**row, "_source": source, "_batch_id": batch_id, "_retrieved_at": retrieved_at},
            separators=(",", ":"),
        )
        + "\n"
        for row in rows
    ).encode("utf-8")
    S3.put_object(
        Bucket=bucket,
        Key=key,
        Body=gzip.compress(body),
        ContentType="application/x-ndjson",
        ContentEncoding="gzip",
        ServerSideEncryption="AES256",
        Metadata={"source": source, "batch-id": batch_id, "row-count": str(len(rows))},
    )


def socrata_source(event: dict[str, Any]) -> dict[str, Any]:
    source = event["source"]
    endpoints = {
        "inspections": "https://data.cityofnewyork.us/resource/43nn-pn8j.json",
        "complaints": "https://data.cityofnewyork.us/resource/erm2-nwe9.json",
    }
    columns = {"inspections": INSPECTION_COLUMNS, "complaints": COMPLAINT_COLUMNS}
    orders = {
        "inspections": "record_date,camis,inspection_date,violation_code",
        "complaints": "created_date DESC,unique_key DESC",
    }
    where = None
    if source == "complaints":
        start_date = event.get("start_date", "2020-01-01")
        where = (
            "agency='DOHMH' AND complaint_type IN "
            "('Food Establishment','Food Poisoning','Rodent','Mobile Food Vendor') "
            f"AND created_date >= '{start_date}T00:00:00.000'"
        )
    bucket = os.environ["RAW_BUCKET"]
    batch_id = event["batch_id"]
    ingest_date = event.get("ingest_date", datetime.now(UTC).date().isoformat())
    page_size = int(event.get("page_size", 50_000))
    max_rows = int(event.get("max_rows", 0))
    offset = 0
    file_count = 0
    while True:
        remaining = max_rows - offset if max_rows else page_size
        if max_rows and remaining <= 0:
            break
        limit = min(page_size, remaining) if max_rows else page_size
        params: dict[str, Any] = {
            "$select": columns[source],
            "$order": orders[source],
            "$limit": limit,
            "$offset": offset,
        }
        if where:
            params["$where"] = where
        rows = request_json(endpoints[source], params)
        if not rows:
            break
        key = (
            f"source={source}/ingest_date={ingest_date}/batch_id={batch_id}/"
            f"part-{file_count:05d}.jsonl.gz"
        )
        upload_rows(bucket, key, source, batch_id, rows)
        offset += len(rows)
        file_count += 1
        if len(rows) < limit:
            break
    return {**event, "source": source, "row_count": offset, "file_count": file_count}


def weather_source(event: dict[str, Any]) -> dict[str, Any]:
    params = {
        "dataset": "daily-summaries",
        "stations": event.get("station", "USW00094728"),
        "startDate": event.get("start_date", "2020-01-01"),
        "endDate": event.get("end_date", datetime.now(UTC).date().isoformat()),
        "format": "json",
        "units": "standard",
        "includeAttributes": "false",
    }
    rows = request_json("https://www.ncei.noaa.gov/access/services/data/v1", params)
    bucket = os.environ["RAW_BUCKET"]
    batch_id = event["batch_id"]
    ingest_date = event.get("ingest_date", datetime.now(UTC).date().isoformat())
    key = f"source=weather/ingest_date={ingest_date}/batch_id={batch_id}/part-00000.jsonl.gz"
    upload_rows(bucket, key, "weather", batch_id, rows)
    return {**event, "source": "weather", "row_count": len(rows), "file_count": 1}


def handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    if event["source"] == "weather":
        return weather_source(event)
    return socrata_source(event)

