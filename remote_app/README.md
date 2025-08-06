# Remote App Services

This directory contains remote processing services for HomeSystem.

## Structure

- `ocr_service/` - Remote OCR processing using PaddleOCR
- `shared/` - Common utilities shared across all remote services

## OCR Service

The OCR service provides remote PaddleOCR processing capabilities to offload compute-intensive OCR operations from the main HomeSystem.

### Configuration

Set the following environment variables:

```bash
REMOTE_OCR_ENDPOINT=http://your-server:5000
REMOTE_OCR_TIMEOUT=300
```

### Usage

From HomeSystem ArxivTool:

```python
# Use remote OCR service
ocr_result, status_info = arxiv_tool.performOCR(use_remote_ocr=True)
```