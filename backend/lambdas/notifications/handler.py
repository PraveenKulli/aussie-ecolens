"""
Notifications Lambda — subscribe/unsubscribe to tag-based email alerts
  POST /notifications/subscribe   → { "email": "...", "tags": ["Sus_scrofa", ...] }
  POST /notifications/unsubscribe → { "subscription_arn": "..." }
"""

import json
import os
import boto3

sns      = boto3.client("sns")
dynamodb = boto3.resource("dynamodb")
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


def handle_subscribe(body: dict) -> dict:
    email = body.get("email", "").strip()
    tags  = body.get("tags", [])

    if not email:
        return _response(400, {"error": "email is required"})
    if not tags:
        return _response(400, {"error": "tags list is required"})

    filter_policy = json.dumps({"tags": tags})

    try:
        resp = sns.subscribe(
            TopicArn=SNS_ARN,
            Protocol="email",
            Endpoint=email,
            Attributes={"FilterPolicy": filter_policy},
            ReturnSubscriptionArn=True,
        )
        subscription_arn = resp.get("SubscriptionArn", "")
        return _response(200, {
            "message":          f"Subscription pending email confirmation for {email}",
            "subscription_arn": subscription_arn,
            "watched_tags":     tags,
            "note":             "Check your email and click the confirmation link to activate notifications",
        })
    except Exception as e:
        return _response(500, {"error": str(e)})


def handle_unsubscribe(body: dict) -> dict:
    sub_arn = body.get("subscription_arn", "").strip()
    if not sub_arn:
        return _response(400, {"error": "subscription_arn is required"})

    try:
        sns.unsubscribe(SubscriptionArn=sub_arn)
        return _response(200, {"message": "Unsubscribed successfully"})
    except Exception as e:
        return _response(400, {"error": str(e)})


def lambda_handler(event, context):
    path = event.get("rawPath", event.get("path", ""))
    body = json.loads(event.get("body") or "{}")

    if "unsubscribe" in path:
        return handle_unsubscribe(body)
    else:
        return handle_subscribe(body)
