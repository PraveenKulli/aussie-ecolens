"""
Thumbnail Lambda — triggered automatically when a file lands in s3://bucket/uploads/
  • Images  → resize to max 300px (longest side), maintain aspect ratio, JPEG compress
  • Videos  → extract 1 frame per second using OpenCV, save each frame as an image,
              then thumbnail each frame
Updates the DynamoDB record with thumbnail_url (for images) or frame_urls (for videos).
"""

import json
import os
import tempfile
import boto3
import cv2
from boto3.dynamodb.conditions import Attr

s3       = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
table    = dynamodb.Table(os.environ["DYNAMODB_TABLE"])
BUCKET   = os.environ["S3_BUCKET"]

THUMB_MAX_PX   = 300   # longest side in pixels
THUMB_QUALITY  = 85    # JPEG quality 0-100
VIDEO_EXTS     = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
IMAGE_EXTS     = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"}


def _s3_key_to_file_id(key: str) -> str:
    """uploads/abc123.jpg → abc123"""
    return os.path.splitext(os.path.basename(key))[0]


def _upload_thumbnail(local_path: str, thumb_key: str) -> str:
    s3.upload_file(
        local_path, BUCKET, thumb_key,
        ExtraArgs={"ContentType": "image/jpeg"},
    )
    return f"https://{BUCKET}.s3.amazonaws.com/{thumb_key}"


def make_image_thumbnail(s3_key: str) -> str:
    """Download image, resize, re-upload as thumbnail. Returns thumbnail URL."""
    ext = os.path.splitext(s3_key)[1].lower()

    with tempfile.TemporaryDirectory() as tmpdir:
        src_path   = os.path.join(tmpdir, f"original{ext}")
        thumb_path = os.path.join(tmpdir, "thumb.jpg")

        s3.download_file(BUCKET, s3_key, src_path)

        img = cv2.imread(src_path)
        if img is None:
            raise ValueError(f"cv2 could not read image: {s3_key}")

        h, w = img.shape[:2]
        scale = THUMB_MAX_PX / max(h, w)
        new_w = max(1, int(w * scale))
        new_h = max(1, int(h * scale))
        resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)

        cv2.imwrite(thumb_path, resized, [cv2.IMWRITE_JPEG_QUALITY, THUMB_QUALITY])

        file_id   = _s3_key_to_file_id(s3_key)
        thumb_key = f"thumbnails/{file_id}.jpg"
        return _upload_thumbnail(thumb_path, thumb_key)


def make_video_frames(s3_key: str) -> list[str]:
    """
    Download video, extract 1 frame/sec, thumbnail each frame.
    Returns list of frame thumbnail URLs.
    """
    ext = os.path.splitext(s3_key)[1].lower()

    with tempfile.TemporaryDirectory() as tmpdir:
        src_path = os.path.join(tmpdir, f"video{ext}")
        s3.download_file(BUCKET, s3_key, src_path)

        cap = cv2.VideoCapture(src_path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        frame_interval = int(fps)  # 1 frame per second
        file_id = _s3_key_to_file_id(s3_key)

        frame_urls = []
        frame_idx  = 0
        saved_idx  = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % frame_interval == 0:
                # Thumbnail this frame
                h, w = frame.shape[:2]
                scale = THUMB_MAX_PX / max(h, w)
                new_w = max(1, int(w * scale))
                new_h = max(1, int(h * scale))
                resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)

                frame_path = os.path.join(tmpdir, f"frame_{saved_idx}.jpg")
                cv2.imwrite(frame_path, resized, [cv2.IMWRITE_JPEG_QUALITY, THUMB_QUALITY])

                thumb_key = f"thumbnails/{file_id}_frame{saved_idx}.jpg"
                url = _upload_thumbnail(frame_path, thumb_key)
                frame_urls.append(url)
                saved_idx += 1

            frame_idx += 1

        cap.release()
        return frame_urls


def lambda_handler(event, context):
    for record in event.get("Records", []):
        s3_key  = record["s3"]["object"]["key"]
        ext     = os.path.splitext(s3_key)[1].lower()
        file_id = _s3_key_to_file_id(s3_key)

        print(f"[thumbnail] Processing {s3_key}")

        try:
            if ext in IMAGE_EXTS:
                thumb_url = make_image_thumbnail(s3_key)
                table.update_item(
                    Key={"file_id": file_id},
                    UpdateExpression="SET thumbnail_url = :t",
                    ExpressionAttributeValues={":t": thumb_url},
                )
                print(f"[thumbnail] Image thumbnail created: {thumb_url}")

            elif ext in VIDEO_EXTS:
                frame_urls = make_video_frames(s3_key)
                table.update_item(
                    Key={"file_id": file_id},
                    UpdateExpression="SET frame_urls = :f, thumbnail_url = :t",
                    ExpressionAttributeValues={
                        ":f": frame_urls,
                        ":t": frame_urls[0] if frame_urls else "",
                    },
                )
                print(f"[thumbnail] Video frames created: {len(frame_urls)} frames")

            else:
                print(f"[thumbnail] Unsupported extension {ext}, skipping.")

        except Exception as e:
            print(f"[thumbnail] ERROR for {s3_key}: {e}")
            raise
