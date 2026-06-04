"""
Queries Lambda — handles all query endpoints:
  POST /query/tags       → find files by tag names + optional min counts (AND logic)
  POST /query/thumbnail  → find full-size image URL from thumbnail URL
  POST /query/file       → upload temp file, detect tags, find matching files in DB
"""

import json
import os
import tempfile
import urllib.request
import uuid
import boto3
from boto3.dynamodb.conditions import Key

s3       = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
table    = dynamodb.Table(os.environ["DYNAMODB_TABLE"])
BUCKET   = os.environ["S3_BUCKET"]
GCP_URL  = os.environ.get("GCP_FUNCTION_URL", "")


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


def scan_all_files() -> list:
    """Scan all DynamoDB items (pagination-aware)."""
    items = []
    resp  = table.scan()
    items.extend(resp.get("Items", []))
    while "LastEvaluatedKey" in resp:
        resp = table.scan(ExclusiveStartKey=resp["LastEvaluatedKey"])
        items.extend(resp.get("Items", []))
    return items


def handle_query_tags(body: dict) -> dict:
    """
    Body options:
      1. { "tags": {"koala": 3, "wombat": 2} }    → AND logic with min counts
      2. { "species": ["dingo"] }                  → find files with at least 1 of each species
    Returns: { "results": [{ "file_url": ..., "thumbnail_url": ..., "tags": [...] }] }
    """
    tag_query   = body.get("tags", {})      # {"species": count, ...}
    species_query = body.get("species", []) # ["dingo", ...]
  
    if isinstance(species_query, str):
        species_query = [species_query]
  
    # Normalise both query formats into: {species: min_count}
    required: dict[str, int] = {}
    if tag_query:
        required = {k: int(v) for k, v in tag_query.items()}
    elif species_query:
        required = {s: 1 for s in species_query}
    else:
        return _response(400, {"error": "Provide 'tags' or 'species' in request body"})

    all_items = scan_all_files()
    results   = []

    for item in all_items:
        if item.get("status") != "ready":
            continue
        item_tags = item.get("tags", [])

        if isinstance(item_tags, dict):
            tag_counts = {
                k: int(v)
                for k, v in item_tags.items()
            }
        else:
            tag_counts = {}
            for t in item_tags:
                tag_counts[t] = tag_counts.get(t, 0) + 1

        # AND logic: every required species must appear with >= min count
        match = all(
            tag_counts.get(species, 0) >= min_count
            for species, min_count in required.items()
        )

        if match:
            results.append({
                "file_url":      item.get("file_url", ""),
                "thumbnail_url": item.get("thumbnail_url", ""),
                "frame_urls":    item.get("frame_urls", []),
                "file_type":     item.get("file_type", "image"),
                "tags":          item_tags,
                "file_id":       item.get("file_id", ""),
            })

    return _response(200, {"count": len(results), "results": results})


def handle_query_thumbnail(body: dict) -> dict:
    """
    Body: { "thumbnail_url": "https://..." }
    Returns: { "file_url": "https://..." }
    """
    thumb_url = body.get("thumbnail_url", "").strip()
    if not thumb_url:
        return _response(400, {"error": "thumbnail_url is required"})

    results = table.query(
        IndexName="thumbnail-index",
        KeyConditionExpression=Key("thumbnail_url").eq(thumb_url),
    )
    items = results.get("Items", [])
    if not items:
        return _response(404, {"error": "No file found for this thumbnail URL"})

    item = items[0]
    return _response(200, {
        "file_url":      item.get("file_url", ""),
        "thumbnail_url": thumb_url,
        "tags":          item.get("tags", []),
        "file_id":       item.get("file_id", ""),
    })


def call_gcp_for_tags(file_url: str, file_type: str) -> list:
    """Send a file URL to GCP Cloud Function to get tags."""
    if not GCP_URL:
        return []
    payload = json.dumps({
        "file_url":  file_url,
        "file_type": file_type,
    }).encode()
    req = urllib.request.Request(GCP_URL, data=payload,
                                 headers={"Content-Type": "application/json"},
                                 method="POST")
    try:
        with urllib.request.urlopen(req, timeout=240) as resp:
            result = json.loads(resp.read())
            return result.get("tags", [])
    except Exception as e:
        print(f"[queries] GCP tag detection failed: {e}")
        return []


def handle_query_file(event: dict) -> dict:
    """
    Accepts a base64-encoded file (or multipart) in the body.
    Runs ML detection (via GCP), searches DB for matching files.
    Does NOT permanently store the query file.
    Body: { "file_base64": "<base64>", "content_type": "image/jpeg", "filename": "photo.jpg" }
    """
    import base64
    body = json.loads(event.get("body") or "{}")
    file_b64     = body.get("file_base64", "")
    content_type = body.get("content_type", "image/jpeg")
    filename     = body.get("filename", "query.jpg")

    if not file_b64:
        return _response(400, {"error": "file_base64 is required"})

    ext     = os.path.splitext(filename)[1].lower() or ".jpg"
    tmp_key = f"temp_query/{uuid.uuid4()}{ext}"

    try:
        file_bytes = base64.b64decode(file_b64)

        # Upload to S3 temporarily (GCP needs a URL to download from)
        s3.put_object(
            Bucket=BUCKET,
            Key=tmp_key,
            Body=file_bytes,
            ContentType=content_type,
        )
        tmp_url = f"https://{BUCKET}.s3.amazonaws.com/{tmp_key}"

        file_type = "video" if ext in {".mp4", ".mov", ".avi", ".mkv"} else "image"
        detected_tags = call_gcp_for_tags(tmp_url, file_type)

        if not detected_tags:
            return _response(200, {
                "detected_tags": [],
                "results":       [],
                "message":       "No species detected in the query file",
            })

        # Find all DB files that contain ALL detected tags
        all_items = scan_all_files()
        results   = []
        for item in all_items:
            if item.get("status") != "ready":
                continue
            item_tags = set(item.get("tags", []))
            if all(t in item_tags for t in detected_tags):
                results.append({
                    "file_url":      item.get("file_url", ""),
                    "thumbnail_url": item.get("thumbnail_url", ""),
                    "file_type":     item.get("file_type", "image"),
                    "tags":          list(item_tags),
                })

        return _response(200, {
            "detected_tags": detected_tags,
            "count":         len(results),
            "results":       results,
        })

    finally:
        # Always delete temporary file — never stored permanently
        try:
            s3.delete_object(Bucket=BUCKET, Key=tmp_key)
            print(f"[queries] Temp query file deleted: {tmp_key}")
        except Exception as e:
            print(f"[queries] Failed to delete temp file: {e}")


def lambda_handler(event, context):
    path = event.get("rawPath", event.get("path", ""))
    body = json.loads(event.get("body") or "{}")

    if "/query/tags" in path:
        return handle_query_tags(body)
    elif "/query/species" in path:
        return handle_query_tags(body)
    elif "/query/thumbnail" in path:
        return handle_query_thumbnail(body)
    elif "/query/file" in path:
        return handle_query_file(event)

    return _response(404, {"error": "Not found"})
