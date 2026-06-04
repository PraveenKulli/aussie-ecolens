with open('main.tf', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    'arn:aws:execute-api:${var.aws_region}:*:${aws_api_gateway_rest_api.main.id}/*/*',
    'arn:aws:execute-api:${var.aws_region}:371320130392:${aws_api_gateway_rest_api.main.id}/*/*'
)

with open('main.tf', 'w', encoding='utf-8') as f:
    f.write(content)

print('Done')
