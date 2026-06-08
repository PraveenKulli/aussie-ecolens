import boto3
import json
import os
import io
import hashlib
import torch
import torchvision.transforms as transforms
from PIL import Image
import numpy as np
from megadetector.detection import run_detector_batch

s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
table = dynamodb.Table('AussieEcoLens')

BUCKET = 'aussie-ecolens-hkri0008'
MODEL_KEY = 'models/model.pt'
MD_MODEL_KEY = 'models/mdv5a.pt'
SNIP_SIZE = 600
LOWER_CONF = 0.05

CLASSES = [
    'Alectura_lathami', 'Antechinus_agilis', 'Bos_taurus', 'Burhinus_grallarius',
    'Canis_familiaris', 'Chalcophaps_longirostris', 'Colluricincla_harmonica',
    'Corcorax_melanorhamphos', 'Dacelo_novaeguineae', 'Dama_dama',
    'Eopsaltria_australis', 'Felis_catus', 'Geopelia_humeralis', 'Gymnorhina_tibicen',
    'Homo_sapiens', 'Isoodon_macrourus', 'Lepus_europaeus', 'Macropus_giganteus',
    'Menura_novaehollandiae', 'Mus_musculus', 'Oryctolagus_cuniculus',
    'Perameles_nasuta', 'Pitta_versicolor', 'Rattus', 'Rattus_fuscipes',
    'Rattus_rattus', 'Strepera_graculina', 'Sus_scrofa', 'Tachyglossus_aculeatus',
    'Thylogale_stigmatica', 'Trichosurus_caninus', 'Trichosurus_cunninghami',
    'Trichosurus_vulpecula', 'Varanus_varius', 'Vombatus_ursinus', 'Vulpes_vulpes',
    'Wallabia_bicolor', 'Canis_dingo', 'Capra_hircus', 'Casuarius_casuarius',
    'Heteromyias_cinereifrons', 'Hypsiprymnodon_moschatus', 'Megapodius_reinwardt',
    'Notamacropus_rufogriseus', 'Orthonyx_spaldingii', 'Uromys_caudimaculatus'
]

if torch.cuda.is_available():
    DEVICE = 'cuda'
elif torch.backends.mps.is_available():
    DEVICE = 'mps'
else:
    DEVICE = 'cpu'

transform = transforms.Compose([
    transforms.Resize((480, 480)),
    transforms.ToTensor(),
])

def download_model_from_s3(s3_key, local_path):
    if not os.path.exists(local_path):
        print(f"Downloading {s3_key} from S3...")
        s3.download_file(BUCKET, s3_key, local_path)
        print(f"Downloaded to {local_path}")
    else:
        print(f"Model already exists at {local_path}")

def run_megadetector(image_path, md_model_path):
    data = run_detector_batch.load_and_run_detector_batch(
        image_file_names=[image_path],
        model_file=md_model_path
    )
    return data[0] if data else None

def crop_detections(image_path, detections):
    crops = []
    img = Image.open(image_path).convert('RGB')
    W, H = img.size

    for det in detections:
        if det.get('category') != '1':
            continue
        if det.get('conf', 0) < LOWER_CONF:
            continue

        x, y, w, h = det['bbox']
        left = int(x * W)
        top = int(y * H)
        right = int((x + w) * W)
        bottom = int((y + h) * H)

        crop = img.crop((left, top, right, bottom))
        resized = crop.resize((SNIP_SIZE, SNIP_SIZE), Image.BILINEAR)
        crops.append(resized)

    return crops

@torch.no_grad()
def classify_crop(crop_img, species_model):
    img = transform(crop_img)
    img = img.unsqueeze(0)
    img = img.permute(0, 2, 3, 1)
    img = img.to(DEVICE)

    logits = species_model(img)
    probs = torch.softmax(logits, dim=1)[0].cpu().numpy()

    order = np.argsort(probs)[::-1]
    best_idx = order[0]
    best_label = CLASSES[best_idx]
    best_conf = float(probs[best_idx])

    return best_label, best_conf

def get_thumbnail_url(original_key):
    filename = os.path.basename(original_key)
    thumb_key = f"thumbnails/thumb_{filename}"
    if not thumb_key.lower().endswith(('.jpg', '.jpeg')):
        thumb_key = thumb_key.rsplit('.', 1)[0] + '.jpg'
    return f"https://{BUCKET}.s3.amazonaws.com/{thumb_key}"

def lambda_handler(event, context):
    try:
        record = event['Records'][0]['s3']
        bucket = record['bucket']['name']
        key = record['object']['key']

        print(f"ML Detection triggered for: {key}")

        if not key.startswith('originals/ml/'):
            print(f"Skipping {key} - not in originals/")
            return {'statusCode': 200, 'body': 'Skipped'}

        lower_key = key.lower()
        if not any(lower_key.endswith(ext) for ext in ['.jpg', '.jpeg', '.png']):
            print(f"Skipping {key} - not a supported image")
            return {'statusCode': 200, 'body': 'Skipped'}

        # Download image to /tmp
        filename = os.path.basename(key)
        local_image_path = f'/tmp/{filename}'
        s3.download_file(bucket, key, local_image_path)
        print(f"Downloaded image to {local_image_path}")

        # Download models to /tmp
        md_model_path = '/tmp/mdv5a.pt'
        species_model_path = '/tmp/model.pt'
        download_model_from_s3(MD_MODEL_KEY, md_model_path)
        download_model_from_s3(MODEL_KEY, species_model_path)

        # Load SpeciesNet model
        print("Loading SpeciesNet model...")
        species_model = torch.load(species_model_path, map_location=DEVICE, weights_only=False)
        species_model.eval()
        species_model.to(DEVICE)

        # Run MegaDetector
        print("Running MegaDetector...")
        md_result = run_megadetector(local_image_path, md_model_path)

        tags = {}

        if md_result and md_result.get('detections'):
            crops = crop_detections(local_image_path, md_result['detections'])
            print(f"Found {len(crops)} animal detections")

            for crop in crops:
                label, conf = classify_crop(crop, species_model)
                print(f"Classified as: {label} ({conf:.4f})")
                if conf > 0.1:
                    tags[label] = tags.get(label, 0) + 1
        else:
            print("No animal detections found by MegaDetector")

        # Build URLs
        original_url = f"https://{BUCKET}.s3.amazonaws.com/{key}"
        thumbnail_url = get_thumbnail_url(key)
        file_id = hashlib.md5(key.encode()).hexdigest()

        # Save to DynamoDB
        item = {
            'file_id': file_id,
            'file_key': key,
            'file_type': 'image',
            'original_url': original_url,
            'thumbnail_url': thumbnail_url,
            'tags': tags,
            'filename': filename
        }

        table.put_item(Item=item)
        print(f"Saved to DynamoDB: {item}")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'ML detection complete',
                'file_id': file_id,
                'tags': tags,
                'original_url': original_url,
                'thumbnail_url': thumbnail_url
            })
        }

    except Exception as e:
        print(f"ERROR: {str(e)}")
        raise e