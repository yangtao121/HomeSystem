# PaperAnalysis Service Docker Image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=utf-8
ENV LANG=C.UTF-8
ENV TZ=Asia/Shanghai
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    git \
    gcc \
    g++ \
    netcat-openbsd \
    postgresql-client \
    redis-tools \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean 


# Set working directory
WORKDIR /app

# Configure pip to use domestic mirror
RUN mkdir -p /root/.pip && \
    echo "[global]" > /root/.pip/pip.conf && \
    echo "index-url = https://pypi.tuna.tsinghua.edu.cn/simple" >> /root/.pip/pip.conf && \
    echo "trusted-host = pypi.tuna.tsinghua.edu.cn" >> /root/.pip/pip.conf

# Copy requirements first for better caching
COPY Web/PaperAnalysis/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy HomeSystem core modules (dependency) first
COPY HomeSystem /app/HomeSystem

# Copy PaperAnalysis application code
COPY Web/PaperAnalysis /app

# Create directories for logs, uploads, and data
RUN mkdir -p /app/logs /app/uploads /app/static/uploads \
    /app/data/paper_analyze \
    /app/data/paper_gather/task_history \
    /app/data/paper_gather/config_presets \
    /app/data/paper_gather/scheduled_tasks

# Create non-root user for security
RUN useradd -m -u 1000 paperuser && \
    mkdir -p /home/paperuser/.pip && \
    echo "[global]" > /home/paperuser/.pip/pip.conf && \
    echo "index-url = https://pypi.tuna.tsinghua.edu.cn/simple" >> /home/paperuser/.pip/pip.conf && \
    echo "trusted-host = pypi.tuna.tsinghua.edu.cn" >> /home/paperuser/.pip/pip.conf && \
    chown -R paperuser:paperuser /app /home/paperuser/.pip

# Copy and set up entrypoint script
COPY Web/PaperAnalysis/docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Switch to non-root user
USER paperuser

# Expose port (configurable via environment)
EXPOSE 5002

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:5002/api/health || exit 1

# Start the service
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["python", "app.py"]