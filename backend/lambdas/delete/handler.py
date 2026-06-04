"""
Delete Lambda — removes files and their thumbnails from S3 and DynamoDB
  POST /delete
  Body: { "urls": ["https://bucket.s3.amazonaws.com/uploads/uuid.jpg", ...] }
"""

import json
import os
import urllib.parse
import boto3
from boto3.dynamodb.conditions import Attr

s3       = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
table    = dynamodb.Table(os.environ["DYNAMODB_TABLE"])
BUCKET   = os.environ["S3_BUCKET"]


def _response(status, body):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body),
    }


def url_to_s3_key(url: str) -> str:
    """https://bucket.s3.amazonaws.com/uploads/uuid.jpg → uploads/uuid.jpg"""
    parsed = urllib.parse.urlparse(url)
    return parsed.path.lstrip("/")


def delete_s3_object(key: str):
    try:
        s3.delete_object(Bucket=BUCKET, Key=key)
        print(f"[delete] Deleted S3 object: {key}")
    except Exception as e:
        print(f"[delete] Failed to delete S3 {key}: {e}")


def find_item_by_url(file_url: str) -> dict | None:
    resp  = table.scan(FilterExpression=Attr("file_url").eq(file_url))
    items = resp.get("Items", [])
    return items[0] if items else None


def lambda_handler(event, context):
    body = json.loads(event.get("body") or "{}")
    urls = body.get("urls", [])

    if not urls:
        return _response(400, {"error": "urls list is required"})

    deleted = []
    errors  = []

    for url in urls:
        item = find_item_by_url(url)
        if not item:
            errors.append({"url": url, "error": "File not found in database"})
            continue

        file_id   = item["file_id"]
        file_key  = item.get("file_key", url_to_s3_key(url))
        thumb_url = item.get("thumbnail_url", "")
        frame_urls = item.get("frame_urls", [])

        # Delete main file from S3
        delete_s3_object(file_key)

        # Delete thumbnail from S3
        if thumb_url:
            delete_s3_object(url_to_s3_key(thumb_url))

        # Delete all video frame thumbnails
        for frame_url in frame_urls:
            delete_s3_object(url_to_s3_key(frame_url))

        # Delete DynamoDB record
        table.delete_item(Key={"file_id": file_id})
        print(f"[delete] DynamoDB record deleted: {file_id}")

        deleted.append({"url": url, "file_id": file_id})

    return _response(200, {
        "deleted": deleted,
        "errors":  errors,
        "message": f"Deleted {len(deleted)} file(s)",
    })
