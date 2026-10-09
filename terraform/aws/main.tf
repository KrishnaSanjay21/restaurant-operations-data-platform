data "aws_caller_identity" "current" {}

resource "random_id" "suffix" {
  byte_length = 3
}

locals {
  name                = "${var.project_name}-${var.environment}"
  bucket_suffix       = random_id.suffix.hex
  alarm_actions       = var.alarm_topic_arn == "" ? [] : [var.alarm_topic_arn]
  snowflake_layers    = var.snowflake_connector_layer_arn == "" ? [] : [var.snowflake_connector_layer_arn]
}

resource "aws_s3_bucket" "raw" {
  bucket        = "${local.name}-raw-${local.bucket_suffix}"
  force_destroy = false
}

resource "aws_s3_bucket" "curated" {
  bucket        = "${local.name}-curated-${local.bucket_suffix}"
  force_destroy = false
}

resource "aws_s3_bucket" "artifacts" {
  bucket        = "${local.name}-artifacts-${local.bucket_suffix}"
  force_destroy = false
}

resource "aws_s3_bucket_public_access_block" "all" {
  for_each = {
    raw       = aws_s3_bucket.raw.id
    curated   = aws_s3_bucket.curated.id
    artifacts = aws_s3_bucket.artifacts.id
  }
  bucket                  = each.value
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "all" {
  for_each = {
    raw       = aws_s3_bucket.raw.id
    curated   = aws_s3_bucket.curated.id
    artifacts = aws_s3_bucket.artifacts.id
  }
  bucket = each.value
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "all" {
  for_each = {
    raw       = aws_s3_bucket.raw.id
    curated   = aws_s3_bucket.curated.id
    artifacts = aws_s3_bucket.artifacts.id
  }
  bucket = each.value
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_lifecycle_configuration" "raw" {
  bucket = aws_s3_bucket.raw.id
  rule {
    id     = "archive-raw"
    status = "Enabled"
    filter {}
    transition {
      days          = 90
      storage_class = "STANDARD_IA"
    }
    noncurrent_version_expiration { noncurrent_days = 30 }
  }
}

resource "aws_sqs_queue" "dead_letter" {
  name                      = "${local.name}-dead-letter"
  message_retention_seconds = 1209600
  visibility_timeout_seconds = 300
  sqs_managed_sse_enabled   = true
}

data "archive_file" "ingest_lambda" {
  type        = "zip"
  source_file = "${path.module}/../../orchestration/lambdas/ingest_api.py"
  output_path = "${path.module}/ingest_api.zip"
}

data "archive_file" "snowflake_lambda" {
  type        = "zip"
  source_file = "${path.module}/../../orchestration/lambdas/snowflake_load.py"
  output_path = "${path.module}/snowflake_load.zip"
}

resource "aws_iam_role" "lambda" {
  name = "${local.name}-lambda-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "lambda" {
  role = aws_iam_role.lambda.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:*"
      },
      {
        Effect = "Allow"
        Action = ["s3:PutObject", "s3:AbortMultipartUpload"]
        Resource = "${aws_s3_bucket.raw.arn}/*"
      },
      {
        Effect = "Allow"
        Action = ["secretsmanager:GetSecretValue"]
        Resource = var.snowflake_secret_arn
      }
    ]
  })
}

resource "aws_lambda_function" "ingest" {
  function_name    = "${local.name}-ingest"
  role             = aws_iam_role.lambda.arn
  runtime          = "python3.12"
  handler          = "ingest_api.handler"
  filename         = data.archive_file.ingest_lambda.output_path
  source_code_hash = data.archive_file.ingest_lambda.output_base64sha256
  timeout          = 900
  memory_size      = 2048
  environment {
    variables = { RAW_BUCKET = aws_s3_bucket.raw.id }
  }
}

resource "aws_lambda_function" "snowflake_load" {
  function_name    = "${local.name}-snowflake-load"
  role             = aws_iam_role.lambda.arn
  runtime          = "python3.12"
  handler          = "snowflake_load.handler"
  filename         = data.archive_file.snowflake_lambda.output_path
  source_code_hash = data.archive_file.snowflake_lambda.output_base64sha256
  timeout          = 300
  memory_size      = 1024
  layers           = local.snowflake_layers
  environment {
    variables = { SNOWFLAKE_SECRET_ARN = var.snowflake_secret_arn }
  }
}

resource "aws_s3_object" "glue_script" {
  bucket = aws_s3_bucket.artifacts.id
  key    = "glue/normalize_job.py"
  source = "${path.module}/../../glue/normalize_job.py"
  etag   = filemd5("${path.module}/../../glue/normalize_job.py")
}

resource "aws_iam_role" "glue" {
  name = "${local.name}-glue-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = { Service = "glue.amazonaws.com" }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "glue" {
  role = aws_iam_role.glue.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["s3:GetObject", "s3:ListBucket"]
        Resource = [aws_s3_bucket.raw.arn, "${aws_s3_bucket.raw.arn}/*", aws_s3_bucket.artifacts.arn, "${aws_s3_bucket.artifacts.arn}/*"]
      },
      {
        Effect = "Allow"
        Action = ["s3:PutObject", "s3:DeleteObject", "s3:ListBucket"]
        Resource = [aws_s3_bucket.curated.arn, "${aws_s3_bucket.curated.arn}/*"]
      },
      {
        Effect = "Allow"
        Action = ["sqs:SendMessage", "sqs:SendMessageBatch"]
        Resource = aws_sqs_queue.dead_letter.arn
      },
      {
        Effect = "Allow"
        Action = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents", "cloudwatch:PutMetricData"]
        Resource = "*"
      }
    ]
  })
}

resource "aws_glue_catalog_database" "platform" {
  name = replace(local.name, "-", "_")
}

resource "aws_glue_job" "normalize" {
  name              = "${local.name}-normalize"
  role_arn          = aws_iam_role.glue.arn
  glue_version      = "5.0"
  worker_type       = "G.1X"
  number_of_workers = 5
  max_retries       = 1
  timeout           = 60
  command {
    name            = "glueetl"
    python_version  = "3"
    script_location = "s3://${aws_s3_bucket.artifacts.id}/${aws_s3_object.glue_script.key}"
  }
  default_arguments = {
    "--job-bookmark-option"              = "job-bookmark-enable"
    "--enable-continuous-cloudwatch-log" = "true"
    "--enable-metrics"                   = "true"
  }
}

resource "aws_cloudwatch_log_group" "step_functions" {
  name              = "/aws/vendedlogs/states/${local.name}"
  retention_in_days = 30
}

resource "aws_iam_role" "step_functions" {
  name = "${local.name}-step-functions-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = { Service = "states.amazonaws.com" }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "step_functions" {
  role = aws_iam_role.step_functions.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["lambda:InvokeFunction"]
        Resource = [aws_lambda_function.ingest.arn, aws_lambda_function.snowflake_load.arn]
      },
      {
        Effect = "Allow"
        Action = ["glue:StartJobRun", "glue:GetJobRun", "glue:GetJobRuns", "glue:BatchStopJobRun"]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = ["sqs:SendMessage"]
        Resource = aws_sqs_queue.dead_letter.arn
      },
      {
        Effect = "Allow"
        Action = ["logs:CreateLogDelivery", "logs:GetLogDelivery", "logs:UpdateLogDelivery", "logs:DeleteLogDelivery", "logs:ListLogDeliveries", "logs:PutResourcePolicy", "logs:DescribeResourcePolicies", "logs:DescribeLogGroups"]
        Resource = "*"
      }
    ]
  })
}

resource "aws_sfn_state_machine" "pipeline" {
  name     = local.name
  role_arn = aws_iam_role.step_functions.arn
  definition = templatefile("${path.module}/../../orchestration/step_functions/restaurant_ops.asl.json.tftpl", {
    ingest_lambda_arn    = aws_lambda_function.ingest.arn
    snowflake_lambda_arn = aws_lambda_function.snowflake_load.arn
    glue_job_name        = aws_glue_job.normalize.name
    raw_bucket           = aws_s3_bucket.raw.id
    curated_bucket       = aws_s3_bucket.curated.id
    dlq_url              = aws_sqs_queue.dead_letter.url
  })
  logging_configuration {
    include_execution_data = false
    level                  = "ERROR"
    log_destination        = "${aws_cloudwatch_log_group.step_functions.arn}:*"
  }
}

resource "aws_iam_role" "events" {
  name = "${local.name}-events-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = { Service = "events.amazonaws.com" }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "events" {
  role = aws_iam_role.events.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = "states:StartExecution"
      Resource = aws_sfn_state_machine.pipeline.arn
    }]
  })
}

resource "aws_cloudwatch_event_rule" "daily" {
  name                = "${local.name}-daily"
  schedule_expression = var.schedule_expression
}

resource "aws_cloudwatch_event_target" "pipeline" {
  rule     = aws_cloudwatch_event_rule.daily.name
  arn      = aws_sfn_state_machine.pipeline.arn
  role_arn = aws_iam_role.events.arn
  input = jsonencode({
    start_date = "2020-01-01"
  })
}

resource "aws_cloudwatch_metric_alarm" "pipeline_failed" {
  alarm_name          = "${local.name}-executions-failed"
  namespace           = "AWS/States"
  metric_name         = "ExecutionsFailed"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  dimensions = { StateMachineArn = aws_sfn_state_machine.pipeline.arn }
  alarm_actions = local.alarm_actions
}

resource "aws_cloudwatch_metric_alarm" "dlq_visible" {
  alarm_name          = "${local.name}-dlq-visible"
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateNumberOfMessagesVisible"
  statistic           = "Maximum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  dimensions = { QueueName = aws_sqs_queue.dead_letter.name }
  alarm_actions = local.alarm_actions
}

