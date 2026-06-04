import boto3

s3 = boto3.client('s3', region_name='us-east-1')
lambda_client = boto3.client('lambda', region_name='us-east-1')

bucket = 'aussie-ecolens-media-8a763a3b'

# Get tagger Lambda ARN
tagger = lambda_client.get_function(FunctionName='aussie-ecolens-tagger')
tagger_arn = tagger['Configuration']['FunctionArn']
thumb = lambda_client.get_function(FunctionName='aussie-ecolens-thumbnail')
thumb_arn = thumb['Configuration']['FunctionArn']

print(f"Tagger ARN: {tagger_arn}")

# Set notification with different suffixes to avoid overlap
s3.put_bucket_notification_configuration(
    Bucket=bucket,
    NotificationConfiguration={
        'LambdaFunctionConfigurations': [
            {
                'LambdaFunctionArn': thumb_arn,
                'Events': ['s3:ObjectCreated:*'],
                'Filter': {
                    'Key': {
                        'FilterRules': [
                            {'Name': 'prefix', 'Value': 'uploads/'},
                            {'Name': 'suffix', 'Value': '.jpg'},
                        ]
                    }
                }
            },
            {
                'LambdaFunctionArn': tagger_arn,
                'Events': ['s3:ObjectCreated:*'],
                'Filter': {
                    'Key': {
                        'FilterRules': [
                            {'Name': 'prefix', 'Value': 'uploads/'},
                            {'Name': 'suffix', 'Value': '.JPG'},
                        ]
                    }
                }
            },
        ]
    }
)
print("S3 notification updated!")
