terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

provider "google" {
  project = var.gcp_project_id
  region  = var.gcp_region
}

resource "random_id" "suffix" {
  byte_length = 4
}

# ─────────────────────────────────────────────
# S3 BUCKET — media storage (AWS primary)
# ─────────────────────────────────────────────
resource "aws_s3_bucket" "media" {
  bucket        = "aussie-ecolens-media-${random_id.suffix.hex}"
  force_destroy = true
}

resource "aws_s3_bucket_cors_configuration" "media" {
  bucket = aws_s3_bucket.media.id
  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["GET", "PUT", "POST", "DELETE", "HEAD"]
    allowed_origins = ["*"]
    expose_headers  = ["ETag"]
    max_age_seconds = 3000
  }
}

resource "aws_s3_bucket_public_access_block" "media" {
  bucket                  = aws_s3_bucket.media.id
  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

resource "aws_s3_bucket_policy" "media_public_read" {
  bucket     = aws_s3_bucket.media.id
  depends_on = [aws_s3_bucket_public_access_block.media]
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "PublicRead"
      Effect    = "Allow"
      Principal = "*"
      Action    = "s3:GetObject"
      Resource  = "${aws_s3_bucket.media.arn}/*"
    }]
  })
}

# ─────────────────────────────────────────────
# COGNITO USER POOL
# ─────────────────────────────────────────────
resource "aws_cognito_user_pool" "main" {
  name = "aussie-ecolens-users"

  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]

  password_policy {
    minimum_length    = 8
    require_lowercase = true
    require_numbers   = true
    require_symbols   = false
    require_uppercase = true
  }

  schema {
    name                = "email"
    attribute_data_type = "String"
    required            = true
    mutable             = true
  }
  schema {
    name                = "given_name"
    attribute_data_type = "String"
    required            = true
    mutable             = true
  }
  schema {
    name                = "family_name"
    attribute_data_type = "String"
    required            = true
    mutable             = true
  }

  verification_message_template {
    default_email_option = "CONFIRM_WITH_CODE"
    email_subject        = "Aussie EcoLens — Verify your email"
    email_message        = "Your verification code is {####}"
  }

  email_configuration {
    email_sending_account = "COGNITO_DEFAULT"
  }
}

resource "aws_cognito_user_pool_client" "frontend" {
  name         = "aussie-ecolens-frontend"
  user_pool_id = aws_cognito_user_pool.main.id

  explicit_auth_flows = [
    "ALLOW_USER_PASSWORD_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH",
    "ALLOW_USER_SRP_AUTH",
  ]

  access_token_validity  = 1
  id_token_validity      = 1
  refresh_token_validity = 30

  token_validity_units {
    access_token  = "hours"
    id_token      = "hours"
    refresh_token = "days"
  }

  prevent_user_existence_errors = "ENABLED"
}

# ─────────────────────────────────────────────
# DYNAMODB TABLE
# ─────────────────────────────────────────────
resource "aws_dynamodb_table" "files" {
  name         = "aussie-ecolens-files"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "file_id"

  attribute {
    name = "file_id"
    type = "S"
  }
  attribute {
    name = "checksum"
    type = "S"
  }
  attribute {
    name = "thumbnail_url"
    type = "S"
  }

  global_secondary_index {
    name            = "checksum-index"
    hash_key        = "checksum"
    projection_type = "ALL"
  }

  global_secondary_index {
    name            = "thumbnail-index"
    hash_key        = "thumbnail_url"
    projection_type = "ALL"
  }
}

# ─────────────────────────────────────────────
# IAM ROLE — Lambda execution
# ─────────────────────────────────────────────
resource "aws_iam_role" "lambda_exec" {
  name = "aussie-ecolens-lambda-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "lambda_policy" {
  name = "aussie-ecolens-lambda-policy"
  role = aws_iam_role.lambda_exec.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:HeadObject", "s3:ListBucket"]
        Resource = ["${aws_s3_bucket.media.arn}", "${aws_s3_bucket.media.arn}/*"]
      },
      {
        Effect   = "Allow"
        Action   = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:DeleteItem",
                    "dynamodb:Query", "dynamodb:Scan", "dynamodb:UpdateItem"]
        Resource = ["${aws_dynamodb_table.files.arn}", "${aws_dynamodb_table.files.arn}/index/*"]
      },
      {
        Effect   = "Allow"
        Action   = ["sns:Publish", "sns:Subscribe", "sns:ListSubscriptionsByTopic"]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["cognito-idp:AdminGetUser"]
        Resource = aws_cognito_user_pool.main.arn
      }
    ]
  })
}

# ─────────────────────────────────────────────
# SNS TOPIC — tag notifications
# ─────────────────────────────────────────────
resource "aws_sns_topic" "tag_notifications" {
  name = "aussie-ecolens-tag-notifications"
}

# ─────────────────────────────────────────────
# LAMBDA — Auth helper
# ─────────────────────────────────────────────
data "archive_file" "auth_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../backend/lambdas/auth"
  output_path = "${path.module}/zips/auth.zip"
}
resource "aws_lambda_function" "auth" {
  filename         = data.archive_file.auth_zip.output_path
  source_code_hash = data.archive_file.auth_zip.output_base64sha256
  function_name    = "aussie-ecolens-auth"
  role             = aws_iam_role.lambda_exec.arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.12"
  timeout          = 30
  environment {
    variables = {
      COGNITO_USER_POOL_ID = aws_cognito_user_pool.main.id
      COGNITO_CLIENT_ID    = aws_cognito_user_pool_client.frontend.id
    }
  }
}

# ─────────────────────────────────────────────
# LAMBDA — Upload (pre-signed URL + dedup)
# ─────────────────────────────────────────────
data "archive_file" "upload_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../backend/lambdas/upload"
  output_path = "${path.module}/zips/upload.zip"
}
resource "aws_lambda_function" "upload" {
  filename         = data.archive_file.upload_zip.output_path
  source_code_hash = data.archive_file.upload_zip.output_base64sha256
  function_name    = "aussie-ecolens-upload"
  role             = aws_iam_role.lambda_exec.arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.12"
  timeout          = 30
  environment {
    variables = {
      S3_BUCKET      = aws_s3_bucket.media.bucket
      DYNAMODB_TABLE = aws_dynamodb_table.files.name
    }
  }
}

# ─────────────────────────────────────────────
# LAMBDA — Thumbnail (triggered by S3)
# ─────────────────────────────────────────────
data "archive_file" "thumbnail_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../backend/lambdas/thumbnail"
  output_path = "${path.module}/zips/thumbnail.zip"
}
resource "aws_lambda_function" "thumbnail" {
  filename         = data.archive_file.thumbnail_zip.output_path
  source_code_hash = data.archive_file.thumbnail_zip.output_base64sha256
  function_name    = "aussie-ecolens-thumbnail"
  role             = aws_iam_role.lambda_exec.arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.12"
  timeout          = 120
  memory_size      = 512
  layers           = [aws_lambda_layer_version.cv2_layer.arn]
  environment {
    variables = {
      S3_BUCKET      = aws_s3_bucket.media.bucket
      DYNAMODB_TABLE = aws_dynamodb_table.files.name
    }
  }
}

# ─────────────────────────────────────────────
# LAMBDA — ML Tagger (GCP Cloud Function trigger)
# NOTE: Tagger runs on GCP Cloud Function for multi-cloud
# This Lambda orchestrates the call to GCP
# ─────────────────────────────────────────────
data "archive_file" "tagger_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../backend/lambdas/tagger"
  output_path = "${path.module}/zips/tagger.zip"
}
resource "aws_lambda_function" "tagger" {
  filename         = data.archive_file.tagger_zip.output_path
  source_code_hash = data.archive_file.tagger_zip.output_base64sha256
  function_name    = "aussie-ecolens-tagger"
  role             = aws_iam_role.lambda_exec.arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.12"
  timeout          = 300
  memory_size      = 256
  environment {
    variables = {
      S3_BUCKET         = aws_s3_bucket.media.bucket
      DYNAMODB_TABLE    = aws_dynamodb_table.files.name
      SNS_TOPIC_ARN     = aws_sns_topic.tag_notifications.arn
      GCP_FUNCTION_URL  = var.gcp_tagger_function_url
    }
  }
}

# ─────────────────────────────────────────────
# LAMBDA — Queries
# ─────────────────────────────────────────────
data "archive_file" "queries_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../backend/lambdas/queries"
  output_path = "${path.module}/zips/queries.zip"
}
resource "aws_lambda_function" "queries" {
  filename         = data.archive_file.queries_zip.output_path
  source_code_hash = data.archive_file.queries_zip.output_base64sha256
  function_name    = "aussie-ecolens-queries"
  role             = aws_iam_role.lambda_exec.arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.12"
  timeout          = 30
  environment {
    variables = {
      DYNAMODB_TABLE   = aws_dynamodb_table.files.name
      S3_BUCKET        = aws_s3_bucket.media.bucket
      GCP_FUNCTION_URL = var.gcp_tagger_function_url
    }
  }
}

# ─────────────────────────────────────────────
# LAMBDA — Tag management
# ─────────────────────────────────────────────
data "archive_file" "tags_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../backend/lambdas/tags"
  output_path = "${path.module}/zips/tags.zip"
}
resource "aws_lambda_function" "tags" {
  filename         = data.archive_file.tags_zip.output_path
  source_code_hash = data.archive_file.tags_zip.output_base64sha256
  function_name    = "aussie-ecolens-tags"
  role             = aws_iam_role.lambda_exec.arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.12"
  timeout          = 30
  environment {
    variables = {
      DYNAMODB_TABLE = aws_dynamodb_table.files.name
      SNS_TOPIC_ARN  = aws_sns_topic.tag_notifications.arn
    }
  }
}

# ─────────────────────────────────────────────
# LAMBDA — Delete
# ─────────────────────────────────────────────
data "archive_file" "delete_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../backend/lambdas/delete"
  output_path = "${path.module}/zips/delete.zip"
}
resource "aws_lambda_function" "delete" {
  filename         = data.archive_file.delete_zip.output_path
  source_code_hash = data.archive_file.delete_zip.output_base64sha256
  function_name    = "aussie-ecolens-delete"
  role             = aws_iam_role.lambda_exec.arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.12"
  timeout          = 30
  environment {
    variables = {
      S3_BUCKET      = aws_s3_bucket.media.bucket
      DYNAMODB_TABLE = aws_dynamodb_table.files.name
    }
  }
}

# ─────────────────────────────────────────────
# LAMBDA — Notifications
# ─────────────────────────────────────────────
data "archive_file" "notifications_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../backend/lambdas/notifications"
  output_path = "${path.module}/zips/notifications.zip"
}
resource "aws_lambda_function" "notifications" {
  filename         = data.archive_file.notifications_zip.output_path
  source_code_hash = data.archive_file.notifications_zip.output_base64sha256
  function_name    = "aussie-ecolens-notifications"
  role             = aws_iam_role.lambda_exec.arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.12"
  timeout          = 30
  environment {
    variables = {
      SNS_TOPIC_ARN  = aws_sns_topic.tag_notifications.arn
      DYNAMODB_TABLE = aws_dynamodb_table.files.name
    }
  }
}

# ─────────────────────────────────────────────
# LAMBDA LAYER — OpenCV
# ─────────────────────────────────────────────
resource "aws_lambda_layer_version" "cv2_layer" {
  layer_name          = "aussie-ecolens-cv2"
  compatible_runtimes = ["python3.12"]
  # In production: build and upload the actual layer zip
  # For deployment: use the pre-built layer from scripts/build_layer.sh
  filename = "${path.module}/zips/cv2_layer.zip"
}

# ─────────────────────────────────────────────
# S3 TRIGGERS → Lambda
# ─────────────────────────────────────────────
resource "aws_s3_bucket_notification" "media_trigger" {
  bucket = aws_s3_bucket.media.id

  lambda_function {
    lambda_function_arn = aws_lambda_function.thumbnail.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "uploads/"
    filter_suffix       = ""
  }

  lambda_function {
    lambda_function_arn = aws_lambda_function.tagger.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "uploads/"
    filter_suffix       = ""
  }

  depends_on = [
    aws_lambda_permission.allow_s3_thumbnail,
    aws_lambda_permission.allow_s3_tagger,
  ]
}

resource "aws_lambda_permission" "allow_s3_thumbnail" {
  statement_id  = "AllowS3InvokeThumbnail"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.thumbnail.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.media.arn
}

resource "aws_lambda_permission" "allow_s3_tagger" {
  statement_id  = "AllowS3InvokeTagger"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.tagger.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.media.arn
}

# ─────────────────────────────────────────────
# API GATEWAY
# ─────────────────────────────────────────────
# ─────────────────────────────────────────────
# REST API GATEWAY  (aws_api_gateway_rest_api)
# Tutor confirmed: must be REST API, not HTTP API
# ─────────────────────────────────────────────
resource "aws_api_gateway_rest_api" "main" {
  name        = "aussie-ecolens-api"
  description = "Aussie EcoLens RESTful API — multi-cloud wildlife platform"
  endpoint_configuration {
    types = ["REGIONAL"]
  }
}

# ── Cognito Authorizer ──────────────────────────────────────────────────────
resource "aws_api_gateway_authorizer" "cognito" {
  name                   = "cognito-authorizer"
  rest_api_id            = aws_api_gateway_rest_api.main.id
  type                   = "COGNITO_USER_POOLS"
  provider_arns          = [aws_cognito_user_pool.main.arn]
  identity_source        = "method.request.header.Authorization"
}

# ── Helper: create a resource + POST method + Lambda integration ─────────────
# upload resource
resource "aws_api_gateway_resource" "upload" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_rest_api.main.root_resource_id
  path_part   = "upload"
}
resource "aws_api_gateway_resource" "upload_presign" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.upload.id
  path_part   = "presign"
}
resource "aws_api_gateway_resource" "upload_confirm" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.upload.id
  path_part   = "confirm"
}

# query resource
resource "aws_api_gateway_resource" "query" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_rest_api.main.root_resource_id
  path_part   = "query"
}
resource "aws_api_gateway_resource" "query_tags" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.query.id
  path_part   = "tags"
}
resource "aws_api_gateway_resource" "query_thumbnail" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.query.id
  path_part   = "thumbnail"
}
resource "aws_api_gateway_resource" "query_file" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.query.id
  path_part   = "file"
}

# tags resource
resource "aws_api_gateway_resource" "tags_resource" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_rest_api.main.root_resource_id
  path_part   = "tags"
}

# delete resource
resource "aws_api_gateway_resource" "delete_resource" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_rest_api.main.root_resource_id
  path_part   = "delete"
}

# notifications resource
resource "aws_api_gateway_resource" "notifications" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_rest_api.main.root_resource_id
  path_part   = "notifications"
}
resource "aws_api_gateway_resource" "notifications_subscribe" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.notifications.id
  path_part   = "subscribe"
}
resource "aws_api_gateway_resource" "notifications_unsubscribe" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.notifications.id
  path_part   = "unsubscribe"
}

# ── Local map: resource → lambda invoke ARN ─────────────────────────────────
locals {
  method_map = {
    upload_presign           = { resource = aws_api_gateway_resource.upload_presign.id,           lambda = aws_lambda_function.upload.invoke_arn }
    upload_confirm           = { resource = aws_api_gateway_resource.upload_confirm.id,           lambda = aws_lambda_function.upload.invoke_arn }
    query_tags               = { resource = aws_api_gateway_resource.query_tags.id,               lambda = aws_lambda_function.queries.invoke_arn }
    query_thumbnail          = { resource = aws_api_gateway_resource.query_thumbnail.id,          lambda = aws_lambda_function.queries.invoke_arn }
    query_file               = { resource = aws_api_gateway_resource.query_file.id,               lambda = aws_lambda_function.queries.invoke_arn }
    tags_resource            = { resource = aws_api_gateway_resource.tags_resource.id,            lambda = aws_lambda_function.tags.invoke_arn }
    delete_resource          = { resource = aws_api_gateway_resource.delete_resource.id,          lambda = aws_lambda_function.delete.invoke_arn }
    notifications_subscribe  = { resource = aws_api_gateway_resource.notifications_subscribe.id,  lambda = aws_lambda_function.notifications.invoke_arn }
    notifications_unsubscribe= { resource = aws_api_gateway_resource.notifications_unsubscribe.id,lambda = aws_lambda_function.notifications.invoke_arn }
  }
}

# ── POST methods with Cognito auth ──────────────────────────────────────────
resource "aws_api_gateway_method" "post_upload_presign" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.upload_presign.id
  http_method   = "POST"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}
resource "aws_api_gateway_integration" "post_upload_presign" {
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_resource.upload_presign.id
  http_method             = "POST"
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.upload.invoke_arn
}

resource "aws_api_gateway_method" "post_upload_confirm" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.upload_confirm.id
  http_method   = "POST"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}
resource "aws_api_gateway_integration" "post_upload_confirm" {
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_resource.upload_confirm.id
  http_method             = "POST"
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.upload.invoke_arn
}

resource "aws_api_gateway_method" "post_query_tags" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.query_tags.id
  http_method   = "POST"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}
resource "aws_api_gateway_integration" "post_query_tags" {
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_resource.query_tags.id
  http_method             = "POST"
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.queries.invoke_arn
}

resource "aws_api_gateway_method" "post_query_thumbnail" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.query_thumbnail.id
  http_method   = "POST"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}
resource "aws_api_gateway_integration" "post_query_thumbnail" {
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_resource.query_thumbnail.id
  http_method             = "POST"
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.queries.invoke_arn
}

resource "aws_api_gateway_method" "post_query_file" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.query_file.id
  http_method   = "POST"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}
resource "aws_api_gateway_integration" "post_query_file" {
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_resource.query_file.id
  http_method             = "POST"
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.queries.invoke_arn
}

resource "aws_api_gateway_method" "post_tags" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.tags_resource.id
  http_method   = "POST"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}
resource "aws_api_gateway_integration" "post_tags" {
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_resource.tags_resource.id
  http_method             = "POST"
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.tags.invoke_arn
}

resource "aws_api_gateway_method" "post_delete" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.delete_resource.id
  http_method   = "POST"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}
resource "aws_api_gateway_integration" "post_delete" {
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_resource.delete_resource.id
  http_method             = "POST"
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.delete.invoke_arn
}

resource "aws_api_gateway_method" "post_notify_sub" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.notifications_subscribe.id
  http_method   = "POST"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}
resource "aws_api_gateway_integration" "post_notify_sub" {
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_resource.notifications_subscribe.id
  http_method             = "POST"
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.notifications.invoke_arn
}

resource "aws_api_gateway_method" "post_notify_unsub" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.notifications_unsubscribe.id
  http_method   = "POST"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}
resource "aws_api_gateway_integration" "post_notify_unsub" {
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_resource.notifications_unsubscribe.id
  http_method             = "POST"
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.notifications.invoke_arn
}

# ── Deploy the REST API ──────────────────────────────────────────────────────
resource "aws_api_gateway_deployment" "prod" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  depends_on  = [
    aws_api_gateway_integration.post_upload_presign,
    aws_api_gateway_integration.post_upload_confirm,
    aws_api_gateway_integration.post_query_tags,
    aws_api_gateway_integration.post_query_thumbnail,
    aws_api_gateway_integration.post_query_file,
    aws_api_gateway_integration.post_tags,
    aws_api_gateway_integration.post_delete,
    aws_api_gateway_integration.post_notify_sub,
    aws_api_gateway_integration.post_notify_unsub,
  ]
  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_api_gateway_stage" "prod" {
  deployment_id = aws_api_gateway_deployment.prod.id
  rest_api_id   = aws_api_gateway_rest_api.main.id
  stage_name    = "prod"
}

# ── Lambda permissions for REST API Gateway ──────────────────────────────────
locals {
  apigw_exec = "arn:aws:execute-api:${var.aws_region}:*:${aws_api_gateway_rest_api.main.id}/*/*"
}

resource "aws_lambda_permission" "apigw_upload" {
  statement_id  = "AllowAPIGWUpload"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.upload.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = local.apigw_exec
}

resource "aws_lambda_permission" "apigw_queries" {
  statement_id  = "AllowAPIGWQueries"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.queries.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = local.apigw_exec
}

resource "aws_lambda_permission" "apigw_tags" {
  statement_id  = "AllowAPIGWTags"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.tags.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = local.apigw_exec
}

resource "aws_lambda_permission" "apigw_delete" {
  statement_id  = "AllowAPIGWDelete"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.delete.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = local.apigw_exec
}

resource "aws_lambda_permission" "apigw_notifications" {
  statement_id  = "AllowAPIGWNotifications"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.notifications.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = local.apigw_exec
}

# ─────────────────────────────────────────────
# GCP — Cloud Storage bucket for ML model
# ─────────────────────────────────────────────
resource "google_storage_bucket" "ml_models" {
  name          = "aussie-ecolens-models-${var.gcp_project_id}"
  location      = var.gcp_region
  force_destroy = true
  uniform_bucket_level_access = true
}

resource "google_storage_bucket_iam_member" "model_public_read" {
  bucket = google_storage_bucket.ml_models.name
  role   = "roles/storage.objectViewer"
  member = "allUsers"
}
