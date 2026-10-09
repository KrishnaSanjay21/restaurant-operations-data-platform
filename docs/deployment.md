# AWS and Snowflake deployment — cost-controlled walkthrough

This guide deploys the reference architecture without representing it as free or
production-ready. AWS pricing and Free Tier eligibility vary by account, region,
and signup date. Review Billing before every run.

## 1. Know what can charge you

| Component | Cost guidance for this project |
|---|---|
| Lambda, Step Functions, SQS, CloudWatch | Small test runs may fit current monthly free allowances, but limits apply. |
| S3 | Storage and requests can be charged. Raw objects are compressed and lifecycle-managed. |
| Glue Spark ETL | **Paid compute. It is not made free by the Data Catalog free allowance.** This project defaults to two G.1X workers. |
| Secrets Manager | Normally charged per secret and API calls after any applicable trial. One secret is used. |
| Snowflake | Separate Snowflake credits/storage; not part of AWS Free Tier. Use an X-Small auto-suspending warehouse or a trial account. |
| Power BI | Separate Microsoft licensing rules apply if the report is published. |

Cost-safe defaults in Terraform:

- recurring schedule disabled;
- CloudWatch alarms disabled;
- 10,000 inspections and 10,000 complaints per test run;
- two G.1X Glue workers;
- X-Small Snowflake warehouse with 60-second auto-suspend;
- no customer-managed KMS key;
- raw S3 objects transition to Standard-IA after 90 days.

For the verified 500,000+ evidence run, use the local DuckDB pipeline. Only raise
the AWS limits when you intentionally accept Glue, S3, API, and Snowflake costs.

Official references:

- https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/tracking-free-tier-usage.html
- https://aws.amazon.com/glue/pricing/
- https://aws.amazon.com/sqs/pricing/
- https://aws.amazon.com/cloudwatch/pricing/
- https://aws.amazon.com/secrets-manager/pricing/

## 2. Install and verify the tools

Install Git, Python 3.12, AWS CLI v2, and Terraform 1.7 or newer. Then run:

```powershell
aws --version
terraform version
python --version
aws configure
aws sts get-caller-identity
```

Use an IAM role or short-lived credentials when possible. Never put AWS keys in
Terraform files or Git. The AWS provider supports the shared AWS CLI profile.

## 3. Create billing protection first

In AWS Console:

1. Open **Billing and Cost Management → Budgets**.
2. Create a monthly cost budget such as `$5`.
3. Add email notifications at 50%, 80%, and 100%.
4. Open **Billing preferences** and enable Free Tier usage alerts.
5. Keep all resources in one region; this guide uses `us-east-1`.

A budget is an alert, not a hard spending cap.

## 4. Create a Snowflake service identity

Use a Snowflake trial or a cost-controlled account. In Snowsight, create a user
that will only load this portfolio database. Store its password in a password
manager; do not commit it.

Run `snowflake/00_platform.sql` as an administrator, then grant the loader role to
the service user:

```sql
GRANT ROLE RESTAURANT_OPS_LOADER TO USER RESTAURANT_OPS_SERVICE;
```

The warehouse is X-Small, auto-resumes when used, and suspends after 60 seconds.
Suspend it manually whenever testing is finished:

```sql
ALTER WAREHOUSE RESTAURANT_OPS_WH SUSPEND;
```

## 5. Build the Linux-compatible Snowflake Lambda layer

From the repository root in PowerShell:

```powershell
New-Item -ItemType Directory -Force .build\snowflake-layer\python
python -m pip install "snowflake-connector-python==4.8.0" `
  --platform manylinux2014_x86_64 `
  --implementation cp `
  --python-version 3.12 `
  --only-binary=:all: `
  --target .build\snowflake-layer\python
Compress-Archive -Path .build\snowflake-layer\python `
  -DestinationPath .build\snowflake-connector-layer.zip -Force
aws lambda publish-layer-version `
  --layer-name restaurant-ops-snowflake-connector `
  --zip-file fileb://.build/snowflake-connector-layer.zip `
  --compatible-runtimes python3.12 `
  --compatible-architectures x86_64 `
  --region us-east-1
```

Record the returned `LayerVersionArn`. AWS requires the layer to use a top-level
`python` directory and Linux-compatible packages.

## 6. Store the Snowflake credentials

Create a temporary JSON file outside the repository:

```json
{
  "account": "YOUR_ACCOUNT_IDENTIFIER",
  "user": "RESTAURANT_OPS_SERVICE",
  "password": "YOUR_PASSWORD",
  "warehouse": "RESTAURANT_OPS_WH",
  "database": "RESTAURANT_OPS",
  "role": "RESTAURANT_OPS_LOADER"
}
```

Store it and then remove the temporary file:

```powershell
aws secretsmanager create-secret `
  --name restaurant-ops/dev/snowflake `
  --secret-string file://$env:TEMP/restaurant-ops-snowflake.json `
  --region us-east-1
Remove-Item -LiteralPath "$env:TEMP\restaurant-ops-snowflake.json"
```

Record the returned secret ARN. One Secrets Manager secret is a small recurring
cost after any trial. The project uses the AWS-managed encryption key to avoid a
separate customer-managed KMS-key charge.

## 7. Configure Terraform for a small test

```powershell
Copy-Item terraform\aws\terraform.tfvars.example terraform\aws\terraform.tfvars
```

Edit `terraform.tfvars`:

```hcl
aws_region                    = "us-east-1"
environment                   = "dev"
snowflake_secret_arn          = "<SECRET_ARN>"
snowflake_connector_layer_arn = "<LAYER_VERSION_ARN>"
enable_schedule               = false
enable_alarms                 = false
glue_workers                  = 2
inspections_max_rows          = 10000
complaints_max_rows           = 10000
snowflake_principal_arn       = ""
snowflake_external_id         = "BOOTSTRAP_ONLY_REPLACE_AFTER_DESC_INTEGRATION"
```

The file is ignored by Git. Do not enable the daily schedule during initial tests.

## 8. Preview and create the AWS resources

```powershell
terraform -chdir=terraform/aws init
terraform -chdir=terraform/aws fmt -check
terraform -chdir=terraform/aws validate
terraform -chdir=terraform/aws plan -out=tfplan
terraform -chdir=terraform/aws apply tfplan
terraform -chdir=terraform/aws output
```

Terraform creates three encrypted/private S3 buckets, the Glue job, two Lambdas,
Step Functions, SQS DLQ, CloudWatch log group, EventBridge resources, and scoped
IAM roles. The recurring trigger and alarms are not created with the defaults.

Record these outputs:

```powershell
$curatedBucket = terraform -chdir=terraform/aws output -raw curated_bucket
$snowflakeRole = terraform -chdir=terraform/aws output -raw snowflake_storage_role_arn
$stateMachine = terraform -chdir=terraform/aws output -raw state_machine_arn
```

## 9. Complete the Snowflake–S3 trust handshake

In Snowflake, replace the two placeholders and run:

```sql
USE ROLE ACCOUNTADMIN;

CREATE OR REPLACE STORAGE INTEGRATION RESTAURANT_OPS_S3
  TYPE = EXTERNAL_STAGE
  STORAGE_PROVIDER = 'S3'
  ENABLED = TRUE
  STORAGE_AWS_ROLE_ARN = '<snowflake_storage_role_arn>'
  STORAGE_ALLOWED_LOCATIONS = ('s3://<curated_bucket>/');

DESC INTEGRATION RESTAURANT_OPS_S3;
```

Copy `STORAGE_AWS_IAM_USER_ARN` and `STORAGE_AWS_EXTERNAL_ID` from the result into
`terraform.tfvars`:

```hcl
snowflake_principal_arn = "<STORAGE_AWS_IAM_USER_ARN>"
snowflake_external_id   = "<STORAGE_AWS_EXTERNAL_ID>"
```

Update the IAM trust policy:

```powershell
terraform -chdir=terraform/aws plan -out=tfplan
terraform -chdir=terraform/aws apply tfplan
```

This two-pass bootstrap avoids storing long-lived AWS keys in Snowflake. Snowflake
recommends a storage integration with its IAM principal and generated external ID.

## 10. Create and test the external stage

Run `snowflake/01_raw_tables.sql`, then create the stage:

```sql
USE ROLE ACCOUNTADMIN;
USE DATABASE RESTAURANT_OPS;
USE SCHEMA RAW;

GRANT USAGE ON INTEGRATION RESTAURANT_OPS_S3 TO ROLE RESTAURANT_OPS_LOADER;

CREATE OR REPLACE STAGE CURATED_STAGE
  URL = 's3://<curated_bucket>/'
  STORAGE_INTEGRATION = RESTAURANT_OPS_S3
  FILE_FORMAT = PARQUET_FORMAT;

GRANT USAGE ON STAGE CURATED_STAGE TO ROLE RESTAURANT_OPS_LOADER;
LIST @CURATED_STAGE;
```

An empty `LIST` result is expected before the first pipeline run; an authorization
error means the trust policy, external ID, role ARN, or bucket URL is wrong.

Run `snowflake/02_load_procedure.sql` and `snowflake/03_monitoring.sql`.

## 11. Run one bounded pipeline execution

Start with recent data and a unique execution name:

```powershell
$executionName = "portfolio-test-$(Get-Date -Format yyyyMMdd-HHmmss)"
aws stepfunctions start-execution `
  --state-machine-arn $stateMachine `
  --name $executionName `
  --input '{"start_date":"2026-01-01"}' `
  --region us-east-1
```

Watch **Step Functions → Executions**. The flow should ingest API pages, run the
three Glue normalization jobs, and invoke the Snowflake batch loader. Glue is the
main AWS cost in this architecture, so do not repeatedly rerun a successful batch.

## 12. Validate the data and dbt project

In Snowflake:

```sql
SELECT * FROM RESTAURANT_OPS.RAW.LOAD_AUDIT ORDER BY COMPLETED_AT DESC;
SELECT * FROM RESTAURANT_OPS.ANALYTICS.VW_PIPELINE_FRESHNESS;
SELECT * FROM RESTAURANT_OPS.ANALYTICS.VW_LOAD_RECONCILIATION;
```

Locally, configure the environment variables expected by
`dbt/restaurant_ops/profiles.yml`, then run:

```powershell
dbt build --project-dir dbt\restaurant_ops --profiles-dir dbt\restaurant_ops
dbt source freshness --project-dir dbt\restaurant_ops --profiles-dir dbt\restaurant_ops
```

All critical dbt tests must pass before refreshing Power BI.

## 13. Inspect monitoring and failure recovery

- Step Functions: execution graph, input, output, and failed state.
- CloudWatch Logs: Lambda, Glue, and Step Functions error logs.
- SQS: dead-letter queue messages and rejection payloads.
- S3: raw `source/date/batch` partitions and curated Parquet.
- Snowflake: `RAW.LOAD_AUDIT` and monitoring views.

Follow `docs/failure_recovery.md` before replaying a failed batch. Enable alarms
only after supplying an SNS topic and reviewing CloudWatch/SNS pricing.

## 14. Enable a schedule only after testing

To enable the daily EventBridge trigger, change only:

```hcl
enable_schedule = true
```

Then review and apply a new Terraform plan. Leave it false for a portfolio demo to
prevent unattended Glue and Snowflake charges.

## 15. Full-scale portfolio run

The repository already contains local evidence for 577,630 API rows. If you still
want to reproduce that volume in AWS, explicitly change:

```hcl
inspections_max_rows = 0
complaints_max_rows  = 275000
```

Run `terraform plan`, estimate Glue/S3/Snowflake costs, and apply. This is a paid
scale test and should not be described as guaranteed Free Tier usage.

## 16. Stop costs when finished

First suspend Snowflake:

```sql
ALTER WAREHOUSE RESTAURANT_OPS_WH SUSPEND;
```

Download any evidence you want to keep, then destroy the AWS resources:

```powershell
terraform -chdir=terraform/aws plan -destroy -out=destroy.tfplan
terraform -chdir=terraform/aws apply destroy.tfplan
```

The S3 buckets use `force_destroy = false`, so Terraform will refuse to remove
non-empty buckets. Empty only the three exact bucket names shown by Terraform
outputs, then retry the reviewed destroy plan. Finally, schedule deletion of the
Snowflake secret and remove the Lambda layer version if no other function uses it.

Verify **Billing → Cost Explorer**, **Budgets**, S3, Glue, Lambda, Step Functions,
SQS, CloudWatch, and Secrets Manager before considering cleanup complete.

