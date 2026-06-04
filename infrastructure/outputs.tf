output "api_gateway_url" {
  value       = "${aws_apigatewayv2_api.main.api_endpoint}/prod"
  description = "API Gateway base URL"
}

output "cognito_user_pool_id" {
  value       = aws_cognito_user_pool.main.id
  description = "Cognito User Pool ID"
}

output "cognito_client_id" {
  value       = aws_cognito_user_pool_client.frontend.id
  description = "Cognito App Client ID"
}

output "s3_bucket_name" {
  value       = aws_s3_bucket.media.bucket
  description = "S3 media bucket name"
}

output "dynamodb_table_name" {
  value       = aws_dynamodb_table.files.name
  description = "DynamoDB table name"
}

output "sns_topic_arn" {
  value       = aws_sns_topic.tag_notifications.arn
  description = "SNS topic ARN for tag notifications"
}

output "gcp_model_bucket" {
  value       = google_storage_bucket.ml_models.name
  description = "GCP bucket for ML models"
}
