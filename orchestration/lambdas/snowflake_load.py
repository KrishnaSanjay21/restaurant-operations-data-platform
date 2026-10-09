"""Start Snowflake ingestion after curated files are ready.

Package this handler with ``snowflake-connector-python`` in a Lambda layer. The
Snowflake password is read at runtime from AWS Secrets Manager and is never
stored in the state machine input or logs.
"""

from __future__ import annotations

import json
import os
from typing import Any

import boto3
import snowflake.connector

SECRETS = boto3.client("secretsmanager")


def handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    secret = json.loads(
        SECRETS.get_secret_value(SecretId=os.environ["SNOWFLAKE_SECRET_ARN"])["SecretString"]
    )
    connection = snowflake.connector.connect(
        account=secret["account"],
        user=secret["user"],
        password=secret["password"],
        warehouse=secret.get("warehouse", "RESTAURANT_OPS_WH"),
        database=secret.get("database", "RESTAURANT_OPS"),
        schema="RAW",
        role=secret.get("role", "RESTAURANT_OPS_LOADER"),
    )
    batch_id = event["batch_id"]
    source_counts = {
        item["source"].upper(): int(item.get("row_count", 0))
        for item in event.get("source_results", [])
    }
    try:
        cursor = connection.cursor()
        cursor.execute(
            "CALL RAW.LOAD_CURATED_BATCH(%s, PARSE_JSON(%s))",
            (batch_id, json.dumps(source_counts)),
        )
        result = cursor.fetchone()
    finally:
        connection.close()
    return {**event, "snowflake_result": result[0] if result else "completed"}

