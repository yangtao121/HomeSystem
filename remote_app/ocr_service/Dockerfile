# OCR Service Docker Image - Simplified for testing
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=utf-8
ENV LANG=C.UTF-8
ENV TZ=Asia/Shanghai
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies for PaddleOCR 3.1.0
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    libgl1-mesa-dev \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libgcc-s1 \
    libomp-dev \
    libopenblas-dev \
    libgeos-dev \
    # Clean up
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Set working directory
WORKDIR /app

# Configure pip to use domestic mirror as default
RUN mkdir -p /root/.pip && \
    echo "[global]" > /root/.pip/pip.conf && \
    echo "index-url = https://pypi.tuna.tsinghua.edu.cn/simple" >> /root/.pip/pip.conf && \
    echo "trusted-host = pypi.tuna.tsinghua.edu.cn" >> /root/.pip/pip.conf

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
# Install PaddlePaddle GPU 3.1.0 for CUDA 12.6 first
RUN pip install --no-cache-dir --upgrade pip && \
    pip install paddlepaddle-gpu -i https://www.paddlepaddle.org.cn/packages/nightly/cu129/ && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directories for PaddleOCR models and results
RUN mkdir -p /app/.paddleocr /app/.paddlehub /tmp/ocr_service /tmp/ocr_results /app/logs

# Create non-root user for security
RUN useradd -m -u 1000 ocruser && \
    mkdir -p /home/ocruser/.pip && \
    echo "[global]" > /home/ocruser/.pip/pip.conf && \
    echo "index-url = https://pypi.tuna.tsinghua.edu.cn/simple" >> /home/ocruser/.pip/pip.conf && \
    echo "trusted-host = pypi.tuna.tsinghua.edu.cn" >> /home/ocruser/.pip/pip.conf && \
    chown -R ocruser:ocruser /app /tmp/ocr_service /tmp/ocr_results /home/ocruser/.pip
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