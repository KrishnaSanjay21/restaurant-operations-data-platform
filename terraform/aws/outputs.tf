output "raw_bucket" { value = aws_s3_bucket.raw.id }
output "curated_bucket" { value = aws_s3_bucket.curated.id }
output "artifacts_bucket" { value = aws_s3_bucket.artifacts.id }
output "dead_letter_queue_url" { value = aws_sqs_queue.dead_letter.url }
output "state_machine_arn" { value = aws_sfn_state_machine.pipeline.arn }
output "glue_job_name" { value = aws_glue_job.normalize.name }

