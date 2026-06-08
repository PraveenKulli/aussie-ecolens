# Aussie EcoLens 🦘
**FIT5225 2026 S1 Assignment 2 — Multi-Cloud Serverless Wildlife Platform**

> A fully cloud-hosted, serverless, multi-cloud platform for automated wildlife tagging and media management.
> Users upload images and videos; ML models auto-detect Australian species and store tags for search.

---

## Live Application

**URL:** https://d2hn4bficq8hjc.cloudfront.net

No installation required — the application is fully deployed on AWS CloudFront + S3.

---

## Team

| Name | Student ID | Contribution | % |
|------|-----------|--------------|---|
| Anil Kumar Ramesh | 35090642 | Cognito, S3, DynamoDB, IAM, Architecture diagram | 20% |
| Hemanth Naik Krishna Naik | 35093846 | GCP Cloud Function, MegaDetector, SpeciesNet, OpenCV thumbnails, DynamoDB | 20% |
| Sukanya Gaikwad | 35223478 | Lambda (queries, tags, delete, notifications), API Gateway, SNS | 20% |
| Praveen Kulli | 35532009 | Full-stack: Terraform IaC, all 7 Lambda functions, GCP Cloud Function, React frontend, CloudFront deployment, reports | 40% |


---

## Architecture

```
┌────────────────────────── AWS (us-east-1) ─────────────────────────────────────┐
│                                                                                  │
│  User → CloudFront (d2hn4bficq8hjc.cloudfront.net) → S3 (React SPA)           │
│             HTTPS / CDN                                                          │
│                                                                                  │
│  Browser ─── JWT (Cognito us-east-1_xJaCQ1Jc2) ──► API Gateway                │
│                                                      (pqusvcc000.execute-api)   │
│      ├─ POST /upload/presign  → Lambda(upload)  → DynamoDB (dedup GSI)         │
│      │                        → S3 presigned PUT URL                            │
│      ├─ POST /upload/confirm  → Lambda(upload)  → DynamoDB + async Tagger      │
│      ├─ S3 ObjectCreated ────→ Lambda(thumbnail) → S3 (thumbnails/)            │
│      │   Lambda(tagger) ──────────────────────────────────────────────────────┐ │
│      ├─ POST /query/tags      → Lambda(queries) → DynamoDB                   │ │
│      ├─ POST /query/thumbnail → Lambda(queries) → DynamoDB (thumbnail GSI)   │ │
│      ├─ POST /query/file      → Lambda(queries) → GCP → DynamoDB             │ │
│      ├─ POST /tags            → Lambda(tags)    → DynamoDB                   │ │
│      ├─ POST /delete          → Lambda(delete)  → S3 + DynamoDB              │ │
│      └─ POST /notifications/* → Lambda(notify)  → SNS (FilterPolicy)         │ │
│                                                                                │ │
│  Cognito · S3 (media + frontend) · CloudFront · DynamoDB · SNS · IAM (x7)    │ │
└────────────────────────────────────────────────────────────────────────────────┘ │
                                                                                    │
┌────────────────────────── GCP (us-central1) ───────────────────────────────────┐ │
│                                                                                  │ │
│  Cloud Function Gen2 (aussie-ecolens-tagger) ◄──────────────────────────────── ┘ │
│      1. Receives presigned S3 URL (no AWS credentials on GCP)                    │
│      2. Downloads file from S3                                                    │
│      3. Runs MegaDetector v5a (mdv5a.pt) — animal detection                     │
│      4. Runs SpeciesNet (model.pt) — species classification                      │
│      5. Returns detected species tags as JSON                                    │
│                                                                                   │
│  Cloud Storage (aussie-ecolens-models-498402): mdv5a.pt + model.pt              │
│  Model swap = upload new file to GCS only, zero code redeployment               │
└───────────────────────────────────────────────────────────────────────────────────
```

**Multi-cloud design:** AWS handles all user-facing services (auth, storage, API, DB, notifications, CDN). GCP handles compute-intensive ML inference. Models in GCS = swap model with zero code changes.

---

## AWS Resources

| Resource | ID / Name |
|----------|-----------|
| Cognito User Pool | us-east-1_xJaCQ1Jc2 |
| Cognito Client | 6431c0ji6u58381oou60annbf7 |
| S3 Media Bucket | aussie-ecolens-media-1330499f |
| S3 Frontend Bucket | aussie-ecolens-frontend-pkul0010 |
| CloudFront Distribution | E3ALYSL0F0IL48 |
| API Gateway | pqusvcc000.execute-api.us-east-1.amazonaws.com/prod |
| DynamoDB Table | aussie-ecolens-files |
| SNS Topic | arn:aws:sns:us-east-1:625693792944:aussie-ecolens-tag-notifications |
| Region | us-east-1 |

## GCP Resources

| Resource | ID / Name |
|----------|-----------|
| Project | aussie-ecolens-498402 |
| Cloud Function | aussie-ecolens-tagger (us-central1) |
| Cloud Storage Bucket | aussie-ecolens-models-498402 |
| Region | us-central1 |

---

## API Reference

All endpoints require `Authorization: Bearer <cognito_id_token>` header.

### Upload

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/upload/presign` | SHA-256 dedup check + get S3 presigned PUT URL |
| POST | `/upload/confirm` | Confirm upload, trigger ML pipeline |

**POST /upload/presign**
```json
// Request
{ "filename": "kangaroo.jpg", "checksum": "<sha256>", "content_type": "image/jpeg" }

// Response (new file)
{ "duplicate": false, "upload_url": "https://...", "file_key": "uploads/uuid.jpg", "file_id": "uuid" }

// Response (duplicate)
{ "duplicate": true, "file_url": "https://...", "thumbnail_url": "https://...", "tags": ["Sus_scrofa"] }
```

### Queries

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/query/tags` | Find by species + minimum counts (AND logic) |
| POST | `/query/thumbnail` | Get full-size file URL from thumbnail URL |
| POST | `/query/file` | Upload file → detect species → return matching library files |

**POST /query/tags**
```json
// By tag counts (AND logic — all conditions must match):
{ "tags": { "Sus_scrofa": 2, "Felis_catus": 1 } }

// By species name only:
{ "species": ["Canis_familiaris"] }

// Response
{ "count": 3, "results": [{ "file_url": "...", "thumbnail_url": "...", "tags": ["..."] }] }
```

**POST /query/file**
```json
// Request (base64 encoded — video files use extracted frame)
{ "file_base64": "<base64>", "content_type": "image/jpeg", "filename": "photo.jpg" }

// Response
{ "detected_tags": ["Sus_scrofa"], "count": 5, "results": [...] }
```

### Tag Management

**POST /tags**
```json
// operation: 1 = add tags, 0 = remove tags
{ "urls": ["https://..."], "tags": ["Sus_scrofa"], "operation": 1 }
```

### Delete

**POST /delete**
```json
// Permanently deletes S3 file, thumbnails, and DynamoDB record
{ "urls": ["https://...", "https://..."] }
```

### Notifications

**POST /notifications/subscribe**
```json
// SNS subscription with FilterPolicy for species-specific alerts
{ "email": "user@example.com", "tags": ["Sus_scrofa", "Felis_catus"] }
```

**POST /notifications/unsubscribe**
```json
{ "subscription_arn": "arn:aws:sns:us-east-1:625693792944:aussie-ecolens-tag-notifications:..." }
```

---

## Project Structure

```
aussie-ecolens/
├── infrastructure/
│   ├── main.tf              # All AWS resources (Terraform IaC)
│   ├── variables.tf
│   └── outputs.tf
├── backend/
│   └── lambdas/
│       ├── upload/          # Presigned URLs + SHA-256 deduplication
│       ├── thumbnail/       # OpenCV image resize + video frame extraction (1fps)
│       ├── tagger/          # AWS→GCP orchestration + DynamoDB + SNS publish
│       │   └── gcp_function.py  # GCP: MegaDetector + SpeciesNet inference
│       ├── queries/         # Tags (AND+count), thumbnail, file query
│       ├── tags/            # Bulk tag add/remove (operation 1/0)
│       ├── delete/          # S3 + thumbnail + DynamoDB deletion
│       └── notifications/   # SNS subscribe/unsubscribe with FilterPolicy
├── frontend/
│   └── src/
│       ├── pages/           # Dashboard, Upload, Query, Manage, Notify
│       ├── services/        # api.js (all API calls + JWT auth)
│       └── components/      # Layout, navigation
├── docs/
│   └── architecture.xml     # draw.io architecture diagram
└── README.md
```

---

## Key Technical Features

- **SHA-256 deduplication:** Computed client-side (chunked for large videos). Checked against DynamoDB GSI before any S3 upload.
- **Fine-grained IAM:** Seven separate Lambda execution roles — each scoped to minimum required permissions. No shared roles.
- **Cross-cloud auth:** GCP accesses private S3 files via presigned URLs — no AWS credentials on GCP.
- **Model flexibility:** ML models stored in GCP Cloud Storage. Update model = upload new file to GCS only, zero Lambda/function redeployment.
- **Video support:** Thumbnail Lambda extracts frames at 1fps using OpenCV. Query-by-file extracts a single frame client-side before sending to API.
- **SNS FilterPolicy:** Each subscription filters by species. Users only receive emails for their watched species.
- **CloudFront HTTPS:** React SPA served globally via CDN. No local server required.
- **Terraform IaC:** All AWS infrastructure defined as code. Reproducible, version-controlled deployments.

---

## Supported Species (46 total)

Australian Brushturkey, Cattle, Dingo, Domestic Cat, Cassowary, Wild Boar,
Long-nosed Bandicoot, Red-legged Pademelon, Musky Rat-Kangaroo,
Orange-footed Scrubfowl, Northern Chowchilla, Grey-headed Robin,
Giant White-tailed Rat, and more.

See `labels.txt` for the full list.

---

## Acknowledgements

- MegaDetector by Microsoft AI for Earth
- SpeciesNet fine-tuned model provided by the FIT5225 teaching team
- AWS Academy for cloud credits
- GCP Free Tier for ML inference compute
