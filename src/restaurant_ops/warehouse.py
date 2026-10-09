from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import duckdb

MODEL_SQL = r"""
CREATE OR REPLACE TABLE dim_restaurant AS
WITH ranked AS (
    SELECT
        restaurant_id,
        restaurant_name,
        cuisine_description,
        phone,
        location_key,
        borough,
        building,
        street,
        zipcode,
        latitude,
        longitude,
        record_date,
        ROW_NUMBER() OVER (
            PARTITION BY restaurant_id
            ORDER BY record_date DESC NULLS LAST, _retrieved_at DESC NULLS LAST
        ) AS row_num
    FROM curated_inspections
)
SELECT * EXCLUDE (row_num) FROM ranked WHERE row_num = 1;

CREATE OR REPLACE TABLE dim_location AS
WITH locations AS (
    SELECT DISTINCT
        location_key,
        borough,
        address_normalized,
        zipcode AS postal_code,
        latitude,
        longitude,
        'RESTAURANT' AS source_type
    FROM curated_inspections
    UNION ALL
    SELECT DISTINCT
        location_key,
        borough,
        address_normalized,
        incident_zip AS postal_code,
        latitude,
        longitude,
        'COMPLAINT' AS source_type
    FROM curated_complaints
), ranked AS (
    SELECT *, ROW_NUMBER() OVER (
        PARTITION BY location_key
        ORDER BY CASE WHEN source_type = 'RESTAURANT' THEN 0 ELSE 1 END
    ) AS row_num
    FROM locations
)
SELECT * EXCLUDE (row_num) FROM ranked WHERE row_num = 1;

CREATE OR REPLACE TABLE dim_date AS
WITH bounds AS (
    SELECT MIN(event_date) AS min_date, MAX(event_date) AS max_date
    FROM (
        SELECT CAST(inspection_date AS DATE) AS event_date FROM curated_inspections
        UNION ALL
        SELECT CAST(created_date AS DATE) FROM curated_complaints
        UNION ALL
        SELECT CAST(weather_date AS DATE) FROM curated_weather
    )
), dates AS (
    SELECT CAST(day AS DATE) AS date_key
    FROM bounds, range(min_date, max_date + INTERVAL 1 DAY, INTERVAL 1 DAY) t(day)
)
SELECT
    date_key,
    YEAR(date_key) AS year,
    QUARTER(date_key) AS quarter,
    MONTH(date_key) AS month,
    STRFTIME(date_key, '%B') AS month_name,
    WEEKOFYEAR(date_key) AS week_of_year,
    DAYOFWEEK(date_key) AS day_of_week,
    STRFTIME(date_key, '%A') AS day_name,
    CASE WHEN DAYOFWEEK(date_key) IN (0, 6) THEN TRUE ELSE FALSE END AS is_weekend
FROM dates;

CREATE OR REPLACE TABLE dim_violation AS
WITH ranked AS (
    SELECT
        violation_code,
        violation_description,
        critical_flag,
        ROW_NUMBER() OVER (
            PARTITION BY violation_code
            ORDER BY record_date DESC NULLS LAST
        ) AS row_num
    FROM curated_inspections
    WHERE violation_code IS NOT NULL
)
SELECT * EXCLUDE (row_num) FROM ranked WHERE row_num = 1;

CREATE OR REPLACE TABLE fct_inspection AS
SELECT
    inspection_key,
    restaurant_id,
    location_key,
    CAST(inspection_date AS DATE) AS inspection_date,
    inspection_type,
    MAX(action) AS action,
    MAX(score) AS score,
    MAX(grade) AS grade,
    MAX(CAST(grade_date AS DATE)) AS grade_date,
    COUNT(DISTINCT violation_key) FILTER (WHERE violation_code IS NOT NULL) AS violation_count,
    COUNT(DISTINCT violation_key) FILTER (WHERE critical_flag = 'Critical') AS critical_violation_count,
    MAX(record_date) AS source_record_date,
    MAX(_retrieved_at) AS loaded_at
FROM curated_inspections
GROUP BY ALL;

CREATE OR REPLACE TABLE fct_violation AS
SELECT DISTINCT
    violation_key,
    inspection_key,
    restaurant_id,
    location_key,
    violation_code,
    violation_description,
    critical_flag,
    CAST(inspection_date AS DATE) AS violation_date,
    _retrieved_at AS loaded_at
FROM curated_inspections
WHERE violation_code IS NOT NULL;

CREATE OR REPLACE TABLE fct_complaint AS
WITH restaurant_addresses AS (
    SELECT
        restaurant_id,
        address_normalized,
        zipcode,
        ROW_NUMBER() OVER (
            PARTITION BY address_normalized, zipcode
            ORDER BY record_date DESC NULLS LAST
        ) AS row_num
    FROM curated_inspections
    WHERE address_normalized IS NOT NULL AND zipcode IS NOT NULL
), restaurant_match AS (
    SELECT * EXCLUDE (row_num) FROM restaurant_addresses WHERE row_num = 1
)
SELECT
    c.complaint_id,
    r.restaurant_id,
    c.location_key,
    CAST(c.created_date AS DATE) AS complaint_date,
    c.created_date,
    c.closed_date,
    c.complaint_type,
    c.descriptor,
    c.location_type,
    c.status,
    c.resolution_description,
    c.borough,
    c.incident_zip,
    c.latitude,
    c.longitude,
    c.open_data_channel_type,
    CASE WHEN r.restaurant_id IS NOT NULL THEN 'EXACT_ADDRESS_ZIP' ELSE 'UNMATCHED' END AS restaurant_match_method,
    c._retrieved_at AS loaded_at
FROM curated_complaints c
LEFT JOIN restaurant_match r
    ON c.address_normalized = r.address_normalized
   AND c.incident_zip = r.zipcode;

CREATE OR REPLACE TABLE fct_weather AS
SELECT
    weather_key,
    station_id,
    CAST(weather_date AS DATE) AS weather_date,
    temperature_max_f,
    temperature_min_f,
    precipitation_in,
    snowfall_in,
    snow_depth_in,
    average_wind_mph,
    _retrieved_at AS loaded_at
FROM curated_weather;

CREATE OR REPLACE TABLE rpt_restaurant_risk AS
WITH inspection_metrics AS (
    SELECT
        restaurant_id,
        COUNT(*) AS inspection_count,
        SUM(violation_count) AS violation_count,
        SUM(critical_violation_count) AS critical_violation_count,
        AVG(score) AS average_inspection_score,
        MAX(inspection_date) AS latest_inspection_date,
        ARG_MAX(grade, inspection_date) AS latest_grade
    FROM fct_inspection
    GROUP BY restaurant_id
), complaint_metrics AS (
    SELECT
        restaurant_id,
        COUNT(*) AS matched_complaint_count,
        COUNT(*) FILTER (WHERE complaint_type = 'Food Poisoning') AS food_poisoning_complaints,
        COUNT(*) FILTER (WHERE complaint_type = 'Rodent') AS rodent_complaints
    FROM fct_complaint
    WHERE restaurant_id IS NOT NULL
    GROUP BY restaurant_id
)
SELECT
    r.restaurant_id,
    r.restaurant_name,
    r.cuisine_description,
    r.borough,
    r.zipcode,
    r.location_key,
    i.inspection_count,
    i.violation_count,
    i.critical_violation_count,
    ROUND(i.average_inspection_score, 2) AS average_inspection_score,
    i.latest_inspection_date,
    i.latest_grade,
    COALESCE(c.matched_complaint_count, 0) AS matched_complaint_count,
    COALESCE(c.food_poisoning_complaints, 0) AS food_poisoning_complaints,
    COALESCE(c.rodent_complaints, 0) AS rodent_complaints,
    ROUND(
        COALESCE(i.average_inspection_score, 0) * 2
        + COALESCE(i.critical_violation_count, 0) * 3
        + COALESCE(c.matched_complaint_count, 0) * 2,
        2
    ) AS risk_score,
    CASE
        WHEN risk_score >= 80 THEN 'CRITICAL'
        WHEN risk_score >= 50 THEN 'HIGH'
        WHEN risk_score >= 25 THEN 'MEDIUM'
        ELSE 'LOW'
    END AS risk_tier
FROM dim_restaurant r
LEFT JOIN inspection_metrics i USING (restaurant_id)
LEFT JOIN complaint_metrics c USING (restaurant_id);

CREATE OR REPLACE TABLE rpt_daily_operations AS
SELECT
    d.date_key,
    COUNT(DISTINCT i.inspection_key) AS inspections,
    COALESCE(SUM(i.violation_count), 0) AS violations,
    COALESCE(SUM(i.critical_violation_count), 0) AS critical_violations,
    COUNT(DISTINCT c.complaint_id) AS complaints,
    COUNT(DISTINCT c.complaint_id) FILTER (WHERE c.complaint_type = 'Food Poisoning') AS food_poisoning_complaints,
    MAX(w.temperature_max_f) AS temperature_max_f,
    MAX(w.precipitation_in) AS precipitation_in,
    MAX(w.snowfall_in) AS snowfall_in
FROM dim_date d
LEFT JOIN fct_inspection i ON d.date_key = i.inspection_date
LEFT JOIN fct_complaint c ON d.date_key = c.complaint_date
LEFT JOIN fct_weather w ON d.date_key = w.weather_date
GROUP BY d.date_key;
"""


def _table_count(connection: duckdb.DuckDBPyConnection, table: str) -> int:
    return int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def build_local_warehouse(project_root: Path) -> dict[str, Any]:
    curated = project_root / "data" / "curated"
    database_path = project_root / "data" / "warehouse" / "restaurant_ops.duckdb"
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect(str(database_path))
    started = time.perf_counter()
    try:
        for source in ("inspections", "complaints", "weather"):
            parquet_path = (curated / f"{source}.parquet").as_posix().replace("'", "''")
            connection.execute(
                f"CREATE OR REPLACE VIEW curated_{source} AS SELECT * FROM read_parquet('{parquet_path}')"
            )
        connection.execute(MODEL_SQL)
        tables = [
            "dim_restaurant",
            "dim_location",
            "dim_date",
            "dim_violation",
            "fct_inspection",
            "fct_violation",
            "fct_complaint",
            "fct_weather",
            "rpt_restaurant_risk",
            "rpt_daily_operations",
        ]
        counts = {table: _table_count(connection, table) for table in tables}
        exports = project_root / "data" / "warehouse" / "powerbi"
        exports.mkdir(parents=True, exist_ok=True)
        for table in ("rpt_restaurant_risk", "rpt_daily_operations", "dim_restaurant", "dim_location"):
            output = (exports / f"{table}.parquet").as_posix().replace("'", "''")
            connection.execute(f"COPY {table} TO '{output}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    finally:
        connection.close()
    payload = {
        "database": str(database_path.relative_to(project_root)),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "table_counts": counts,
    }
    (project_root / "artifacts" / "warehouse_build.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )
    return payload


def run_quality_checks(project_root: Path) -> dict[str, Any]:
    database_path = project_root / "data" / "warehouse" / "restaurant_ops.duckdb"
    connection = duckdb.connect(str(database_path), read_only=True)
    checks = {
        "dim_restaurant_unique": "SELECT COUNT(*) = COUNT(DISTINCT restaurant_id) FROM dim_restaurant",
        "inspection_key_unique": "SELECT COUNT(*) = COUNT(DISTINCT inspection_key) FROM fct_inspection",
        "violation_key_unique": "SELECT COUNT(*) = COUNT(DISTINCT violation_key) FROM fct_violation",
        "complaint_key_unique": "SELECT COUNT(*) = COUNT(DISTINCT complaint_id) FROM fct_complaint",
        "weather_key_unique": "SELECT COUNT(*) = COUNT(DISTINCT weather_key) FROM fct_weather",
        "inspection_restaurant_not_null": "SELECT COUNT(*) = 0 FROM fct_inspection WHERE restaurant_id IS NULL",
        "inspection_restaurant_relationship": """
            SELECT COUNT(*) = 0 FROM fct_inspection f
            LEFT JOIN dim_restaurant d USING (restaurant_id)
            WHERE d.restaurant_id IS NULL
        """,
        "violation_inspection_relationship": """
            SELECT COUNT(*) = 0 FROM fct_violation v
            LEFT JOIN fct_inspection i USING (inspection_key)
            WHERE i.inspection_key IS NULL
        """,
        "risk_tier_accepted_values": """
            SELECT COUNT(*) = 0 FROM rpt_restaurant_risk
            WHERE risk_tier NOT IN ('LOW','MEDIUM','HIGH','CRITICAL')
        """,
        "nonnegative_inspection_scores": "SELECT COUNT(*) = 0 FROM fct_inspection WHERE score < 0",
    }
    try:
        results = {
            name: {"passed": bool(connection.execute(sql).fetchone()[0]), "sql": " ".join(sql.split())}
            for name, sql in checks.items()
        }
    finally:
        connection.close()
    payload = {
        "critical_check_count": len(results),
        "critical_pass_count": sum(item["passed"] for item in results.values()),
        "all_critical_checks_passed": all(item["passed"] for item in results.values()),
        "checks": results,
    }
    (project_root / "artifacts" / "quality_report.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )
    return payload

