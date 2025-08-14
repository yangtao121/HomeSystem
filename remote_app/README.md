# Remote App Services

This directory contains remote processing services for HomeSystem.

## Structure

- `ocr_service/` - Remote OCR processing using PaddleOCR
- `shared/` - Common utilities shared across all remote services

## OCR Service

The OCR service provides remote PaddleOCR processing capabilities to offload compute-intensive OCR operations from the main HomeSystem.

### Configuration

#### Client Configuration (in HomeSystem)

Set the following environment variables:

```bash
REMOTE_OCR_ENDPOINT=http://your-server:5001
REMOTE_OCR_TIMEOUT=300
```

#### Server Configuration (OCR Service)

The OCR service port can be configured using environment variables:

```bash
# Option 1: Use OCR-specific port (recommended)
OCR_SERVICE_PORT=8080

# Option 2: Use generic port (affects all services)
PORT=8080

# Option 3: Use defaults (port 5001)
# No environment variable needed
```

**Port Priority**: `OCR_SERVICE_PORT` > `PORT` > `5001` (default)

Other configurable options:

```bash
# Service settings
HOST=0.0.0.0                    # Default: 0.0.0.0
DEBUG=False                     # Default: False
LOG_LEVEL=INFO                  # Default: INFO

# OCR settings
OCR_MAX_PAGES=25               # Default: 25
OCR_TEMP_DIR=/tmp/ocr_service  # Default: /tmp/ocr_service
OCR_RESULTS_DIR=/tmp/ocr_results # Default: /tmp/ocr_results

# PaddleOCR settings
PADDLEOCR_USE_ANGLE_CLS=True   # Default: True
PADDLEOCR_USE_GPU=False        # Default: False
PADDLEOCR_LANG=ch              # Default: ch
```

### Quick Start

1. **Copy configuration template:**
   ```bash
   cd ocr_service
   cp .env.example .env
   # Edit .env to customize port and other settings
   ```

2. **Start the service:**
   ```bash
   ./start.sh
   ```

3. **Verify service is running:**
   ```bash
   curl http://localhost:5001/api/health
   ```

### Usage

From HomeSystem ArxivTool:

```python
# Use remote OCR service
ocr_result, status_info = arxiv_tool.performOCR(use_remote_ocr=True)
```