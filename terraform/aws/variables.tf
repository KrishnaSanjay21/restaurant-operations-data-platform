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

