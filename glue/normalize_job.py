"""AWS Glue 4/5 PySpark job for schema normalization and reject routing."""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator
from typing import Any

import boto3
from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from pyspark.sql import DataFrame, Row
from pyspark.sql import functions as F
from pyspark.sql.types import DoubleType


def stable_hash(*columns: str) -> Any:
    return F.sha2(F.concat_ws("|", *[F.coalesce(F.col(c).cast("string"), F.lit("")) for c in columns]), 256)


def send_rejections(rows: Iterator[Row], queue_url: str, source: str, batch_id: str) -> None:
    client = boto3.client("sqs")
    entries: list[dict[str, str]] = []
    counter = 0
    for row in rows:
        body = json.dumps(
            {
                "source": source,
                "batch_id": batch_id,
                "rejection_reason": row["rejection_reason"],
                "record": {k: v for k, v in row.asDict(recursive=True).items() if k != "raw_payload"},
            },
            default=str,
        )[:250_000]
        entries.append({"Id": str(counter), "MessageBody": body})
        counter += 1
        if len(entries) == 10:
            client.send_message_batch(QueueUrl=queue_url, Entries=entries)
            entries = []
            counter = 0
    if entries:
        client.send_message_batch(QueueUrl=queue_url, Entries=entries)


def normalize_inspections(frame: DataFrame) -> tuple[DataFrame, DataFrame]:
    normalized = (
        frame.withColumn("restaurant_id", F.trim("camis"))
        .withColumn("restaurant_name", F.trim("dba"))
        .withColumn("inspection_date", F.to_timestamp("inspection_date"))
        .withColumn("record_date", F.to_timestamp("record_date"))
        .withColumn("score", F.col("score").cast(DoubleType()))
        .withColumn("latitude", F.col("latitude").cast(DoubleType()))
        .withColumn("longitude", F.col("longitude").cast(DoubleType()))
        .withColumn("borough", F.upper(F.trim("boro")))
        .withColumn("address_normalized", F.upper(F.regexp_replace(F.concat_ws(" ", "building", "street"), "[^A-Z0-9 ]", " ")))
        .withColumn("location_key", stable_hash("borough", "address_normalized", "zipcode", "latitude", "longitude"))
        .withColumn("inspection_key", stable_hash("restaurant_id", "inspection_date", "inspection_type"))
        .withColumn("violation_key", stable_hash("inspection_key", "violation_code", "violation_description"))
        .withColumn(
            "source_row_key",
            stable_hash(
                "inspection_key",
                "violation_code",
                "violation_description",
                "action",
                "score",
                "grade",
                "record_date",
            ),
        )
    )
    invalid = normalized.filter(
        F.col("restaurant_id").isNull()
        | F.col("inspection_date").isNull()
        | (F.col("inspection_date") < F.to_timestamp(F.lit("2000-01-01")))
    ).withColumn(
        "rejection_reason",
        F.lit("missing restaurant_id or inspection_date before 2000-01-01"),
    )
    valid = normalized.subtract(invalid.drop("rejection_reason")).dropDuplicates(
        ["inspection_key", "violation_code", "violation_description", "record_date"]
    )
    return valid, invalid


def normalize_complaints(frame: DataFrame) -> tuple[DataFrame, DataFrame]:
    normalized = (
        frame.withColumn("complaint_id", F.trim("unique_key"))
        .withColumn("created_date", F.to_timestamp("created_date"))
        .withColumn("closed_date", F.to_timestamp("closed_date"))
        .withColumn("latitude", F.col("latitude").cast(DoubleType()))
        .withColumn("longitude", F.col("longitude").cast(DoubleType()))
        .withColumn("borough", F.upper(F.trim("borough")))
        .withColumn("address_normalized", F.upper(F.regexp_replace("incident_address", "[^A-Z0-9 ]", " ")))
        .withColumn("location_key", stable_hash("borough", "address_normalized", "incident_zip", "latitude", "longitude"))
    )
    invalid = normalized.filter(F.col("complaint_id").isNull() | F.col("created_date").isNull()).withColumn(
        "rejection_reason", F.lit("missing complaint_id or invalid created_date")
    )
    valid = normalized.subtract(invalid.drop("rejection_reason")).dropDuplicates(["complaint_id"])
    return valid, invalid


def normalize_weather(frame: DataFrame) -> tuple[DataFrame, DataFrame]:
    renamed = frame.select([F.col(c).alias(c.lower()) for c in frame.columns])
    normalized = (
        renamed.withColumn("station_id", F.trim("station"))
        .withColumn("weather_date", F.to_date("date"))
        .withColumn("temperature_max_f", F.col("tmax").cast(DoubleType()))
        .withColumn("temperature_min_f", F.col("tmin").cast(DoubleType()))
        .withColumn("precipitation_in", F.col("prcp").cast(DoubleType()))
        .withColumn("snowfall_in", F.col("snow").cast(DoubleType()))
        .withColumn("snow_depth_in", F.col("snwd").cast(DoubleType()))
        .withColumn("average_wind_mph", F.col("awnd").cast(DoubleType()))
        .withColumn("weather_key", stable_hash("station_id", "weather_date"))
    )
    invalid = normalized.filter(F.col("station_id").isNull() | F.col("weather_date").isNull()).withColumn(
        "rejection_reason", F.lit("missing station_id or invalid weather_date")
    )
    valid = normalized.subtract(invalid.drop("rejection_reason")).dropDuplicates(["weather_key"])
    return valid, invalid


args = getResolvedOptions(
    sys.argv,
    ["JOB_NAME", "SOURCE", "RAW_BUCKET", "CURATED_BUCKET", "DLQ_URL", "INGEST_DATE", "BATCH_ID"],
)
source = args["SOURCE"]
context = GlueContext(SparkContext.getOrCreate())
job = Job(context)
job.init(args["JOB_NAME"], args)
raw_path = (
    f"s3://{args['RAW_BUCKET']}/source={source}/ingest_date={args['INGEST_DATE']}/"
    f"batch_id={args['BATCH_ID']}/*.jsonl.gz"
)
frame = context.spark_session.read.json(raw_path)
normalizer = {
    "inspections": normalize_inspections,
    "complaints": normalize_complaints,
    "weather": normalize_weather,
}[source]
accepted, rejected = normalizer(frame)
accepted.write.mode("append").partitionBy("_batch_id").parquet(
    f"s3://{args['CURATED_BUCKET']}/{source}/"
)
if not rejected.rdd.isEmpty():
    rejected.write.mode("append").json(
        f"s3://{args['CURATED_BUCKET']}/rejected/source={source}/batch_id={args['BATCH_ID']}/"
    )
    rejected.foreachPartition(
        lambda rows: send_rejections(rows, args["DLQ_URL"], source, args["BATCH_ID"])
    )
print(json.dumps({
    "metric": "normalization_complete",
    "source": source,
    "batch_id": args["BATCH_ID"],
    "accepted_rows": accepted.count(),
    "rejected_rows": rejected.count(),
}))
job.commit()

