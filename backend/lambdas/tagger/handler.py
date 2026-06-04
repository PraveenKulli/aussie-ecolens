"""
Tagger Lambda (AWS) — triggered by S3 upload.
  1. Downloads the file from S3
  2. Calls the GCP Cloud Function (multi-cloud!) which runs MegaDetector + SpeciesNet
  3. Saves detected tags, file type, and URLs to DynamoDB
  4. Publishes SNS notification for any watched tags
"""

import json
import os
import tempfile
import urllib.request
import boto3

s3       = boto3.client("s3")
sns      = boto3.client("sns")
dynamodb = boto3.resource("dynamodb")
table    = dynamodb.Table(os.environ["DYNAMODB_TABLE"])

BUCKET           = os.environ["S3_BUCKET"]
SNS_TOPIC_ARN    = os.environ["SNS_TOPIC_ARN"]
GCP_FUNCTION_URL = os.environ.get("GCP_FUNCTION_URL", "")

VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}


def _s3_key_to_file_id(key: str) -> str:
    return os.path.splitext(os.path.basename(key))[0]


def call_gcp_tagger(s3_key: str, file_url: str, file_type: str) -> list:
    """
    Call GCP Cloud Function with the S3 URL.
    GCP function downloads the image/video from S3, runs MegaDetector + SpeciesNet,
    and returns a list of detected species tags.
    Returns: ["Sus_scrofa", "Felis_catus", ...]
    """
    if not GCP_FUNCTION_URL:
        print("[tagger] No GCP_FUNCTION_URL configured, using fallback local inference")
        return run_local_inference(s3_key, file_type)

    payload = json.dumps({
        "file_url":  file_url,
        "file_type": file_type,
        "s3_key":    s3_key,
        "s3_bucket": BUCKET,
    }).encode("utf-8")

    req = urllib.request.Request(
        GCP_FUNCTION_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=240) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            tags = result.get("tags", [])
            print(f"[tagger] GCP returned tags: {tags}")
            return tags
    except Exception as e:
        print(f"[tagger] GCP call failed: {e}. Falling back to local inference.")
        return run_local_inference(s3_key, file_type)


def run_local_inference(s3_key: str, file_type: str) -> list:
    """
    Fallback: run inference locally inside the Lambda.
    This is used when GCP is unavailable. Requires the ML layer.
    """
    try:
        import torch
        import torchvision.transforms as transforms
        from PIL import Image
        import numpy as np

        CLASSES = [
            'Alectura_lathami', 'Antechinus_agilis', 'Bos_taurus', 'Burhinus_grallarius',
            'Canis_familiaris', 'Chalcophaps_longirostris', 'Colluricincla_harmonica',
            'Corcorax_melanorhamphos', 'Dacelo_novaeguineae', 'Dama_dama',
            'Eopsaltria_australis', 'Felis_catus', 'Geopelia_humeralis',
            'Gymnorhina_tibicen', 'Homo_sapiens', 'Isoodon_macrourus',
            'Lepus_europaeus', 'Macropus_giganteus', 'Menura_novaehollandiae',
            'Mus_musculus', 'Oryctolagus_cuniculus', 'Perameles_nasuta',
            'Pitta_versicolor', 'Rattus', 'Rattus_fuscipes', 'Rattus_rattus',
            'Strepera_graculina', 'Sus_scrofa', 'Tachyglossus_aculeatus',
            'Thylogale_stigmatica', 'Trichosurus_caninus', 'Trichosurus_cunninghami',
            'Trichosurus_vulpecula', 'Varanus_varius', 'Vombatus_ursinus',
            'Vulpes_vulpes', 'Wallabia_bicolor', 'Canis_dingo', 'Capra_hircus',
            'Casuarius_casuarius', 'Heteromyias_cinereifrons',
            'Hypsiprymnodon_moschatus', 'Megapodius_reinwardt',
            'Notamacropus_rufogriseus', 'Orthonyx_spaldingii', 'Uromys_caudimaculatus',
        ]

        MODEL_PATH = "/opt/model.pt"
        if not os.path.exists(MODEL_PATH):
            print("[tagger] model.pt not found in layer, returning empty tags")
            return []

        device = "cpu"
        model = torch.load(MODEL_PATH, map_location=device, weights_only=False)
        model.eval()
        model.to(device)

        transform = transforms.Compose([
            transforms.Resize((480, 480)),
            transforms.ToTensor(),
        ])

        CONF_THRESHOLD = 0.15

        with tempfile.TemporaryDirectory() as tmpdir:
            ext      = os.path.splitext(s3_key)[1].lower()
            src_path = os.path.join(tmpdir, f"input{ext}")
            s3.download_file(BUCKET, s3_key, src_path)

            if file_type == "video":
                import cv2
                cap = cv2.VideoCapture(src_path)
                fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
                frame_interval = int(fps)
                images_to_classify = []
                fi = 0
                while True:
                    ret, frame = cap.read()
                    if not ret:
                        break
                    if fi % frame_interval == 0:
                        rgb   = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        pil   = Image.fromarray(rgb)
                        images_to_classify.append(pil)
                    fi += 1
                cap.release()
            else:
                images_to_classify = [Image.open(src_path).convert("RGB")]

            tag_counts: dict[str, int] = {}

            @torch.no_grad()
            def classify(pil_img):
                t = transform(pil_img).unsqueeze(0).permute(0, 2, 3, 1).to(device)
                logits = model(t)
                probs  = torch.softmax(logits, dim=1)[0].cpu().numpy()
                best   = int(np.argmax(probs))
                if probs[best] >= CONF_THRESHOLD:
                    return CLASSES[best]
                return None

            for img in images_to_classify:
                tag = classify(img)
                if tag:
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1

            return list(tag_counts.keys())

    except Exception as e:
        print(f"[tagger] Local inference error: {e}")
        return []


def publish_notifications(tags: list, file_url: str):
    """Publish SNS notification for new tags."""
    if not tags:
        return
    try:
        message = {
            "event":    "new_file_tagged",
            "tags":     tags,
            "file_url": file_url,
        }
        sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Message=json.dumps(message),
            Subject=f"New wildlife detected: {', '.join(tags[:3])}",
            MessageAttributes={
                "tags": {
                    "DataType":    "String.Array",
                    "StringValue": json.dumps(tags),
                }
            },
        )
        print(f"[tagger] SNS published for tags: {tags}")
    except Exception as e:
        print(f"[tagger] SNS publish error: {e}")


def lambda_handler(event, context):
    for record in event.get("Records", []):
        s3_key  = record["s3"]["object"]["key"]
        ext     = os.path.splitext(s3_key)[1].lower()
        file_id = _s3_key_to_file_id(s3_key)
        file_url = f"https://{BUCKET}.s3.amazonaws.com/{s3_key}"

        file_type = "video" if ext in VIDEO_EXTS else "image"

        print(f"[tagger] Processing {s3_key} ({file_type})")

        tags = call_gcp_tagger(s3_key, file_url, file_type)

        # Update DynamoDB
        # Derive expected thumbnail URL (thumbnail Lambda writes to thumbnails/<file_id>.jpg)
        thumb_url = f"https://{BUCKET}.s3.amazonaws.com/thumbnails/{file_id}.jpg"

        table.update_item(
            Key={"file_id": file_id},
            UpdateExpression=(
                "SET tags = :t, #st = :s, file_type = :ft, "
                "file_url = :fu, thumbnail_url = if_not_exists(thumbnail_url, :thu)"
            ),
            ExpressionAttributeNames={"#st": "status"},
            ExpressionAttributeValues={
                ":t":   tags,
                ":s":   "ready",
                ":ft":  file_type,
                ":fu":  file_url,
                ":thu": thumb_url,   # only set if thumbnail Lambda hasn't already
            },
        )
        print(f"[tagger] DB updated — tags: {tags}, file_url: {file_url}")

        publish_notifications(tags, file_url)
