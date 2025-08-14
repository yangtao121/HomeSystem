#!/bin/bash

# Remote OCR Service Startup Script

echo "Starting Remote OCR Service..."

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed"
    exit 1
fi

# Set default environment variables if not set
export HOST=${HOST:-"0.0.0.0"}
export OCR_SERVICE_PORT=${OCR_SERVICE_PORT:-"5001"}
export PORT=${PORT:-$OCR_SERVICE_PORT}
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

echo "Configuration:"
echo "  Host: $HOST"
echo "  Port: $OCR_SERVICE_PORT"
echo "  Debug: $DEBUG"
echo "  Max Pages: $OCR_MAX_PAGES"
echo "  Use GPU: $PADDLEOCR_USE_GPU"

# Create directories
mkdir -p "$OCR_TEMP_DIR"
mkdir -p "$OCR_RESULTS_DIR"

# Check if requirements are installed
echo "Checking dependencies..."
python3 -c "import flask; import paddleocr; print('Dependencies OK')" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "Installing dependencies..."
    pip3 install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "Error: Failed to install dependencies"
        exit 1
    fi
fi

# Start the service
echo "Starting OCR service on $HOST:$OCR_SERVICE_PORT..."
python3 app.py