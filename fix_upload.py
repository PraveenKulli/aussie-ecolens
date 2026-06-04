with open('backend/lambdas/upload/handler.py', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    '"thumbnail_url": "",',
    '"thumbnail_url": "pending",'
)

with open('backend/lambdas/upload/handler.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Done')
