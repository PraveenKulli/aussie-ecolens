import boto3

client = boto3.client('apigateway', region_name='us-east-1')
api_id = 'arxwhky463'

# Get all resources
resources = client.get_resources(restApiId=api_id)

for item in resources['items']:
    resource_id = item['id']
    path = item.get('path', '')
    
    # Skip root
    if path == '/':
        continue
    
    print(f"Adding OPTIONS to {path} ({resource_id})")
    
    try:
        # Create OPTIONS method
        client.put_method(
            restApiId=api_id,
            resourceId=resource_id,
            httpMethod='OPTIONS',
            authorizationType='NONE'
        )
        
        # Mock integration
        client.put_integration(
            restApiId=api_id,
            resourceId=resource_id,
            httpMethod='OPTIONS',
            type='MOCK',
            requestTemplates={'application/json': '{"statusCode": 200}'}
        )
        
        # Method response
        client.put_method_response(
            restApiId=api_id,
            resourceId=resource_id,
            httpMethod='OPTIONS',
            statusCode='200',
            responseParameters={
                'method.response.header.Access-Control-Allow-Headers': False,
                'method.response.header.Access-Control-Allow-Methods': False,
                'method.response.header.Access-Control-Allow-Origin': False
            }
        )
        
        # Integration response
        client.put_integration_response(
            restApiId=api_id,
            resourceId=resource_id,
            httpMethod='OPTIONS',
            statusCode='200',
            responseParameters={
                'method.response.header.Access-Control-Allow-Headers': "'Content-Type,Authorization,X-Amz-Date,X-Api-Key'",
                'method.response.header.Access-Control-Allow-Methods': "'POST,OPTIONS'",
                'method.response.header.Access-Control-Allow-Origin': "'*'"
            }
        )
        print(f"  Done: {path}")
    except Exception as e:
        print(f"  Skip {path}: {e}")

# Redeploy
client.create_deployment(restApiId=api_id, stageName='prod')
print("Redeployed!")
