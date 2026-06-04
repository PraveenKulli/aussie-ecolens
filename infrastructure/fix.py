import re

with open('main.tf', encoding='utf-8') as f:
    content = f.read()

content = content.replace('role = aws_iam_role.lambda_exec.arn', 'role = "arn:aws:iam::371320130392:role/LabRole"')
content = re.sub(r'resource "aws_iam_role" "lambda_exec" \{.*?\n\}', '', content, flags=re.DOTALL)
content = re.sub(r'resource "aws_iam_role_policy" "lambda_policy" \{.*?\n\}', '', content, flags=re.DOTALL)
content = re.sub(r'resource "aws_s3_bucket_policy" "media_public_read" \{.*?\n\}', '', content, flags=re.DOTALL)

with open('main.tf', 'w', encoding='utf-8') as f:
    f.write(content)

print('Done')
