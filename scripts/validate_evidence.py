from __future__ import annotations

import json
from pathlib import Path


def read_json(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"Missing evidence artifact: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    counts = read_json(root / "artifacts" / "record_counts.json")
    quality = read_json(root / "artifacts" / "quality_report.json")
    benchmark = read_json(root / "artifacts" / "incremental_benchmark.json")
    observed = int(counts["total_rows"])
    checks = {
        "minimum_500k_raw_records": observed >= 500_000,
        "all_critical_quality_checks_pass": bool(quality["all_critical_checks_passed"]),
        "incremental_runtime_is_faster": benchmark["incremental_merge_seconds"] < benchmark["full_refresh_seconds"],
        "dashboard_preview_exists": (root / "dashboard" / "executive-dashboard.png").is_file(),
        "power_bi_project_exists": (root / "powerbi" / "RestaurantOperations.pbip").is_file(),
    }
    payload = {
        "observed_raw_records": observed,
        "critical_checks_passed": quality["critical_pass_count"],
        "critical_checks_total": quality["critical_check_count"],
        "checks": checks,
        "all_targets_met": all(checks.values()),
    }
    target = root / "artifacts" / "validation_summary.json"
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    if not payload["all_targets_met"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

