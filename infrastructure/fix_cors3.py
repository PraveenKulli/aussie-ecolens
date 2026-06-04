import boto3

client = boto3.client('apigateway', region_name='us-east-1')
api_id = 'arxwhky463'

resources = client.get_resources(restApiId=api_id, limit=100)

for item in resources['items']:
    resource_id = item['id']
    path = item.get('path', '')
    methods = item.get('resourceMethods', {})
    
    if 'OPTIONS' not in methods:
        continue
    
    try:
        client.put_integration_response(
            restApiId=api_id,
            resourceId=resource_id,
            httpMethod='OPTIONS',
            statusCode='200',
            responseParameters={
                'method.response.header.Access-Control-Allow-Headers': "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token,X-Amz-User-Agent'",
                'method.response.header.Access-Control-Allow-Methods': "'DELETE,GET,HEAD,OPTIONS,PATCH,POST,PUT'",
                'method.response.header.Access-Control-Allow-Origin': "'*'"
            }
        )
        print(f"Updated: {path}")
    except Exception as e:
        print(f"Error {path}: {e}")

client.create_deployment(restApiId=api_id, stageName='prod')
print("Done!")
