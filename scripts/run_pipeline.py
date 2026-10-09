from __future__ import annotations

import argparse
import json
from pathlib import Path

from benchmark_incremental import main as benchmark_incremental
from build_dashboard_assets import main as build_dashboard_assets
from generate_pbip import make_model, make_report

from restaurant_ops.config import load_config
from restaurant_ops.ingest import ingest_public_sources
from restaurant_ops.normalize import normalize_all
from restaurant_ops.warehouse import build_local_warehouse, run_quality_checks


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest and normalize public restaurant data")
    parser.add_argument("--profile", choices=("sample", "portfolio"), default="sample")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    ingestion = ingest_public_sources(load_config(root, args.profile))
    normalization = normalize_all(root)
    warehouse = build_local_warehouse(root)
    quality = run_quality_checks(root)
    benchmark_incremental()
    build_dashboard_assets()
    make_model()
    make_report()
    print(json.dumps({
        "ingestion": ingestion,
        "normalization": normalization,
        "warehouse": warehouse,
        "quality": quality,
    }, indent=2))


if __name__ == "__main__":
    main()

