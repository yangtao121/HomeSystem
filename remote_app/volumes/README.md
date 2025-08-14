# Volumes Directory

This directory contains persistent data for the Remote App services.

## Directory Structure

- **models/**: PaddleOCR model cache
  - Contains downloaded OCR models to avoid re-downloading
  - Mapped to `/app/.paddleocr` in the container

- **hub/**: PaddleHub cache
  - Contains PaddleHub model cache
  - Mapped to `/app/.paddlehub` in the container

- **results/**: OCR processing results
  - Stores processed OCR output files
  - Mapped to `/tmp/ocr_results` in the container

- **temp/**: Temporary files
  - Temporary storage for file processing
  - Mapped to `/tmp/ocr_service` in the container

- **logs/**: Application logs
  - Contains service log files
  - Mapped to `/app/logs` in the container

- **prometheus/**: Prometheus data (when monitoring is enabled)
  - Time series database storage
  - Mapped to `/prometheus` in the Prometheus container

- **grafana/**: Grafana data (when monitoring is enabled)
  - Dashboard and configuration storage
  - Mapped to `/var/lib/grafana` in the Grafana container

## Backup Recommendations

1. **models/**: Backup recommended to avoid re-downloading
2. **results/**: Backup if you need to preserve OCR results
3. **prometheus/**: Backup if you want to preserve metrics history
4. **grafana/**: Backup to preserve custom dashboards
5. **logs/**: Optional backup for audit purposes
6. **temp/**: No backup needed (temporary files)

## Cleanup

- **temp/**: Can be safely cleared when services are not running
- **logs/**: Can be rotated/cleared as needed
- **results/**: Clear based on your retention policy