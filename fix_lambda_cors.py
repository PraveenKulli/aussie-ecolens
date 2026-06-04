import os
import re

cors_headers = """    "headers": {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Amz-Date,X-Api-Key",
        "Access-Control-Allow-Methods": "POST,OPTIONS",
    },"""

lambdas = [
    "backend/lambdas/upload/handler.py",
    "backend/lambdas/queries/handler.py",
    "backend/lambdas/tags/handler.py",
    "backend/lambdas/delete/handler.py",
    "backend/lambdas/notifications/handler.py",
    "backend/lambdas/tagger/handler.py",
]

for path in lambdas:
    with open(path, encoding="utf-8") as f:
        content = f.read()
    
    old = '''    "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
        },'''
    
    print(f"Checking {path}... headers present: {'Access-Control-Allow-Origin' in content}")

print("Done checking")
