from __future__ import annotations

import json
import time
from pathlib import Path

import duckdb


def timed(connection: duckdb.DuckDBPyConnection, sql: str) -> float:
    started = time.perf_counter()
    connection.execute(sql)
    return time.perf_counter() - started


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    database_path = root / "data" / "warehouse" / "restaurant_ops.duckdb"
    connection = duckdb.connect(str(database_path))
    try:
        connection.execute("DROP TABLE IF EXISTS benchmark_full")
        connection.execute("DROP TABLE IF EXISTS benchmark_incremental")
        full_seconds = timed(
            connection,
            "CREATE TABLE benchmark_full AS SELECT * FROM fct_complaint",
        )
        connection.execute(
            "CREATE TABLE benchmark_incremental AS SELECT * FROM fct_complaint WHERE FALSE"
        )
        connection.execute(
            "INSERT INTO benchmark_incremental SELECT * FROM fct_complaint USING SAMPLE 90 PERCENT"
        )
        incremental_seconds = timed(
            connection,
            """
            MERGE INTO benchmark_incremental target
            USING (
                SELECT * FROM fct_complaint
                ORDER BY complaint_id DESC
                LIMIT 10000
            ) source
            ON target.complaint_id = source.complaint_id
            WHEN MATCHED THEN UPDATE SET
                status = source.status,
                closed_date = source.closed_date,
                loaded_at = source.loaded_at
            WHEN NOT MATCHED THEN INSERT BY NAME
            """,
        )
        full_rows = connection.execute("SELECT COUNT(*) FROM benchmark_full").fetchone()[0]
        incremental_rows = connection.execute(
            "SELECT COUNT(*) FROM benchmark_incremental"
        ).fetchone()[0]
    finally:
        connection.close()

    speedup = full_seconds / incremental_seconds if incremental_seconds else None
    payload = {
        "benchmark_engine": "DuckDB local evidence path",
        "full_refresh_rows": int(full_rows),
        "incremental_candidate_rows": 10000,
        "post_merge_rows": int(incremental_rows),
        "full_refresh_seconds": round(full_seconds, 6),
        "incremental_merge_seconds": round(incremental_seconds, 6),
        "speedup_ratio": round(speedup, 2) if speedup is not None else None,
        "claim_boundary": "Local benchmark; Snowflake runtime must be measured after deployment.",
    }
    (root / "artifacts" / "incremental_benchmark.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()

