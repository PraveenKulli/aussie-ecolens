import boto3
import json
import hashlib
import base64
import os
from boto3.dynamodb.conditions import Attr

s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
table = dynamodb.Table('AussieEcoLens')

BUCKET = 'aussie-ecolens-hkri0008'

def compute_checksum(file_bytes):
    return hashlib.md5(file_bytes).hexdigest()

def check_duplicate(checksum):
    response = table.scan(
        FilterExpression=Attr('checksum').eq(checksum)
    )
    return len(response.get('Items', [])) > 0

def is_video(filename):
    return any(filename.lower().endswith(ext) for ext in ['.mp4', '.avi', '.mov', '.mkv', '.wmv'])

def is_image(filename):
    return any(filename.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'])

def lambda_handler(event, context):
    try:
        body = event.get('body', '')

        if event.get('isBase64Encoded', False):
            file_bytes = base64.b64decode(body)
        else:
            file_bytes = body.encode() if isinstance(body, str) else body

        headers = event.get('headers') or {}
        query_params = event.get('queryStringParameters') or {}

        filename = (
            headers.get('x-filename') or
            headers.get('X-Filename') or
            query_params.get('filename') or
            'uploaded_file.jpg'
        )

        print(f"Upload request for: {filename}")

        # Compute MD5 checksum for deduplication
        checksum = compute_checksum(file_bytes)
        print(f"File checksum: {checksum}")

        # Check for duplicate
        if check_duplicate(checksum):
            print(f"Duplicate file detected: {checksum}")
            return {
                'statusCode': 409,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'message': 'Duplicate file - this file already exists in the system',
                    'checksum': checksum
                })
            }

        # Determine file type and upload to correct folders
        if is_video(filename):
            # Videos go to originals/videos/ - triggers video Lambda
            s3_key = f'originals/videos/{filename}'
            s3.put_object(Bucket=BUCKET, Key=s3_key, Body=file_bytes)
            file_type = 'video'
            original_url = f"https://{BUCKET}.s3.amazonaws.com/{s3_key}"
            thumbnail_url = ''

        elif is_image(filename):
            # Images go to BOTH originals/images/ (thumbnail) AND originals/ml/ (ML detection)
            images_key = f'originals/images/{filename}'
            ml_key = f'originals/ml/{filename}'

            s3.put_object(Bucket=BUCKET, Key=images_key, Body=file_bytes, ContentType='image/jpeg')
            print(f"Uploaded to images folder: {images_key}")

            s3.put_object(Bucket=BUCKET, Key=ml_key, Body=file_bytes, ContentType='image/jpeg')
            print(f"Uploaded to ml folder: {ml_key}")

            s3_key = images_key
            file_type = 'image'
            original_url = f"https://{BUCKET}.s3.amazonaws.com/{images_key}"
            thumbnail_url = f"https://{BUCKET}.s3.amazonaws.com/thumbnails/thumb_{filename}"
        else:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'message': 'Unsupported file type'})
            }

        # Save to DynamoDB with checksum for deduplication
        file_id = checksum
        table.put_item(Item={
            'file_id': file_id,
            'file_key': s3_key,
            'file_type': file_type,
            'original_url': original_url,
            'thumbnail_url': thumbnail_url,
            'tags': {},
            'filename': filename,
            'checksum': checksum
        })

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'message': 'File uploaded successfully',
                'filename': filename,
                'checksum': checksum,
                'original_url': original_url,
                's3_key': s3_key
            })
        }

    except Exception as e:
        print(f"ERROR: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': str(e)})
        }