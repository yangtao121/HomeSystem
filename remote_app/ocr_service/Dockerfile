# OCR Service Docker Image
# This dockerfile creates a complete environment for PaddleOCR processing

FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=utf-8
ENV LANG=C.UTF-8
ENV TZ=Asia/Shanghai
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies required for PaddleOCR and OpenCV
RUN apt-get update && apt-get install -y \
    # OpenCV and image processing dependencies
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libgeos-dev \
    # Font support for Chinese text
    fonts-dejavu-core \
    fontconfig \
    # Network and utility tools
    wget \
    curl \
    git \
    # Build tools (for some Python packages)
    build-essential \
    # Clean up
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy shared utilities
COPY ../shared ../shared

# Copy application code
COPY . .

# Create directories for PaddleOCR models and results
RUN mkdir -p /app/.paddleocr /app/.paddlehub /tmp/ocr_service /tmp/ocr_results /app/logs

# Pre-download PaddleOCR models (optional, can be done at runtime)
# Uncomment the following lines to pre-download models in the image
# RUN python -c "
# import os
# os.environ['PADDLEOCR_HOME'] = '/app/.paddleocr'
# from paddleocr import PaddleOCR
# # Download Chinese + English models
# PaddleOCR(use_angle_cls=True, lang='ch')
# print('PaddleOCR models downloaded successfully')
# " || echo "Model download failed, will download at runtime"

# Create non-root user for security
RUN useradd -m -u 1000 ocruser && \
    chown -R ocruser:ocruser /app /tmp/ocr_service /tmp/ocr_results
USER ocruser

# Set PaddleOCR environment variables
ENV PADDLEOCR_HOME=/app/.paddleocr
ENV HUB_HOME=/app/.paddlehub

# Expose port (configurable via environment)
EXPOSE 5001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:5001/api/health || exit 1

# Create entrypoint script
COPY docker-entrypoint.sh /usr/local/bin/
USER root
RUN chmod +x /usr/local/bin/docker-entrypoint.sh
USER ocruser

# Start the service
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["python", "app.py"]