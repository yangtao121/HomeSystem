#!/bin/bash
# Docker entrypoint script for OCR service

set -e

# Print startup information
echo "============================================"
echo "Starting Remote OCR Service"
echo "============================================"

# Set default environment variables
export HOST=${HOST:-"0.0.0.0"}
export OCR_SERVICE_PORT=${OCR_SERVICE_PORT:-"5001"}
export DEBUG=${DEBUG:-"False"}
export LOG_LEVEL=${LOG_LEVEL:-"INFO"}

# OCR specific settings
export OCR_MAX_PAGES=${OCR_MAX_PAGES:-"25"}
export OCR_TEMP_DIR=${OCR_TEMP_DIR:-"/tmp/ocr_service"}
export OCR_RESULTS_DIR=${OCR_RESULTS_DIR:-"/tmp/ocr_results"}

# PaddleOCR settings
export PADDLEOCR_USE_ANGLE_CLS=${PADDLEOCR_USE_ANGLE_CLS:-"True"}
export PADDLEOCR_USE_GPU=${PADDLEOCR_USE_GPU:-"False"}
export PADDLEOCR_LANG=${PADDLEOCR_LANG:-"ch"}

# Set PaddleOCR home directory
export PADDLEOCR_HOME=${PADDLEOCR_HOME:-"/app/.paddleocr"}
export HUB_HOME=${HUB_HOME:-"/app/.paddlehub"}

# Create necessary directories
mkdir -p "$OCR_TEMP_DIR" "$OCR_RESULTS_DIR" "$PADDLEOCR_HOME" "$HUB_HOME"

# Print configuration
echo "Configuration:"
echo "  Host: $HOST"
echo "  Port: $OCR_SERVICE_PORT"
echo "  Debug: $DEBUG"
echo "  Log Level: $LOG_LEVEL"
echo "  Max Pages: $OCR_MAX_PAGES"
echo "  Use GPU: $PADDLEOCR_USE_GPU"
echo "  Language: $PADDLEOCR_LANG"
echo "  PaddleOCR Home: $PADDLEOCR_HOME"
echo "  Temp Dir: $OCR_TEMP_DIR"
echo "  Results Dir: $OCR_RESULTS_DIR"
echo "============================================"

# Check if PaddleOCR models exist, if not download them
if [ ! -d "$PADDLEOCR_HOME" ] || [ -z "$(ls -A $PADDLEOCR_HOME 2>/dev/null)" ]; then
    echo "PaddleOCR models not found, downloading..."
    python -c "
import os
os.environ['PADDLEOCR_HOME'] = '$PADDLEOCR_HOME'
try:
    from paddleocr import PaddleOCR
    ocr = PaddleOCR(use_angle_cls=True, lang='$PADDLEOCR_LANG')
    print('PaddleOCR models downloaded successfully')
except Exception as e:
    print(f'Failed to download models: {e}')
    exit(1)
"
    echo "Model download completed!"
else
    echo "PaddleOCR models already exist, skipping download"
fi

# Check Python dependencies
echo "Checking Python dependencies..."
python -c "
try:
    import flask
    import paddleocr
    from paddleocr import PaddleOCR
    import cv2
    import numpy as np
    import fitz
    print('All dependencies OK')
except ImportError as e:
    print(f'Missing dependency: {e}')
    exit(1)
" || { echo "Dependency check failed"; exit 1; }

# Wait for any external dependencies if needed
# (add health checks for databases, APIs, etc. if required)

# Start the application
echo "Starting OCR service..."
exec "$@"