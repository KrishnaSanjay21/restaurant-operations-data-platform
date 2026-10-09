.PHONY: install test lint sample full transform benchmark dashboard

install:
	python -m pip install -e ".[dev,dashboard]"

test:
	pytest

lint:
	ruff check .

sample:
	python scripts/run_pipeline.py --profile sample

full:
	python scripts/run_pipeline.py --profile portfolio

transform:
	python scripts/build_local_warehouse.py

benchmark:
	python scripts/benchmark_incremental.py

dashboard:
	python scripts/build_dashboard_assets.py

