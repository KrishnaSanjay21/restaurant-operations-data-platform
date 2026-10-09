# Failure recovery runbook

1. Identify the failed Step Functions execution and preserve its `batch_id`.
2. Inspect CloudWatch logs for the ingestion Lambda, Glue job, and Snowflake loader.
3. Review the SQS dead-letter message. It contains the source, batch, execution,
   error, and original payload.
4. Correct credentials, schema drift, throttling, or malformed data. Invalid rows
   belong in the curated reject prefix; do not edit immutable raw objects.
5. Redrive the SQS message or start the state machine with the original date range
   and a new replay batch identifier.
6. Verify Snowflake `RAW.LOAD_AUDIT` source and loaded counts.
7. Run `dbt build` and `dbt source freshness`; all critical tests must pass.
8. Record the incident, root cause, replay batch, and evidence links.

Idempotency comes from deterministic business keys, raw batch partitions,
Snowflake batch auditing, and dbt `merge` incremental models. Replaying a range may
update a key but must not create duplicate facts.

