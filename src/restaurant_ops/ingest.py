from __future__ import annotations

import os
from dataclasses import asdict
from datetime import UTC, date, datetime
from typing import Any

from restaurant_ops.config import PipelineConfig
from restaurant_ops.noaa import NOAAClient
from restaurant_ops.socrata import COMPLAINT_COLUMNS, INSPECTION_COLUMNS, SocrataClient
from restaurant_ops.storage import build_batch_id, write_jsonl_gzip, write_manifest


def _source_manifest(
    *,
    source: str,
    batch_id: str,
    started_at: datetime,
    files: list[dict[str, Any]],
    expected_rows: int | None,
) -> dict[str, Any]:
    row_count = sum(int(item["row_count"]) for item in files)
    return {
        "source": source,
        "batch_id": batch_id,
        "started_at": started_at.isoformat(),
        "completed_at": datetime.now(UTC).isoformat(),
        "expected_rows": expected_rows,
        "row_count": row_count,
        "file_count": len(files),
        "files": files,
    }


def ingest_public_sources(config: PipelineConfig) -> dict[str, Any]:
    started_at = datetime.now(UTC)
    batch_id = build_batch_id(started_at)
    raw_root = config.project_root / "data" / "raw"
    client = SocrataClient(app_token=os.getenv("NYC_APP_TOKEN"))
    results: dict[str, Any] = {
        "profile": config.profile.name,
        "batch_id": batch_id,
        "started_at": started_at.isoformat(),
        "sources": {},
    }

    inspection_expected = client.count(config.inspections.endpoint)
    inspection_files: list[dict[str, Any]] = []
    for part_number, page in enumerate(
        client.pages(
            source="inspections",
            endpoint=config.inspections.endpoint,
            columns=INSPECTION_COLUMNS,
            order_by=config.inspections.primary_order or "record_date,camis",
            where=None,
            page_size=config.profile.page_size,
            max_rows=config.profile.inspections_limit,
        )
    ):
        result = write_jsonl_gzip(
            raw_root=raw_root,
            source="inspections",
            batch_id=batch_id,
            part_number=part_number,
            rows=page.rows,
        )
        inspection_files.append({**asdict(result), "path": str(result.path.relative_to(config.project_root))})
    results["sources"]["inspections"] = _source_manifest(
        source="inspections",
        batch_id=batch_id,
        started_at=started_at,
        files=inspection_files,
        expected_rows=inspection_expected,
    )

    complaint_where = (
        f"({config.complaints.filter}) AND created_date >= "
        f"'{config.profile.start_date}T00:00:00.000'"
    )
    complaint_expected = client.count(config.complaints.endpoint, complaint_where)
    complaint_files: list[dict[str, Any]] = []
    for part_number, page in enumerate(
        client.pages(
            source="complaints",
            endpoint=config.complaints.endpoint,
            columns=COMPLAINT_COLUMNS,
            order_by=config.complaints.primary_order or "created_date DESC,unique_key DESC",
            where=complaint_where,
            page_size=config.profile.page_size,
            max_rows=config.profile.complaints_limit,
        )
    ):
        result = write_jsonl_gzip(
            raw_root=raw_root,
            source="complaints",
            batch_id=batch_id,
            part_number=part_number,
            rows=page.rows,
        )
        complaint_files.append({**asdict(result), "path": str(result.path.relative_to(config.project_root))})
    results["sources"]["complaints"] = _source_manifest(
        source="complaints",
        batch_id=batch_id,
        started_at=started_at,
        files=complaint_files,
        expected_rows=complaint_expected,
    )

    weather_rows = NOAAClient().daily_summaries(
        endpoint=config.weather.endpoint,
        station=config.weather.station or "USW00094728",
        start_date=config.profile.start_date,
        end_date=date.today().isoformat(),
    )
    weather_result = write_jsonl_gzip(
        raw_root=raw_root,
        source="weather",
        batch_id=batch_id,
        part_number=0,
        rows=weather_rows,
    )
    weather_files = [
        {
            **asdict(weather_result),
            "path": str(weather_result.path.relative_to(config.project_root)),
        }
    ]
    results["sources"]["weather"] = _source_manifest(
        source="weather",
        batch_id=batch_id,
        started_at=started_at,
        files=weather_files,
        expected_rows=None,
    )

    results["completed_at"] = datetime.now(UTC).isoformat()
    results["total_rows"] = sum(item["row_count"] for item in results["sources"].values())
    manifest_path = config.project_root / "artifacts" / "record_counts.json"
    write_manifest(manifest_path, results)
    return results

