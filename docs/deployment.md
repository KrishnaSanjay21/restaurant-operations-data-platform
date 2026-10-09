# Deployment guide

## Local evidence run

```bash
python -m venv .venv
python -m pip install -e ".[dev,dashboard]"
python scripts/run_pipeline.py --profile sample
```

Use `--profile portfolio` to execute the 500,000+ record validation. Outputs are
written to `artifacts/`, `dashboard/`, and ignored local data folders.

## AWS and Snowflake

1. Create a Snowflake secret in AWS Secrets Manager and a Lambda layer containing
   `snowflake-connector-python`.
2. Copy `terraform.tfvars.example`, enter the existing secret ARN and layer ARN,
   then run `terraform init`, `terraform plan`, and reviewed `terraform apply`.
3. Run the SQL files in numeric order as a Snowflake administrator. Replace the
   documented storage-integration role and bucket placeholders.
4. Upload the Glue script to the deployed artifact location if your release process
   does not package it automatically.
5. Configure GitHub `dev` and `prod` environments and Snowflake secrets. Require an
   approval for `prod`.
6. Trigger one bounded backfill, verify `RAW.LOAD_AUDIT`, then run `dbt build` and
   source freshness.

This repository does not assert that these cloud resources have been deployed.

