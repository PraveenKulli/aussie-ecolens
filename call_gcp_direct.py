import boto3
import json
import urllib.request

s3 = boto3.client('s3', region_name='us-east-1')
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
table = dynamodb.Table('aussie-ecolens-files')
GCP_URL = "https://us-central1-aussie-ecolens-498402.cloudfunctions.net/aussie-ecolens-tagger"
BUCKET = "aussie-ecolens-media-8a763a3b"

objects = s3.list_objects_v2(Bucket=BUCKET, Prefix="uploads/")
files = [o["Key"] for o in objects.get("Contents", []) if not o["Key"].endswith("/")]
print(f"Found {len(files)} files in S3")

for key in files:
    file_url = f"https://{BUCKET}.s3.amazonaws.com/{key}"
    file_id = key.split("/")[-1].split(".")[0]
    print(f"Tagging {key}...")
    try:
        payload = json.dumps({"file_url": file_url, "file_type": "image"}).encode()
        req = urllib.request.Request(GCP_URL, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read())
            tags = result.get("tags", [])
            print(f"  Tags: {tags}")
            table.update_item(
                Key={"file_id": file_id},
                UpdateExpression="SET tags = :t, #st = :s",
                ExpressionAttributeNames={"#st": "status"},
                ExpressionAttributeValues={":t": tags, ":s": "ready"}
            )
            print(f"  Saved!")
    except Exception as e:
        print(f"  Error: {e}")

print("All done!")
