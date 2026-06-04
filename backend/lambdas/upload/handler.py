"""
Upload Lambda — two endpoints:
  POST /upload/presign  → returns a pre-signed S3 URL + checks for duplicates via SHA-256 checksum
  POST /upload/confirm  → called after direct upload to trigger tagging pipeline
"""

import json
import os
import uuid
import boto3
from boto3.dynamodb.conditions import Key

s3        = boto3.client("s3")
dynamodb  = boto3.resource("dynamodb")
table     = dynamodb.Table(os.environ["DYNAMODB_TABLE"])
BUCKET    = os.environ["S3_BUCKET"]


def _response(status, body):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
        },
        "body": json.dumps(body),
    }


def handle_presign(event):
    """
    Body: { "filename": "photo.jpg", "checksum": "<sha256_hex>", "content_type": "image/jpeg" }
    Returns: { "upload_url": "...", "file_key": "...", "duplicate": false }
    """
    body = json.loads(event.get("body") or "{}")
    filename     = body.get("filename", "")
    checksum     = body.get("checksum", "")
    content_type = body.get("content_type", "image/jpeg")

    if not filename or not checksum:
        return _response(400, {"error": "filename and checksum are required"})

    # ── Deduplication check ──────────────────────────────────────────────
    existing = table.query(
        IndexName="checksum-index",
        KeyConditionExpression=Key("checksum").eq(checksum),
    )
    if existing["Items"]:
        item = existing["Items"][0]
        return _response(200, {
            "duplicate": True,
            "message":   "File already exists in the system",
            "file_url":  item.get("file_url"),
            "thumbnail_url": item.get("thumbnail_url"),
            "tags":      item.get("tags", []),
        })

    # ── Generate pre-signed upload URL ──────────────────────────────────
    ext     = os.path.splitext(filename)[1].lower()
    file_id = str(uuid.uuid4())
    key     = f"uploads/{file_id}{ext}"

    presigned_url = s3.generate_presigned_url(
        "put_object",
        Params={
            "Bucket":      BUCKET,
            "Key":         key,
            "ContentType": content_type,
        },
        ExpiresIn=300,  # 5 minutes
    )

    return _response(200, {
        "duplicate":  False,
        "upload_url": presigned_url,
        "file_key":   key,
        "file_id":    file_id,
    })


def handle_confirm(event):
    """
    Body: { "file_key": "uploads/uuid.jpg", "filename": "photo.jpg",
            "checksum": "<sha256_hex>", "content_type": "image/jpeg" }
    Writes an initial DB record so the tagger can update it.
    """
    body = json.loads(event.get("body") or "{}")
    file_key     = body.get("file_key", "")
    filename     = body.get("filename", "")
    checksum     = body.get("checksum", "")
    content_type = body.get("content_type", "image/jpeg")

    if not file_key or not checksum:
        return _response(400, {"error": "file_key and checksum are required"})

    # Determine file type
    ext = os.path.splitext(file_key)[1].lower()
    file_type = "video" if ext in {".mp4", ".mov", ".avi", ".mkv"} else "image"

    file_id  = file_key.split("/")[-1].split(".")[0]
    file_url = f"https://{BUCKET}.s3.amazonaws.com/{file_key}"

    table.put_item(Item={
        "file_id":      file_id,
        "file_key":     file_key,
        "filename":     filename,
        "file_url":     file_url,
        "thumbnail_url": "",
        "checksum":     checksum,
        "content_type": content_type,
        "file_type":    file_type,
        "tags":         [],
        "status":       "processing",
    })

    return _response(200, {
        "message":  "Upload confirmed. Processing started.",
        "file_id":  file_id,
        "file_url": file_url,
    })


def lambda_handler(event, context):
    path = event.get("rawPath", event.get("path", ""))

    if "/upload/presign" in path:
        return handle_presign(event)
    elif "/upload/confirm" in path:
        return handle_confirm(event)

    return _response(404, {"error": "Not found"})
