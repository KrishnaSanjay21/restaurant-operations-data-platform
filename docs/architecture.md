# Architecture

```mermaid
flowchart LR
    A[NYC Open Data APIs] --> L[Ingestion Lambda]
    B[NOAA NCEI API] --> L
    L --> R[(S3 raw<br/>source/date/batch)]
    L -. failed request .-> Q[SQS dead-letter queue]
    R --> G[AWS Glue normalization]
    G --> C[(S3 curated Parquet)]
    G -. invalid row .-> Q
    C --> S[(Snowflake RAW)]
    S --> D[dbt staging / intermediate / marts]
    D --> P[Power BI]
    F[Step Functions] --> L
    F --> G
    F --> S
    T[Terraform] -. provisions .-> R
    T -. provisions .-> F
    T -. provisions .-> Q
    M[CloudWatch logs and alarms] --- L
    M --- G
    M --- F
```

Raw objects are immutable, gzip-compressed JSON Lines and partitioned by `source`,
`ingest_date`, and `batch_id`. Glue standardizes types and writes curated Parquet.
The state machine applies bounded retries and routes terminal failures to SQS.
Snowflake preserves ingestion metadata and dbt builds the dimensional layer.

The local DuckDB evidence path implements the same logical dimensions, facts,
quality checks, and reporting marts without representing itself as a deployed AWS
or Snowflake environment.

