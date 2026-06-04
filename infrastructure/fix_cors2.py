import boto3

client = boto3.client('apigateway', region_name='us-east-1')
api_id = 'arxwhky463'

resources = client.get_resources(restApiId=api_id, limit=100)

for item in resources['items']:
    resource_id = item['id']
    path = item.get('path', '')
    methods = item.get('resourceMethods', {})
    
    if 'OPTIONS' in methods:
        # Check if OPTIONS has wrong auth
        try:
            method = client.get_method(
                restApiId=api_id,
                resourceId=resource_id,
                httpMethod='OPTIONS'
            )
            auth = method.get('authorizationType', '')
            print(f"{path}: OPTIONS auth = {auth}")
            
            # If not NONE, delete and recreate
            if auth != 'NONE':
                client.delete_method(
                    restApiId=api_id,
                    resourceId=resource_id,
                    httpMethod='OPTIONS'
                )
                client.put_method(
                    restApiId=api_id,
                    resourceId=resource_id,
                    httpMethod='OPTIONS',
                    authorizationType='NONE'
                )
                client.put_integration(
                    restApiId=api_id,
                    resourceId=resource_id,
                    httpMethod='OPTIONS',
                    type='MOCK',
                    requestTemplates={'application/json': '{"statusCode": 200}'}
                )
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
                print(f"  Fixed: {path}")
        except Exception as e:
            print(f"  Error on {path}: {e}")

client.create_deployment(restApiId=api_id, stageName='prod')
print("Redeployed!")
