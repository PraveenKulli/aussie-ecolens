with open('main.tf', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    'aws_iam_role.lambda_exec.arn',
    '"arn:aws:iam::371320130392:role/LabRole"'
)

with open('main.tf', 'w', encoding='utf-8') as f:
    f.write(content)

print('Done - replacements:', content.count('LabRole'))
