#!/usr/bin/env bash
# deploy.sh — Full deployment script for Aussie EcoLens
# Usage: ./scripts/deploy.sh --gcp-project YOUR_GCP_PROJECT_ID
set -euo pipefail

# ── Colour helpers ──────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ── Parse args ───────────────────────────────────────────────────────────────
GCP_PROJECT=""
AWS_REGION="${AWS_REGION:-us-east-1}"
GCP_REGION="${GCP_REGION:-us-central1}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --gcp-project) GCP_PROJECT="$2"; shift 2 ;;
    --aws-region)  AWS_REGION="$2";  shift 2 ;;
    --gcp-region)  GCP_REGION="$2";  shift 2 ;;
    *) error "Unknown argument: $1" ;;
  esac
done

[[ -z "$GCP_PROJECT" ]] && error "Pass --gcp-project YOUR_GCP_PROJECT_ID"

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
INFRA_DIR="$ROOT_DIR/infrastructure"

info "Deploying Aussie EcoLens"
info "  AWS region:  $AWS_REGION"
info "  GCP project: $GCP_PROJECT"
info "  GCP region:  $GCP_REGION"

# ─────────────────────────────────────────────────────────────────────────────
# STEP 1: Build OpenCV Lambda layer
# ─────────────────────────────────────────────────────────────────────────────
info "Step 1/6: Building OpenCV Lambda layer..."
bash "$ROOT_DIR/scripts/build_layer.sh"

# ─────────────────────────────────────────────────────────────────────────────
# STEP 2: Deploy GCP Cloud Function (ML tagger) first so Terraform gets its URL
# ─────────────────────────────────────────────────────────────────────────────
info "Step 2/6: Deploying GCP Cloud Function..."

GCS_MODEL_BUCKET="aussie-ecolens-models-${GCP_PROJECT}"

# Create GCS bucket if it doesn't exist
gsutil mb -p "$GCP_PROJECT" -l "$GCP_REGION" "gs://${GCS_MODEL_BUCKET}" 2>/dev/null || true

# Upload ML models to GCS
info "  Uploading ML models to GCS (you need mdv5a.pt and model.pt locally)..."
[[ -f "$ROOT_DIR/model.pt"  ]] && gsutil cp "$ROOT_DIR/model.pt"  "gs://${GCS_MODEL_BUCKET}/model.pt"
[[ -f "$ROOT_DIR/mdv5a.pt"  ]] && gsutil cp "$ROOT_DIR/mdv5a.pt"  "gs://${GCS_MODEL_BUCKET}/mdv5a.pt"
# Make public
gsutil iam ch allUsers:objectViewer "gs://${GCS_MODEL_BUCKET}" || true

# Deploy Cloud Function
GCP_FUNC_DIR="$ROOT_DIR/backend/lambdas/tagger"
gcloud functions deploy aussie-ecolens-tagger \
  --project="$GCP_PROJECT" \
  --region="$GCP_REGION" \
  --runtime=python312 \
  --trigger-http \
  --allow-unauthenticated \
  --memory=2048MB \
  --timeout=300s \
  --entry-point=tagger \
  --source="$GCP_FUNC_DIR" \
  --set-env-vars="MODEL_BUCKET=${GCS_MODEL_BUCKET}" \
  --gen2

GCP_FUNCTION_URL=$(gcloud functions describe aussie-ecolens-tagger \
  --project="$GCP_PROJECT" --region="$GCP_REGION" --gen2 \
  --format="value(serviceConfig.uri)")

info "GCP function deployed at: $GCP_FUNCTION_URL"

# ─────────────────────────────────────────────────────────────────────────────
# STEP 3: Terraform apply (AWS infrastructure)
# ─────────────────────────────────────────────────────────────────────────────
info "Step 3/6: Deploying AWS infrastructure with Terraform..."
mkdir -p "$INFRA_DIR/zips"
cd "$INFRA_DIR"

terraform init -reconfigure
terraform apply -auto-approve \
  -var="aws_region=$AWS_REGION" \
  -var="gcp_project_id=$GCP_PROJECT" \
  -var="gcp_region=$GCP_REGION" \
  -var="gcp_tagger_function_url=$GCP_FUNCTION_URL"

# ─────────────────────────────────────────────────────────────────────────────
# STEP 4: Read Terraform outputs
# ─────────────────────────────────────────────────────────────────────────────
info "Step 4/6: Reading Terraform outputs..."
API_URL=$(terraform output -raw api_gateway_url)
COGNITO_POOL=$(terraform output -raw cognito_user_pool_id)
COGNITO_CLIENT=$(terraform output -raw cognito_client_id)
S3_BUCKET=$(terraform output -raw s3_bucket_name)

info "  API Gateway: $API_URL"
info "  Cognito Pool: $COGNITO_POOL"
info "  S3 Bucket: $S3_BUCKET"

# ─────────────────────────────────────────────────────────────────────────────
# STEP 5: Build & deploy frontend
# ─────────────────────────────────────────────────────────────────────────────
info "Step 5/6: Building React frontend..."
cd "$ROOT_DIR/frontend"

# Write .env file
cat > .env <<EOF
VITE_API_BASE_URL=$API_URL
VITE_COGNITO_USER_POOL_ID=$COGNITO_POOL
VITE_COGNITO_CLIENT_ID=$COGNITO_CLIENT
EOF

npm install --silent
npm run build

info "Step 5/6: Deploying frontend to S3..."
# Create/use a separate static hosting bucket
STATIC_BUCKET="${S3_BUCKET}-frontend"
aws s3 mb "s3://${STATIC_BUCKET}" --region "$AWS_REGION" 2>/dev/null || true
aws s3 website "s3://${STATIC_BUCKET}" --index-document index.html --error-document index.html
aws s3 sync dist/ "s3://${STATIC_BUCKET}" --delete --acl public-read

FRONTEND_URL="http://${STATIC_BUCKET}.s3-website-${AWS_REGION}.amazonaws.com"

# ─────────────────────────────────────────────────────────────────────────────
# STEP 6: Print summary
# ─────────────────────────────────────────────────────────────────────────────
info "Step 6/6: Deployment complete!"
echo ""
echo -e "${GREEN}════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Aussie EcoLens deployed successfully!${NC}"
echo -e "${GREEN}════════════════════════════════════════════${NC}"
echo ""
echo -e "  🌐 Frontend:     ${FRONTEND_URL}"
echo -e "  🔌 API Gateway:  ${API_URL}"
echo -e "  🗄️  S3 Bucket:    ${S3_BUCKET}"
echo -e "  🔐 Cognito Pool: ${COGNITO_POOL}"
echo -e "  ⚡ GCP Function: ${GCP_FUNCTION_URL}"
echo ""
echo -e "  Next steps:"
echo -e "  1. Open ${FRONTEND_URL} in your browser"
echo -e "  2. Register a new account"
echo -e "  3. Upload one of the sample images from /test_images/"
echo ""
