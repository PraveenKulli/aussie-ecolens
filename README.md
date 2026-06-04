# Aussie EcoLens 🦘
**FIT5225 2026 S1 Assignment 2 — Multi-Cloud Serverless Wildlife Platform**

> A serverless, multi-cloud platform for automated wildlife tagging and media management.
> Users upload images and videos; ML models auto-detect Australian species and store tags for search.

---

## Architecture

```
┌────────────────────────── AWS ─────────────────────────────────────────┐
│                                                                          │
│  Browser → S3 Static Site (Frontend)                                    │
│      ↕ JWT (Cognito)                                                     │
│  Browser → API Gateway HTTP API                                          │
│      ├─ POST /upload/presign  → Lambda(upload)  → DynamoDB (dedup)      │
│      │                         → S3 (pre-signed URL)                    │
│      ├─ POST /upload/confirm  → Lambda(upload)  → DynamoDB              │
│      ├─ S3 ObjectCreated ─────→ Lambda(thumbnail) → S3 (thumbnails)     │
│      │                   └────→ Lambda(tagger) ──────────────────────┐  │
│      ├─ POST /query/tags      → Lambda(queries) → DynamoDB           │  │
│      ├─ POST /query/thumbnail → Lambda(queries) → DynamoDB           │  │
│      ├─ POST /query/file      → Lambda(queries) → [GCP] → DynamoDB   │  │
│      ├─ POST /tags            → Lambda(tags)    → DynamoDB → SNS     │  │
│      ├─ POST /delete          → Lambda(delete)  → S3 + DynamoDB      │  │
│      └─ POST /notifications/* → Lambda(notify)  → SNS                │  │
│                                                                        │  │
│  Cognito (Auth) · S3 (media) · DynamoDB · SNS (email alerts)          │  │
└────────────────────────────────────────────────────────────────────────┘  │
                                                                             │
┌────────────────────────── GCP ─────────────────────────────────────────┐  │
│                                                                          │  │
│  Cloud Function (aussie-ecolens-tagger) ←─────────────────────────────┘  │
│      1. Downloads file from S3 public URL                                 │
│      2. Loads mdv5a.pt from GCS (MegaDetector)                           │
│      3. Loads model.pt from GCS (SpeciesNet fine-tuned)                  │
│      4. Returns detected species tags                                     │
│                                                                            │
│  Cloud Storage (ML model bucket: mdv5a.pt + model.pt)                    │
└────────────────────────────────────────────────────────────────────────────
```

**Multi-cloud design:** AWS handles all user-facing services (auth, storage, API, DB, notifications). GCP handles the compute-intensive ML inference — keeping models in GCS means swapping to a new model version requires only uploading a new file, **zero code changes**.

---

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| AWS CLI | ≥ 2.x | [docs.aws.amazon.com](https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html) |
| Terraform | ≥ 1.6 | [terraform.io](https://terraform.io/downloads) |
| Google Cloud SDK | latest | [cloud.google.com/sdk](https://cloud.google.com/sdk/docs/install) |
| Docker | ≥ 20.x | Required to build Lambda layer |
| Node.js | ≥ 18 | For frontend |
| Python | 3.12 | For local testing |

---

## Quick Start

### 1. Clone & configure credentials

```bash
git clone https://github.com/PraveenKulli/aussie-ecolens
cd aussie-ecolens

# AWS credentials (AWS Academy)
aws configure  # or set AWS_ACCESS_KEY_ID etc.

# GCP credentials
gcloud auth login
gcloud auth application-default login
```

### 2. Upload ML models to project root

Place your model files here before deploying:
```
aussie-ecolens/
├── model.pt     ← SpeciesNet fine-tuned model
└── mdv5a.pt     ← MegaDetector v5a
```

### 3. Deploy everything

```bash
chmod +x scripts/*.sh
./scripts/deploy.sh --gcp-project YOUR_GCP_PROJECT_ID
```

This script:
1. Builds the OpenCV Lambda layer (Docker required)
2. Deploys the GCP Cloud Function
3. Applies Terraform (all AWS resources)
4. Builds and deploys the React frontend to S3

### 4. Open the app

The script prints the frontend URL at the end. Open it, register, and start uploading!

---

## API Reference

All endpoints require `Authorization: Bearer <cognito_id_token>` header.

### Upload

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/upload/presign` | Check dedup + get S3 pre-signed URL |
| POST | `/upload/confirm` | Confirm upload, trigger ML pipeline |

**POST /upload/presign**
```json
// Request
{ "filename": "kangaroo.jpg", "checksum": "<sha256>", "content_type": "image/jpeg" }

// Response (new file)
{ "duplicate": false, "upload_url": "https://...", "file_key": "uploads/uuid.jpg", "file_id": "uuid" }

// Response (duplicate)
{ "duplicate": true, "message": "File already exists", "file_url": "...", "thumbnail_url": "...", "tags": ["..."] }
```

### Queries

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/query/tags` | Find by species + optional min counts (AND logic) |
| POST | `/query/thumbnail` | Get full-size URL from thumbnail URL |
| POST | `/query/file` | Upload file → detect species → find matches |

**POST /query/tags**
```json
// By counts (AND logic):
{ "tags": { "Sus_scrofa": 2, "Felis_catus": 1 } }

// By species only:
{ "species": ["Canis_dingo"] }

// Response
{ "count": 3, "results": [{ "file_url": "...", "thumbnail_url": "...", "tags": ["..."] }] }
```

**POST /query/file**
```json
// Request (base64 encoded file)
{ "file_base64": "<base64>", "content_type": "image/jpeg", "filename": "photo.jpg" }

// Response
{ "detected_tags": ["Sus_scrofa"], "count": 5, "results": [...] }
```

### Tag Management

**POST /tags**
```json
{ "urls": ["https://..."], "tags": ["Sus_scrofa"], "operation": 1 }
// operation: 1 = add, 0 = remove
```

### Delete

**POST /delete**
```json
{ "urls": ["https://...", "https://..."] }
```

### Notifications

**POST /notifications/subscribe**
```json
{ "email": "user@example.com", "tags": ["Sus_scrofa", "Felis_catus"] }
```

**POST /notifications/unsubscribe**
```json
{ "subscription_arn": "arn:aws:sns:..." }
```

---

## Project Structure

```
aussie-ecolens/
├── infrastructure/          # Terraform (AWS + GCP)
│   ├── main.tf              # All AWS + GCP resources
│   ├── variables.tf
│   └── outputs.tf
├── backend/
│   └── lambdas/
│       ├── upload/          # Pre-signed URLs + deduplication
│       ├── thumbnail/       # OpenCV thumbnail + video frames
│       ├── tagger/          # AWS orchestrator + GCP Cloud Function
│       │   └── gcp_function.py  # GCP: MegaDetector + SpeciesNet
│       ├── queries/         # All 4 query types
│       ├── tags/            # Bulk tag add/remove
│       ├── delete/          # File + DB deletion
│       └── notifications/   # SNS subscribe/unsubscribe
├── frontend/
│   └── src/
│       ├── pages/           # Dashboard, Upload, Query, Manage, Notify
│       ├── services/        # auth.js, api.js
│       └── components/      # Layout
├── scripts/
│   ├── deploy.sh            # Master deployment script
│   └── build_layer.sh       # Build OpenCV Lambda layer
└── docs/
    └── architecture.md
```

---

## Supported Species

The model recognises 46 Australian species including:
Australian Brushturkey, Cattle, Dingo, Domestic Cat, Cassowary, Wild Boar,
Long-nosed Bandicoot, Red-legged Pademelon, Musky Rat-Kangaroo,
Orange-footed Scrubfowl, Northern Chowchilla, Grey-headed Robin,
Giant White-tailed Rat, and more.

See `labels.txt` for the full list.

---

## Team

| Name | Student ID | Contribution | % |
|------|-----------|--------------|---|
| Praveen Kulli | [YOUR_ID] | Full-stack: Infrastructure, all Lambda functions, GCP Cloud Function, React frontend, deployment scripts, reports | % |

---

## Acknowledgements

- MegaDetector by Microsoft AI for Earth
- SpeciesNet fine-tuned model provided by the teaching team
- AWS Academy for cloud credits
- GCP for ML inference compute
