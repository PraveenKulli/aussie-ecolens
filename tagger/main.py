"""
GCP Cloud Function — ML Tagger
This is the MULTI-CLOUD component running on Google Cloud Functions.
It receives a file URL (from AWS S3), runs MegaDetector + SpeciesNet,
and returns detected species tags.

Deploy: gcloud functions deploy aussie-ecolens-tagger \
          --runtime python312 \
          --trigger-http \
          --allow-unauthenticated \
          --memory 2GB \
          --timeout 300s \
          --entry-point tagger \
          --set-env-vars MODEL_BUCKET=aussie-ecolens-models-<project_id>

The model.pt and mdv5a.pt files must be in the GCP Cloud Storage bucket.
"""

import json
import os
import tempfile
import urllib.request
import functions_framework
from flask import jsonify

# GCP Cloud Storage
from google.cloud import storage as gcs_storage

GCS_BUCKET  = os.environ.get("MODEL_BUCKET", "")
MODEL_FILE  = "model.pt"
MD_FILE     = "mdv5a.pt"

# Download models once at cold start (cached in /tmp)
_model     = None
_md_model  = None
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
CONF_THRESHOLD = 0.15
VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}


def _download_model_from_gcs(model_filename: str, local_path: str):
    """Download model from GCP Cloud Storage bucket (swappable without code change)."""
    if os.path.exists(local_path):
        print(f"[gcp-tagger] Using cached model at {local_path}")
        return
    print(f"[gcp-tagger] Downloading {model_filename} from GCS bucket {GCS_BUCKET}")
    client = gcs_storage.Client()
    bucket = client.bucket(GCS_BUCKET)
    blob   = bucket.blob(model_filename)
    blob.download_to_filename(local_path)
    print(f"[gcp-tagger] Downloaded {model_filename} → {local_path}")


def get_speciesnet_model():
    global _model
    if _model is not None:
        return _model
    import torch
    local_path = f"/tmp/{MODEL_FILE}"
    _download_model_from_gcs(MODEL_FILE, local_path)
    _model = torch.load(local_path, map_location="cpu", weights_only=False)
    _model.eval()
    print("[gcp-tagger] SpeciesNet model loaded")
    return _model


def run_megadetector(image_path: str) -> list:
    """Run MegaDetector to get cropped animal bounding boxes."""
    try:
        from megadetector.detection import run_detector_batch
        from PIL import Image as PILImage
        import numpy as np

        data = run_detector_batch.load_and_run_detector_batch(
            image_file_names=[image_path],
            model_file="/tmp/mdv5a.pt",
        )
        crops = []
        if not data:
            return crops

        entry      = data[0]
        detections = entry.get("detections", [])
        img        = PILImage.open(image_path).convert("RGB")
        W, H       = img.size

        for det in detections:
            if det.get("category") != "1":
                continue
            if det.get("conf", 0) < 0.05:
                continue
            x, y, w, h = det["bbox"]
            left   = int(x * W)
            top    = int(y * H)
            right  = int((x + w) * W)
            bottom = int((y + h) * H)
            crop   = img.crop((left, top, right, bottom))
            crops.append(crop)

        # Fallback: use full image if no crops
        if not crops:
            crops = [img]
        return crops

    except Exception as e:
        print(f"[gcp-tagger] MegaDetector error: {e}, using full image")
        from PIL import Image as PILImage
        return [PILImage.open(image_path).convert("RGB")]


def classify_image(pil_image) -> str | None:
    """Run SpeciesNet on a PIL image, return top species or None."""
    import torch
    import torchvision.transforms as transforms
    import numpy as np

    model = get_speciesnet_model()
    transform = transforms.Compose([
        transforms.Resize((480, 480)),
        transforms.ToTensor(),
    ])

    with torch.no_grad():
        t      = transform(pil_image).unsqueeze(0).permute(0, 2, 3, 1)
        logits = model(t)
        probs  = torch.softmax(logits, dim=1)[0].cpu().numpy()
        best   = int(np.argmax(probs))
        if probs[best] >= CONF_THRESHOLD:
            return CLASSES[best]
    return None


def process_image_file(image_path: str) -> list:
    """Process a single image: detect + classify."""
    crops = run_megadetector(image_path)
    tags  = set()
    for crop in crops:
        tag = classify_image(crop)
        if tag:
            tags.add(tag)
    return list(tags)


def process_video_file(video_path: str) -> list:
    """Process video: extract 1 frame/sec, detect + classify each frame."""
    import cv2
    from PIL import Image as PILImage
    import numpy as np

    cap            = cv2.VideoCapture(video_path)
    fps            = cap.get(cv2.CAP_PROP_FPS) or 25.0
    frame_interval = max(1, int(fps))
    tags           = set()
    frame_idx      = 0

    with tempfile.TemporaryDirectory() as tmpdir:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if frame_idx % frame_interval == 0:
                frame_path = os.path.join(tmpdir, f"frame_{frame_idx}.jpg")
                cv2.imwrite(frame_path, frame)
                frame_tags = process_image_file(frame_path)
                tags.update(frame_tags)
            frame_idx += 1

    cap.release()
    return list(tags)


@functions_framework.http
def tagger(request):
    """
    HTTP entry point for GCP Cloud Function.
    Body: { "file_url": "https://...", "file_type": "image"|"video",
            "s3_key": "uploads/xxx.jpg", "s3_bucket": "..." }
    Returns: { "tags": ["Sus_scrofa", ...] }
    """
    if request.method == "OPTIONS":
        return ("", 204, {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST",
            "Access-Control-Allow-Headers": "Content-Type",
        })

    try:
        body      = request.get_json(force=True)
        file_url  = body.get("file_url", "")
        file_type = body.get("file_type", "image")

        if not file_url:
            return (json.dumps({"error": "file_url is required"}), 400,
                    {"Content-Type": "application/json"})

        # Download the model weights to /tmp (from GCS) — swappable
        _download_model_from_gcs(MD_FILE, f"/tmp/{MD_FILE}")

        with tempfile.TemporaryDirectory() as tmpdir:
            ext       = os.path.splitext(file_url.split("?")[0])[1].lower() or ".jpg"
            local_path = os.path.join(tmpdir, f"input{ext}")

            # Download file from S3 public URL
            urllib.request.urlretrieve(file_url, local_path)
            print(f"[gcp-tagger] Downloaded {file_url} → {local_path}")

            if file_type == "video" or ext in VIDEO_EXTS:
                tags = process_video_file(local_path)
            else:
                tags = process_image_file(local_path)

        print(f"[gcp-tagger] Detected tags: {tags}")
        return (
            json.dumps({"tags": tags}),
            200,
            {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
        )

    except Exception as e:
        print(f"[gcp-tagger] ERROR: {e}")
        return (
            json.dumps({"tags": [], "error": str(e)}),
            500,
            {"Content-Type": "application/json"},
        )
