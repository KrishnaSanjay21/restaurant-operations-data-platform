variable "aws_region" {
  description = "AWS region for the platform."
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Resource name prefix."
  type        = string
  default     = "restaurant-ops"
}

variable "environment" {
  description = "Deployment environment."
  type        = string
  default     = "dev"
}

variable "schedule_expression" {
  description = "EventBridge schedule for the incremental pipeline."
  type        = string
  default     = "cron(0 10 * * ? *)"
}

variable "enable_schedule" {
  description = "Create the recurring EventBridge trigger. Keep false for portfolio/free-tier-safe use."
  type        = bool
  default     = false
}

variable "enable_alarms" {
  description = "Create CloudWatch alarms. Keep false until notification and alarm costs are reviewed."
  type        = bool
  default     = false
}

variable "glue_workers" {
  description = "Number of G.1X Glue workers. Two is the smallest practical Spark job setting."
  type        = number
  default     = 2

  validation {
    condition     = var.glue_workers >= 2
    error_message = "Glue Spark jobs require at least two workers for this project."
  }
}

variable "inspections_max_rows" {
  description = "Maximum inspection API rows per run; 0 means unlimited."
  type        = number
  default     = 10000
}

variable "complaints_max_rows" {
  description = "Maximum complaint API rows per run; use 275000 only for an intentional portfolio run."
  type        = number
  default     = 10000
}

variable "snowflake_secret_arn" {
  description = "Existing Secrets Manager secret containing Snowflake account credentials."
  type        = string
  sensitive   = true
}

variable "snowflake_connector_layer_arn" {
  description = "Lambda layer ARN containing snowflake-connector-python for the selected architecture."
  type        = string
  default     = ""
}

variable "alarm_topic_arn" {
  description = "Optional existing SNS topic for CloudWatch alarm actions."
  type        = string
  default     = ""
}

variable "snowflake_principal_arn" {
  description = "Snowflake STORAGE_AWS_IAM_USER_ARN after DESC INTEGRATION. Leave blank only for bootstrap."
  type        = string
  default     = ""
}

variable "snowflake_external_id" {
  description = "Snowflake STORAGE_AWS_EXTERNAL_ID after DESC INTEGRATION."
  type        = string
  default     = "BOOTSTRAP_ONLY_REPLACE_AFTER_DESC_INTEGRATION"
  sensitive   = true
}

