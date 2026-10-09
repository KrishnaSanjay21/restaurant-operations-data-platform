from __future__ import annotations

import json
from pathlib import Path

import typer

from restaurant_ops.config import load_config
from restaurant_ops.ingest import ingest_public_sources
from restaurant_ops.normalize import normalize_all
from restaurant_ops.warehouse import build_local_warehouse, run_quality_checks

app = typer.Typer(no_args_is_help=True)


def root() -> Path:
    return Path(__file__).resolve().parents[2]


@app.command()
def ingest(profile: str = "sample") -> None:
    result = ingest_public_sources(load_config(root(), profile))
    typer.echo(json.dumps(result, indent=2))


@app.command()
def normalize() -> None:
    typer.echo(json.dumps(normalize_all(root()), indent=2))


@app.command("build-warehouse")
def build_warehouse() -> None:
    result = build_local_warehouse(root())
    result["quality"] = run_quality_checks(root())
    typer.echo(json.dumps(result, indent=2))


@app.command()
def run(profile: str = "sample") -> None:
    result = {
        "ingestion": ingest_public_sources(load_config(root(), profile)),
        "normalization": normalize_all(root()),
        "warehouse": build_local_warehouse(root()),
        "quality": run_quality_checks(root()),
    }
    typer.echo(json.dumps(result, indent=2))


if __name__ == "__main__":
    app()

