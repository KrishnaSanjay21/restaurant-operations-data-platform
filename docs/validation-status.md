# Validation status

Verified locally on 2026-10-09 using the published NYC and NOAA APIs.

| Target | Result | Status |
|---|---:|---|
| Process at least 500,000 real API rows | 577,630 | Pass |
| Critical quality tests | 10 / 10 | Pass |
| Unique complaint facts after replay | 361,938 | Pass |
| Unique inspection facts | 93,347 | Pass |
| Unique violation facts | 289,486 | Pass |
| Local full-refresh runtime | 1.634419 seconds | Measured |
| Local 10,000-row incremental merge | 0.249280 seconds | Measured |
| Local runtime improvement | 6.56× | Pass |
| Dashboard preview and PBIP generated | Yes | Pass |

The ingestion manifest records 296,507 inspection rows, 275,000 selected 311
complaints, and 6,123 NOAA daily observations in the validated batch. The local
replay also included earlier immutable partitions; deterministic keys collapsed
overlap into 361,938 unique complaint facts.

The inspection source contains placeholder dates in 1900. The normalization rule
routes those batch occurrences to the reject file, preventing them from distorting
the operational trend. Repeated rejected occurrences remain visible in replay
metrics rather than being silently discarded.

## Claim boundaries

- Python tests, Ruff, the local DuckDB warehouse, quality checks, evidence-scale
  ingestion, dashboard assets, and PBIP generation were executed locally.
- Terraform was not locally validated because the Terraform CLI is not installed
  on this machine; the GitHub CI workflow performs `fmt`, `init -backend=false`,
  and `validate` where Terraform is available.
- dbt 1.12 parsed the complete Snowflake project successfully without warnings;
  actual `dbt build`, AWS resource creation, Snowflake loading, Power BI publishing,
  and scheduled refresh require the operator's credentials and are not represented
  as deployed.

Machine-readable evidence is stored in `artifacts/validation_summary.json`,
`record_counts.json`, `quality_report.json`, `warehouse_build.json`, and
`incremental_benchmark.json`.

