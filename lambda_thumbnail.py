import boto3
import json
import os
import cv2
import numpy as np

s3 = boto3.client('s3')

BUCKET = 'aussie-ecolens-hkri0008'
THUMBNAIL_PREFIX = 'thumbnails/'
MAX_SIZE = 300  # max width or height in pixels

def lambda_handler(event, context):
    try:
        record = event['Records'][0]['s3']
        bucket = record['bucket']['name']
        key = record['object']['key']

        print(f"Processing file: {key} from bucket: {bucket}")

        # Only process files in originals/images/ folder
        if not key.startswith('originals/images/'):
            print(f"Skipping {key} - not in originals/images/")
            return {'statusCode': 200, 'body': 'Skipped'}

        # Only process image files
        lower_key = key.lower()
        if not any(lower_key.endswith(ext) for ext in ['.jpg', '.jpeg', '.png']):
            print(f"Skipping {key} - not an image file")
            return {'statusCode': 200, 'body': 'Skipped - not an image'}

        # Download image from S3 into memory
        response = s3.get_object(Bucket=bucket, Key=key)
        image_data = response['Body'].read()

        # Decode image using OpenCV
        np_arr = np.frombuffer(image_data, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        if img is None:
            raise ValueError(f"Could not decode image: {key}")

        # Get original dimensions
        h, w = img.shape[:2]
        print(f"Original size: {w}x{h}")

        # Maintain aspect ratio - assignment requirement
        if w > h:
            new_w = MAX_SIZE
            new_h = int(h * MAX_SIZE / w)
        else:
            new_h = MAX_SIZE
            new_w = int(w * MAX_SIZE / h)

        # Resize using OpenCV - assignment says use OpenCV
        thumbnail = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
        print(f"Thumbnail size: {new_w}x{new_h}")

        # Encode as JPEG with compression
        encode_params = [cv2.IMWRITE_JPEG_QUALITY, 85]
        _, buffer = cv2.imencode('.jpg', thumbnail, encode_params)
        thumb_bytes = buffer.tobytes()

        # Build thumbnail key
        filename = os.path.basename(key)
        name_no_ext = os.path.splitext(filename)[0]
        thumb_key = f"{THUMBNAIL_PREFIX}thumb_{name_no_ext}.jpg"

        # Upload thumbnail to S3
        s3.put_object(
            Bucket=BUCKET,
            Key=thumb_key,
            Body=thumb_bytes,
            ContentType='image/jpeg'
        )

        thumb_url = f"https://{BUCKET}.s3.amazonaws.com/{thumb_key}"
        print(f"Thumbnail saved to: {thumb_url}")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Thumbnail created successfully',
                'thumbnail_url': thumb_url,
                'original_key': key,
                'original_size': f"{w}x{h}",
                'thumbnail_size': f"{new_w}x{new_h}"
            })
        }

    except Exception as e:
        print(f"ERROR: {str(e)}")
        raise e