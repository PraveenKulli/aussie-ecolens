#!/usr/bin/env bash
# build_layer.sh — builds the OpenCV Lambda layer using Docker
# Produces: infrastructure/zips/cv2_layer.zip
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LAYER_DIR="$ROOT_DIR/backend/layers/ml_layer"
OUT_DIR="$ROOT_DIR/infrastructure/zips"
mkdir -p "$OUT_DIR"

echo "[build_layer] Building OpenCV layer for Python 3.12 on Amazon Linux 2023..."

# Use Docker to build inside the Lambda runtime environment
docker run --rm \
  -v "$LAYER_DIR/python:/out/python" \
  public.ecr.aws/lambda/python:3.12 \
  bash -c "
    pip install opencv-python-headless Pillow --target /out/python
    find /out/python -name '*.pyc' -delete
    find /out/python -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
  "

echo "[build_layer] Zipping layer..."
cd "$LAYER_DIR"
zip -r "$OUT_DIR/cv2_layer.zip" python/ -q
echo "[build_layer] Done: $OUT_DIR/cv2_layer.zip"
