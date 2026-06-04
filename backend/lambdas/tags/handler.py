"""
Tags Lambda — bulk tag addition and removal
  POST /tags
  Body: {
    "urls": ["https://...", "https://..."],
    "tags": ["Sus_scrofa", "Felis_catus"],
    "operation": 1   // 1 = add, 0 = remove
  }
"""

import json
import os
import boto3
from boto3.dynamodb.conditions import Attr

dynamodb = boto3.resource("dynamodb")
sns      = boto3.client("sns")
table    = dynamodb.Table(os.environ["DYNAMODB_TABLE"])
SNS_ARN  = os.environ["SNS_TOPIC_ARN"]


def _response(status, body):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body),
    }


def find_item_by_url(file_url: str) -> dict | None:
    """Find a DynamoDB item by its file_url (scan with filter)."""
    resp = table.scan(
        FilterExpression=Attr("file_url").eq(file_url)
    )
    items = resp.get("Items", [])
    return items[0] if items else None


def lambda_handler(event, context):
    body = json.loads(event.get("body") or "{}")

    urls      = body.get("urls", [])
    new_tags  = body.get("tags", [])
    if isinstance(new_tags, str):
        new_tags = [new_tags]
    operation = body.get("operation", 1)  # 1=add, 0=remove

    if not urls or not new_tags:
        return _response(400, {"error": "urls and tags are required"})
    if operation not in (0, 1):
        return _response(400, {"error": "operation must be 0 (remove) or 1 (add)"})

    updated = []
    errors  = []

    for url in urls:
        item = find_item_by_url(url)
        if not item:
            errors.append({"url": url, "error": "File not found"})
            continue

        file_id       = item["file_id"]
        current_tags = item.get("tags", {})

        # Convert old list-style tags into dictionary format
        if isinstance(current_tags, list):
            tag_counts = {}
            for tag in current_tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        else:
            tag_counts = {
                tag: int(count)
                for tag, count in current_tags.items()
            }
        
        if operation == 1:
            added = []
        
            for tag in new_tags:
                if tag not in tag_counts:
                    added.append(tag)
        
                # Manual add increases the tag count by 1
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        
        else:
            added = []
        
            for tag in new_tags:
                if tag in tag_counts:
                    del tag_counts[tag]
        
        merged = tag_counts

        table.update_item(
            Key={"file_id": file_id},
            UpdateExpression="SET tags = :t",
            ExpressionAttributeValues={":t": merged},
        )
        updated.append({"url": url, "tags": merged})

        # Fire SNS notification for newly added tags
        if operation == 1 and added:
            try:
                sns.publish(
                    TopicArn=SNS_ARN,
                    Message=json.dumps({
                        "event":    "tags_added_manually",
                        "file_url": url,
                        "tags":     added,
                    }),
                    Subject=f"Tags manually added: {', '.join(added[:3])}",
                )
            except Exception as e:
                print(f"[tags] SNS error: {e}")

    return _response(200, {
        "updated": updated,
        "errors":  errors,
        "message": f"Operation {'add' if operation == 1 else 'remove'} completed",
    })
