import boto3
import json

dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
lambda_client = boto3.client('lambda', region_name='us-east-1')
table = dynamodb.Table('aussie-ecolens-files')

# Get all files with status processing
response = table.scan()
items = response['Items']

print(f"Found {len(items)} files to process")

for item in items:
    file_key = item.get('file_key', '')
    file_id = item.get('file_id', '')
    
    if not file_key:
        continue
    
    # Simulate S3 trigger event
    event = {
        'Records': [{
            's3': {
                'bucket': {'name': 'aussie-ecolens-media-8a763a3b'},
                'object': {'key': file_key}
            }
        }]
    }
    
    print(f"Triggering tagger for {item.get('filename', '')}...")
    
    try:
        lambda_client.invoke(
            FunctionName='aussie-ecolens-tagger',
            InvocationType='Event',  # async
            Payload=json.dumps(event)
        )
        print(f"  Triggered!")
    except Exception as e:
        print(f"  Error: {e}")

print("All triggered! Wait 2-3 minutes for GCP ML processing to complete.")
