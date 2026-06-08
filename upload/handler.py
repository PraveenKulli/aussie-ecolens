import json, os, uuid, boto3
from boto3.dynamodb.conditions import Key
s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
lc = boto3.client("lambda")
table = dynamodb.Table(os.environ["DYNAMODB_TABLE"])
BUCKET = os.environ["S3_BUCKET"]
TAGGER = os.environ.get("TAGGER_FUNCTION_NAME","aussie-ecolens-tagger")

def _r(s,b):
    return {"statusCode":s,"headers":{"Content-Type":"application/json","Access-Control-Allow-Origin":"*","Access-Control-Allow-Headers":"*"},"body":json.dumps(b)}

def handle_presign(event):
    body=json.loads(event.get("body") or "{}")
    fn=body.get("filename",""); cs=body.get("checksum",""); ct=body.get("content_type","image/jpeg")
    if not fn or not cs: return _r(400,{"error":"filename and checksum required"})
    ex=table.query(IndexName="checksum-index",KeyConditionExpression=Key("checksum").eq(cs))
    if ex["Items"]:
        i=ex["Items"][0]; return _r(200,{"duplicate":True,"file_url":i.get("file_url"),"thumbnail_url":i.get("thumbnail_url"),"tags":i.get("tags",[])})
    ext=os.path.splitext(fn)[1].lower(); fid=str(uuid.uuid4()); key=f"uploads/{fid}{ext}"
    url=s3.generate_presigned_url("put_object",Params={"Bucket":BUCKET,"Key":key,"ContentType":ct},ExpiresIn=300)
    return _r(200,{"duplicate":False,"upload_url":url,"file_key":key,"file_id":fid})

def handle_confirm(event):
    body=json.loads(event.get("body") or "{}")
    fk=body.get("file_key",""); fn=body.get("filename",""); cs=body.get("checksum",""); ct=body.get("content_type","image/jpeg")
    if not fk or not cs: return _r(400,{"error":"file_key and checksum required"})
    ext=os.path.splitext(fk)[1].lower()
    ft="video" if ext in {".mp4",".mov",".avi",".mkv"} else "image"
    fid=fk.split("/")[-1].split(".")[0]; furl=f"https://{BUCKET}.s3.amazonaws.com/{fk}"
    table.put_item(Item={"file_id":fid,"file_key":fk,"filename":fn,"file_url":furl,"thumbnail_url":"pending","checksum":cs,"content_type":ct,"file_type":ft,"tags":[],"status":"processing"})
    try:
        lc.invoke(FunctionName=TAGGER,InvocationType="Event",Payload=json.dumps({"file_id":fid,"file_key":fk,"file_url":furl,"file_type":ft,"bucket":BUCKET}))
        print(f"Tagger invoked for {fid}")
    except Exception as e:
        print(f"Tagger invoke failed: {e}")
    return _r(200,{"message":"Upload confirmed. Processing started.","file_id":fid,"file_url":furl})

def lambda_handler(event,context):
    path=event.get("rawPath",event.get("path",""))
    if "/upload/presign" in path: return handle_presign(event)
    if "/upload/confirm" in path: return handle_confirm(event)
    return _r(404,{"error":"Not found"})
