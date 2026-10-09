from __future__ import annotations

import gzip
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RawFileResult:
    path: Path
    row_count: int
    sha256: str
    source: str
    batch_id: str


def utc_now() -> datetime:
    return datetime.now(UTC)


def build_batch_id(timestamp: datetime | None = None) -> str:
    value = timestamp or utc_now()
    return value.strftime("%Y%m%dT%H%M%SZ")


def write_jsonl_gzip(
    *,
    raw_root: Path,
    source: str,
    batch_id: str,
    part_number: int,
    rows: list[dict[str, Any]],
    retrieved_at: datetime | None = None,
) -> RawFileResult:
    retrieved = retrieved_at or utc_now()
    partition = (
        raw_root
        / f"source={source}"
        / f"ingest_date={retrieved.date().isoformat()}"
        / f"batch_id={batch_id}"
    )
    partition.mkdir(parents=True, exist_ok=True)
    path = partition / f"part-{part_number:05d}.jsonl.gz"
    digest = hashlib.sha256()
    with gzip.open(path, "wt", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            enriched = {
                **row,
                "_source": source,
                "_batch_id": batch_id,
                "_retrieved_at": retrieved.isoformat(),
            }
            line = json.dumps(enriched, ensure_ascii=False, separators=(",", ":"))
            handle.write(line + "\n")
            digest.update((line + "\n").encode("utf-8"))
    return RawFileResult(
        path=path,
        row_count=len(rows),
        sha256=digest.hexdigest(),
        source=source,
        batch_id=batch_id,
    )


def write_manifest(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def discover_raw_files(raw_root: Path, source: str) -> list[Path]:
    return sorted(raw_root.glob(f"source={source}/ingest_date=*/batch_id=*/part-*.jsonl.gz"))

