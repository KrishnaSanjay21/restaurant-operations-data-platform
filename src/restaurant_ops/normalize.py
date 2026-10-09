from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from restaurant_ops.storage import discover_raw_files


@dataclass(frozen=True)
class NormalizationResult:
    source: str
    accepted_rows: int
    rejected_rows: int
    duplicate_rows_removed: int
    output_path: Path
    rejected_path: Path | None


def _clean_text(series: pd.Series) -> pd.Series:
    return series.astype("string").str.strip().replace({"": pd.NA, "nan": pd.NA})


def _stable_hash(frame: pd.DataFrame, columns: list[str]) -> pd.Series:
    def digest(row: pd.Series) -> str:
        payload = "|".join("" if pd.isna(row.get(col)) else str(row.get(col)) for col in columns)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    return frame.apply(digest, axis=1)


def normalize_address(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = re.sub(r"[^A-Z0-9 ]+", " ", str(value).upper())
    text = re.sub(r"\s+", " ", text).strip()
    replacements = {
        " STREET": " ST",
        " AVENUE": " AVE",
        " BOULEVARD": " BLVD",
        " ROAD": " RD",
        " PLACE": " PL",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text or None


def _read_jsonl(files: list[Path]) -> pd.DataFrame:
    if not files:
        raise FileNotFoundError("No raw files were found for normalization")
    frames = [pd.read_json(path, lines=True, compression="gzip", dtype=False) for path in files]
    return pd.concat(frames, ignore_index=True, sort=False)


def normalize_inspections(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, int]:
    data = frame.copy()
    text_columns = [
        "camis",
        "dba",
        "boro",
        "building",
        "street",
        "zipcode",
        "phone",
        "cuisine_description",
        "action",
        "violation_code",
        "violation_description",
        "critical_flag",
        "grade",
        "inspection_type",
        "community_board",
        "council_district",
        "census_tract",
        "bin",
        "bbl",
        "nta",
    ]
    for column in text_columns:
        if column not in data:
            data[column] = pd.NA
        data[column] = _clean_text(data[column])

    for column in ["inspection_date", "grade_date", "record_date", "_retrieved_at"]:
        data[column] = pd.to_datetime(data.get(column), errors="coerce", utc=True)
    for column in ["score", "latitude", "longitude"]:
        data[column] = pd.to_numeric(data.get(column), errors="coerce")

    data["restaurant_id"] = data["camis"]
    data["restaurant_name"] = data["dba"]
    data["borough"] = data["boro"].str.upper()
    data["address_normalized"] = (
        data["building"].fillna("") + " " + data["street"].fillna("")
    ).map(normalize_address)
    data["location_key"] = _stable_hash(
        data, ["borough", "address_normalized", "zipcode", "latitude", "longitude"]
    )
    data["inspection_key"] = _stable_hash(
        data, ["restaurant_id", "inspection_date", "inspection_type"]
    )
    data["violation_key"] = _stable_hash(
        data, ["inspection_key", "violation_code", "violation_description"]
    )
    data["source_row_key"] = _stable_hash(
        data,
        [
            "inspection_key",
            "violation_code",
            "violation_description",
            "action",
            "score",
            "grade",
            "record_date",
        ],
    )
    minimum_valid_date = pd.Timestamp("2000-01-01", tz="UTC")
    invalid = (
        data["restaurant_id"].isna()
        | data["inspection_date"].isna()
        | (data["inspection_date"] < minimum_valid_date)
    )
    rejected = data.loc[invalid].copy()
    rejected["rejection_reason"] = (
        "missing restaurant_id or inspection_date before 2000-01-01"
    )
    accepted = data.loc[~invalid].copy()
    before = len(accepted)
    accepted = accepted.drop_duplicates(subset=["source_row_key"], keep="last")
    duplicates = before - len(accepted)
    return accepted, rejected, duplicates


def normalize_complaints(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, int]:
    data = frame.copy()
    text_columns = [
        "unique_key",
        "agency",
        "agency_name",
        "complaint_type",
        "descriptor",
        "location_type",
        "incident_zip",
        "incident_address",
        "street_name",
        "city",
        "status",
        "resolution_description",
        "borough",
        "open_data_channel_type",
    ]
    for column in text_columns:
        if column not in data:
            data[column] = pd.NA
        data[column] = _clean_text(data[column])
    for column in ["created_date", "closed_date", "_retrieved_at"]:
        data[column] = pd.to_datetime(data.get(column), errors="coerce", utc=True)
    for column in ["latitude", "longitude"]:
        data[column] = pd.to_numeric(data.get(column), errors="coerce")

    data["complaint_id"] = data["unique_key"]
    data["borough"] = data["borough"].str.upper()
    data["address_normalized"] = data["incident_address"].map(normalize_address)
    data["location_key"] = _stable_hash(
        data, ["borough", "address_normalized", "incident_zip", "latitude", "longitude"]
    )
    invalid = data["complaint_id"].isna() | data["created_date"].isna()
    rejected = data.loc[invalid].copy()
    rejected["rejection_reason"] = "missing complaint_id or invalid created_date"
    accepted = data.loc[~invalid].copy()
    before = len(accepted)
    accepted = accepted.sort_values("_retrieved_at").drop_duplicates(
        subset=["complaint_id"], keep="last"
    )
    duplicates = before - len(accepted)
    return accepted, rejected, duplicates


def normalize_weather(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, int]:
    data = frame.rename(columns=str.lower).copy()
    data["weather_date"] = pd.to_datetime(data.get("date"), errors="coerce", utc=True)
    data["station_id"] = _clean_text(data.get("station", pd.Series(dtype="string")))
    mappings = {
        "tmax": "temperature_max_f",
        "tmin": "temperature_min_f",
        "prcp": "precipitation_in",
        "snow": "snowfall_in",
        "snwd": "snow_depth_in",
        "awnd": "average_wind_mph",
    }
    for source, target in mappings.items():
        data[target] = pd.to_numeric(data.get(source), errors="coerce")
    data["weather_key"] = _stable_hash(data, ["station_id", "weather_date"])
    invalid = data["station_id"].isna() | data["weather_date"].isna()
    rejected = data.loc[invalid].copy()
    rejected["rejection_reason"] = "missing station_id or invalid weather_date"
    accepted = data.loc[~invalid].copy()
    before = len(accepted)
    accepted = accepted.drop_duplicates(subset=["weather_key"], keep="last")
    return accepted, rejected, before - len(accepted)


def normalize_source(project_root: Path, source: str) -> NormalizationResult:
    raw_files = discover_raw_files(project_root / "data" / "raw", source)
    frame = _read_jsonl(raw_files)
    if source == "inspections":
        accepted, rejected, duplicates = normalize_inspections(frame)
    elif source == "complaints":
        accepted, rejected, duplicates = normalize_complaints(frame)
    elif source == "weather":
        accepted, rejected, duplicates = normalize_weather(frame)
    else:
        raise ValueError(f"Unsupported source: {source}")

    curated_dir = project_root / "data" / "curated"
    curated_dir.mkdir(parents=True, exist_ok=True)
    output_path = curated_dir / f"{source}.parquet"
    accepted.to_parquet(output_path, index=False)
    rejected_path: Path | None = None
    if not rejected.empty:
        rejected_path = curated_dir / f"{source}_rejected.parquet"
        rejected.to_parquet(rejected_path, index=False)

    return NormalizationResult(
        source=source,
        accepted_rows=len(accepted),
        rejected_rows=len(rejected),
        duplicate_rows_removed=duplicates,
        output_path=output_path,
        rejected_path=rejected_path,
    )


def normalize_all(project_root: Path) -> dict[str, Any]:
    results = [normalize_source(project_root, source) for source in ("inspections", "complaints", "weather")]
    payload = {
        item.source: {
            "accepted_rows": item.accepted_rows,
            "rejected_rows": item.rejected_rows,
            "duplicate_rows_removed": item.duplicate_rows_removed,
            "output_path": str(item.output_path.relative_to(project_root)),
            "rejected_path": str(item.rejected_path.relative_to(project_root)) if item.rejected_path else None,
        }
        for item in results
    }
    (project_root / "artifacts" / "normalization_report.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )
    return payload

