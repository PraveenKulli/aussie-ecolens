# WINDOWS SETUP GUIDE — Aussie EcoLens
# Run all commands in PowerShell (Run as Administrator where noted)

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 1 — Install required tools (one-time)
# ─────────────────────────────────────────────────────────────────────────────

# 1A. Install Chocolatey (Windows package manager) — Run PowerShell as Administrator
Set-ExecutionPolicy Bypass -Scope Process -Force
[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))

# 1B. Install all tools via Chocolatey (Administrator PowerShell)
choco install awscli terraform googlechrome git nodejs docker-desktop -y

# 1C. Install Google Cloud SDK (download installer)
# Go to: https://cloud.google.com/sdk/docs/install-sdk#windows
# Download and run GoogleCloudSDKInstaller.exe

# Verify everything installed
aws --version          # Should show aws-cli/2.x
terraform --version    # Should show Terraform v1.6+
gcloud --version       # Should show Google Cloud SDK
node --version         # Should show v18+
git --version          # Should show git version 2.x
docker --version       # Should show Docker version 24+

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 2 — Set up your project folder
# ─────────────────────────────────────────────────────────────────────────────

# 2A. Unzip the project (in PowerShell, navigate to where you saved aussie-ecolens.zip)
cd C:\Users\YourName\Downloads   # change this to where you saved the zip
Expand-Archive -Path aussie-ecolens.zip -DestinationPath C:\Projects\
cd C:\Projects\aussie-ecolens

# 2B. Copy your ML model files into the project root
#     model.pt and mdv5a.pt should go HERE (same level as README.md)
#     Your folder should look like:
#       C:\Projects\aussie-ecolens\
#           model.pt          <-- copy here
#           mdv5a.pt          <-- copy here
#           README.md
#           infrastructure\
#           backend\
#           frontend\
#           scripts\

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 3 — Connect to AWS (AWS Academy credentials)
# ─────────────────────────────────────────────────────────────────────────────

# 3A. Go to AWS Academy → Start Lab → AWS Details → Show CLI credentials
# 3B. You'll see something like:
#     [default]
#     aws_access_key_id=ASIA...
#     aws_secret_access_key=xxxxxx
#     aws_session_token=xxxxxx (very long)

# 3C. Open: C:\Users\YourName\.aws\credentials  (create if it doesn't exist)
#     Paste the 3 lines exactly as shown in AWS Academy.

# OR run these commands (replace with your actual values):
aws configure set aws_access_key_id ASIA_YOUR_KEY_HERE
aws configure set aws_secret_access_key YOUR_SECRET_HERE
aws configure set aws_session_token YOUR_VERY_LONG_TOKEN_HERE
aws configure set default.region us-east-1

# 3D. Test it works:
aws sts get-caller-identity
# Should print your account ID — if you see an error, recheck the credentials

# NOTE: AWS Academy credentials expire every 4 hours!
# When they expire, just go back to step 3A and repeat 3C.

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 4 — Connect to Google Cloud (GCP)
# ─────────────────────────────────────────────────────────────────────────────

# 4A. Go to console.cloud.google.com → Create new project
#     Project name: aussie-ecolens
#     Copy your Project ID (e.g. aussie-ecolens-123456)

# 4B. Enable billing (required):
#     console.cloud.google.com/billing → Link billing account → Use free trial ($300 credit)

# 4C. Enable required APIs in GCP Console:
#     console.cloud.google.com/apis/library
#     Search and enable each:
#       - Cloud Functions API
#       - Cloud Build API
#       - Cloud Storage API  
#       - Artifact Registry API
#       - Cloud Run API (needed for Gen2 functions)

# 4D. Login from PowerShell:
gcloud auth login
# (opens browser — sign in with your Google account)

gcloud auth application-default login
# (opens browser again — click Allow)

gcloud config set project aussie-ecolens-123456
# Replace with YOUR actual project ID

# Test it works:
gcloud projects list
# Should show your project

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 5 — Push code to GitHub
# ─────────────────────────────────────────────────────────────────────────────

cd C:\Projects\aussie-ecolens

git init
git remote add origin https://github.com/PraveenKulli/aussie-ecolens.git

# NOTE: .gitignore already excludes model.pt and mdv5a.pt (large files)
# so they won't be pushed to GitHub

git add .
git commit -m "feat: complete multi-cloud serverless implementation"
git branch -M main
git push -u origin main

# If asked for GitHub password, use a Personal Access Token (not your password):
# github.com → Settings → Developer settings → Personal access tokens → Generate new token

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 6 — Build the OpenCV Lambda Layer (Docker required)
# ─────────────────────────────────────────────────────────────────────────────

# 6A. Make sure Docker Desktop is running (open it from Start menu)

# 6B. Run the build script (from project root):
cd C:\Projects\aussie-ecolens

# On Windows, run with Docker directly:
docker run --rm -v "${PWD}/backend/layers/ml_layer/python:/out/python" `
  public.ecr.aws/lambda/python:3.12 `
  bash -c "pip install opencv-python-headless Pillow --target /out/python && find /out/python -name '*.pyc' -delete"

# 6C. Create the zip:
mkdir infrastructure\zips -Force
Compress-Archive -Path backend\layers\ml_layer\python -DestinationPath infrastructure\zips\cv2_layer.zip -Force

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 7 — Deploy GCP Cloud Function (ML Tagger)
# ─────────────────────────────────────────────────────────────────────────────

# 7A. Set your project ID variable
$GCP_PROJECT = "aussie-ecolens-123456"   # CHANGE THIS to your actual project ID
$GCP_REGION  = "us-central1"
$GCS_BUCKET  = "aussie-ecolens-models-$GCP_PROJECT"

# 7B. Create GCS bucket and upload models
gsutil mb -p $GCP_PROJECT -l $GCP_REGION "gs://$GCS_BUCKET"
gsutil cp model.pt  "gs://$GCS_BUCKET/model.pt"
gsutil cp mdv5a.pt  "gs://$GCS_BUCKET/mdv5a.pt"
gsutil iam ch allUsers:objectViewer "gs://$GCS_BUCKET"

# 7C. Deploy the Cloud Function (this takes 3-5 minutes)
gcloud functions deploy aussie-ecolens-tagger `
  --project=$GCP_PROJECT `
  --region=$GCP_REGION `
  --runtime=python312 `
  --trigger-http `
  --allow-unauthenticated `
  --memory=2048MB `
  --timeout=300s `
  --entry-point=tagger `
  --source=backend/lambdas/tagger `
  --set-env-vars="MODEL_BUCKET=$GCS_BUCKET" `
  --gen2

# 7D. Get the function URL (save this — you need it for Terraform)
$GCP_FUNCTION_URL = gcloud functions describe aussie-ecolens-tagger `
  --project=$GCP_PROJECT --region=$GCP_REGION --gen2 `
  --format="value(serviceConfig.uri)"
Write-Host "GCP Function URL: $GCP_FUNCTION_URL"

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 8 — Deploy AWS Infrastructure with Terraform
# ─────────────────────────────────────────────────────────────────────────────

cd C:\Projects\aussie-ecolens\infrastructure

terraform init

terraform apply `
  -var="aws_region=us-east-1" `
  -var="gcp_project_id=$GCP_PROJECT" `
  -var="gcp_region=$GCP_REGION" `
  -var="gcp_tagger_function_url=$GCP_FUNCTION_URL" `
  -auto-approve

# Save the outputs:
$API_URL        = terraform output -raw api_gateway_url
$COGNITO_POOL   = terraform output -raw cognito_user_pool_id
$COGNITO_CLIENT = terraform output -raw cognito_client_id
$S3_BUCKET      = terraform output -raw s3_bucket_name

Write-Host "API URL: $API_URL"
Write-Host "Cognito Pool: $COGNITO_POOL"
Write-Host "Cognito Client: $COGNITO_CLIENT"
Write-Host "S3 Bucket: $S3_BUCKET"

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 9 — Build and deploy the React Frontend
# ─────────────────────────────────────────────────────────────────────────────

cd C:\Projects\aussie-ecolens\frontend

# 9A. Create the .env file (IMPORTANT — paste your actual values)
@"
VITE_API_BASE_URL=$API_URL
VITE_COGNITO_USER_POOL_ID=$COGNITO_POOL
VITE_COGNITO_CLIENT_ID=$COGNITO_CLIENT
"@ | Out-File -FilePath .env -Encoding utf8

# 9B. Install and build
npm install
npm run build

# 9C. Deploy to S3
$STATIC_BUCKET = "$S3_BUCKET-frontend"
aws s3 mb "s3://$STATIC_BUCKET" --region us-east-1
aws s3 website "s3://$STATIC_BUCKET" --index-document index.html --error-document index.html

# Set public access policy
$POLICY = '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":"*","Action":"s3:GetObject","Resource":"arn:aws:s3:::' + $STATIC_BUCKET + '/*"}]}'
aws s3api put-bucket-policy --bucket $STATIC_BUCKET --policy $POLICY
aws s3api delete-public-access-block --bucket $STATIC_BUCKET
aws s3 sync dist/ "s3://$STATIC_BUCKET" --delete --acl public-read

$FRONTEND_URL = "http://$STATIC_BUCKET.s3-website-us-east-1.amazonaws.com"
Write-Host ""
Write-Host "=============================================="
Write-Host "DEPLOYMENT COMPLETE!"
Write-Host "Frontend: $FRONTEND_URL"
Write-Host "=============================================="

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 10 — Test the application
# ─────────────────────────────────────────────────────────────────────────────

# Open the frontend URL in your browser and:
# 1. Register a new account (use your student email)
# 2. Check email for verification code
# 3. Enter code → verified!
# 4. Sign in → you see the Dashboard
# 5. Upload → drag Sus_scrofa_1.JPG → upload
# 6. Upload → drag Sus_scrofa_1.JPG again → should say "Duplicate detected"
# 7. Search → By Species → Sus_scrofa → should return the image
# 8. Alerts → subscribe your email for Sus_scrofa
# 9. Upload Sus_scrofa_2.JPG → check email for SNS notification

# ─────────────────────────────────────────────────────────────────────────────
# TROUBLESHOOTING
# ─────────────────────────────────────────────────────────────────────────────

# "ExpiredTokenException" → AWS Academy credentials expired → redo Phase 3
# "PERMISSION_DENIED" in GCP → re-run: gcloud auth application-default login
# Terraform "Error acquiring state lock" → run: terraform force-unlock LOCK_ID
# npm install errors → run: npm cache clean --force then npm install again
# Docker not found → make sure Docker Desktop is running (check system tray)
