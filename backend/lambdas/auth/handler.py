"""
Auth Lambda — helper for any custom auth flows.
Primary authentication is handled entirely by API Gateway's JWT Cognito Authorizer.
This Lambda is reserved for future custom auth helpers if needed.
"""
import json


def lambda_handler(event, context):
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"message": "Auth is handled by Cognito JWT Authorizer"}),
    }
