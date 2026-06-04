import re

with open('main.tf', encoding='utf-8') as f:
    content = f.read()

old = '''resource "aws_s3_bucket_notification" "media_trigger" {
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
}'''

new = '''resource "aws_s3_bucket_notification" "media_trigger" {
  bucket = aws_s3_bucket.media.id

  lambda_function {
    lambda_function_arn = aws_lambda_function.thumbnail.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "uploads/"
    filter_suffix       = ""
  }

  depends_on = [
    aws_lambda_permission.allow_s3_thumbnail,
    aws_lambda_permission.allow_s3_tagger,
  ]
}'''

content = content.replace(old, new)

with open('main.tf', 'w', encoding='utf-8') as f:
    f.write(content)

print('Done')
