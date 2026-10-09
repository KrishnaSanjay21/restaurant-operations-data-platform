# Restaurant Operations Data Platform

An evidence-backed AWS–Snowflake–dbt portfolio project built from real NYC Open Data and NOAA records.

```text
NYC Open Data + NOAA NCEI
          │
          ▼
 partitioned AWS S3 raw zone
          │
          ▼
 AWS Step Functions ── retries / replay / SQS DLQ
          │
          ▼
 AWS Glue normalization and data-quality routing
          │
          ▼
 Snowflake RAW → dbt staging → intermediate → marts
          │
          ▼
 Power BI restaurant-risk and operations dashboard
```

## What is implemented

- Paginated, restartable ingestion for NYC restaurant inspections and selected DOHMH 311 complaints.
- Token-free NOAA NCEI daily-weather ingestion for Central Park station `USW00094728`.
- Hive-style raw partitions such as `source=inspections/ingest_date=YYYY-MM-DD/batch_id=.../`.
- AWS Glue normalization with rejected-row routing to an SQS dead-letter queue.
- Step Functions orchestration with retries, failure capture, and historical replay parameters.
- Snowflake file format, external-stage template, audited batch loader, and monitoring views.
- dbt staging, intermediate, and dimensional marts with incremental models and critical tests.
- Terraform for S3, IAM, Glue, Step Functions, SQS, EventBridge, CloudWatch, and encryption.
- GitHub Actions for Python, Terraform, dbt validation, and controlled deployment.
- A local DuckDB evidence path that runs without cloud credentials and exports Power BI-ready tables.

## Real data sources

| Source | Public dataset | Role |
|---|---|---|
| NYC DOHMH | Restaurant Inspection Results (`43nn-pn8j`) | Restaurants, inspections, violations, scores, grades |
| NYC 311 | Service Requests from 2010 to Present (`erm2-nwe9`) | Food, vendor, rodent, and food-poisoning complaints |
| NOAA NCEI | Daily Summaries, Central Park (`USW00094728`) | Temperature, precipitation, snow, and wind controls |

The default `portfolio` profile downloads all available inspection rows and the 275,000 most recent relevant complaint rows. The verified October 2026 run processed **577,630 public API rows** before deduplication and created a complete 361,938-row complaint fact by safely replaying overlapping historical batches. Large raw and curated files are intentionally excluded from Git.

## Quick start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev,dashboard]"
python scripts/run_pipeline.py --profile sample
pytest
```

Run the evidence-scale profile:

```powershell
python scripts/run_pipeline.py --profile portfolio
python scripts/validate_evidence.py
```

Optional Socrata app tokens improve rate limits:

```powershell
$env:NYC_APP_TOKEN="your-token"
```

The NOAA Access Data Service used here does not require a token. `NOAA_TOKEN` is reserved for teams that switch to the CDO v2 API.

## Cloud deployment

Cloud resources are defined but are **not represented as deployed** in this repository. Deployment requires the operator's AWS and Snowflake accounts, credentials, budgets, and approvals. See [deployment.md](docs/deployment.md) and [failure-recovery.md](docs/failure-recovery.md).

## Evidence and claims

- Source rows and retrieval timestamps are written to `artifacts/record_counts.json`.
- Data-quality outcomes are written to `artifacts/quality_report.json`.
- Full-refresh and incremental timings are written to `artifacts/incremental_benchmark.json`.
- The measurable-target status is summarized in [validation-status.md](docs/validation-status.md).

Verified local evidence: 577,630 ingested rows, 10/10 passing critical checks,
361,938 unique complaint facts, 93,347 inspection facts, and a 6.56× runtime
improvement for the 10,000-row incremental benchmark versus its full refresh.

## Repository map

| Path | Purpose |
|---|---|
| `src/restaurant_ops/` | Public API clients, raw storage, normalization, local evidence path |
| `glue/` | Production-oriented PySpark normalization job |
| `orchestration/` | Step Functions definition and support Lambda handlers |
| `snowflake/` | Database objects, stages, loading, streams, and tasks |
| `dbt/restaurant_ops/` | dbt project with staging, intermediate, and reporting marts |
| `terraform/aws/` | Reproducible AWS infrastructure |
| `powerbi/` | Source-controlled PBIP, semantic measures, and dashboard specification |
| `docs/` | Architecture, data dictionary, runbooks, replay, KPIs, and evidence |

## Accuracy note

This is a portfolio implementation using public records. AWS, Snowflake, and Power BI deployment evidence must be added by the person who deploys it. Local execution proves ingestion, transformations, idempotency, quality rules, and reporting outputs; it does not prove production operation in another organization.

