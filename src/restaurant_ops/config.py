from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class SourceConfig:
    name: str
    endpoint: str
    dataset_id: str | None = None
    filter: str | None = None
    primary_order: str | None = None
    station: str | None = None
    station_name: str | None = None
    dataset: str | None = None


@dataclass(frozen=True)
class ProfileConfig:
    name: str
    inspections_limit: int
    complaints_limit: int
    page_size: int
    start_date: str


@dataclass(frozen=True)
class PipelineConfig:
    project_root: Path
    minimum_portfolio_records: int
    timezone: str
    profile: ProfileConfig
    inspections: SourceConfig
    complaints: SourceConfig
    weather: SourceConfig
    raw: dict[str, Any]


def load_config(
    project_root: Path,
    profile_name: str = "sample",
    config_path: Path | None = None,
) -> PipelineConfig:
    path = config_path or project_root / "config" / "pipeline.yml"
    with path.open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)

    if profile_name not in raw["profiles"]:
        valid = ", ".join(sorted(raw["profiles"]))
        raise ValueError(f"Unknown profile {profile_name!r}; choose one of: {valid}")

    profile = raw["profiles"][profile_name]
    sources = raw["sources"]
    return PipelineConfig(
        project_root=project_root,
        minimum_portfolio_records=int(raw["project"]["minimum_portfolio_records"]),
        timezone=str(raw["project"]["timezone"]),
        profile=ProfileConfig(
            name=profile_name,
            inspections_limit=int(profile["inspections_limit"]),
            complaints_limit=int(profile["complaints_limit"]),
            page_size=int(profile["page_size"]),
            start_date=str(profile["start_date"]),
        ),
        inspections=SourceConfig(name="inspections", **sources["inspections"]),
        complaints=SourceConfig(name="complaints", **sources["complaints"]),
        weather=SourceConfig(name="weather", **sources["weather"]),
        raw=raw,
    )

