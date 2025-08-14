# Docker Deployment Guide for Remote App Services

This guide provides comprehensive instructions for deploying the Remote App OCR services using Docker.

## 🚀 Quick Start

### Prerequisites

- Docker Engine 20.10+
- Docker Compose v2.0+
- 2GB+ available RAM
- 5GB+ available disk space

### One-Command Deployment

```bash
./deploy.sh
```

That's it! The OCR service will be available at `http://localhost:5001`.

## 📋 Deployment Options

### Basic Deployment (OCR Service Only)

```bash
# Development environment
./deploy.sh

# Production environment
./deploy.sh -e production
```

### Advanced Deployments

```bash
# With Nginx reverse proxy
./deploy.sh -p proxy

# With monitoring (Prometheus + Grafana)
./deploy.sh -p monitoring

# Full deployment (all services)
./deploy.sh -p full -e production
```

## 🔧 Configuration

### Environment Files

1. **Development**: Uses `.env.docker` template
2. **Production**: Uses `.env.production` template

### Key Configuration Options

```env
# Service Configuration
OCR_SERVICE_PORT=5001      # OCR service port
NGINX_PORT=80              # Nginx proxy port
DEBUG=false                # Enable debug mode
LOG_LEVEL=INFO             # Log level

# OCR Settings
OCR_MAX_PAGES=25          # Max pages per PDF
PADDLEOCR_USE_GPU=false   # Enable GPU acceleration
PADDLEOCR_LANG=ch         # OCR language (ch/en)

# Security
API_KEY=                  # Optional API key authentication
```

## 📁 Directory Structure

```
remote_app/
├── docker-compose.yml           # Main compose file
├── .env.docker                  # Development environment
├── .env.production             # Production environment
├── deploy.sh                   # Main deployment script
├── scale.sh                    # Scaling management
├── health-check.sh             # Health monitoring
├── ocr_service/
│   ├── Dockerfile             # OCR service image
│   └── docker-entrypoint.sh   # Container startup script
├── volumes/                    # Persistent data
│   ├── models/                # PaddleOCR models cache
│   ├── results/               # OCR output files
│   └── logs/                  # Application logs
├── nginx/                     # Nginx configuration
└── monitoring/                # Prometheus/Grafana config
```

## 🎛️ Management Commands

### Service Management

```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# Restart services
docker-compose restart

# View logs
docker-compose logs -f ocr-service

# Check status
docker-compose ps
```

### Scaling

```bash
# Scale to 3 instances
./scale.sh up 3

# Scale down to 1 instance
./scale.sh down 1

# Stop all instances
./scale.sh stop

# Check scaling status
./scale.sh status
```

### Health Monitoring

```bash
# Single health check
./health-check.sh

# Verbose health check
./health-check.sh check -v

# Continuous monitoring
./health-check.sh monitor 30
```

## 🔍 Service Endpoints

### OCR Service

- **Health Check**: `GET http://localhost:5001/api/health`
- **Process PDF**: `POST http://localhost:5001/api/ocr/process`
- **Download Results**: `GET http://localhost:5001/api/ocr/download/{job_id}`

### With Nginx Proxy (proxy profile)

- **Health Check**: `GET http://localhost:80/health`
- **OCR API**: `POST http://localhost:80/api/ocr/process`

### With Monitoring (monitoring profile)

- **Grafana**: `http://localhost:3000` (admin/admin123)
- **Prometheus**: `http://localhost:9090`

## 🚢 Production Deployment

### 1. Prepare Production Environment

```bash
# Deploy with production settings
./deploy.sh -p full -e production

# Update configuration
vim .env
```

### 2. Security Configuration

```env
# Set strong API key
API_KEY=your-strong-api-key-here

# Set secure Grafana password
GRAFANA_PASSWORD=your-secure-password

# Enable HTTPS (if using Nginx)
# Place SSL certificates in nginx/ssl/
```

### 3. Resource Optimization

```yaml
# In docker-compose.yml, adjust resource limits:
deploy:
  resources:
    limits:
      memory: 4G      # Increase for production
      cpus: '4.0'     # Increase for production
```

### 4. GPU Support (Optional)

```env
# Enable GPU in .env
PADDLEOCR_USE_GPU=true
```

```yaml
# In docker-compose.yml, add GPU support:
services:
  ocr-service:
    runtime: nvidia
    environment:
      - NVIDIA_VISIBLE_DEVICES=all
```

## 📊 Monitoring and Troubleshooting

### Health Monitoring

```bash
# Check all services health
./health-check.sh check -v

# Monitor continuously
./health-check.sh monitor 60
```

### Log Analysis

```bash
# View OCR service logs
docker-compose logs -f ocr-service

# View all logs
docker-compose logs -f

# Filter error logs
docker-compose logs ocr-service 2>&1 | grep -i error
```

### Performance Monitoring

```bash
# Check resource usage
docker stats

# Check disk usage
docker system df
```

### Common Issues

1. **Service not starting**:
   ```bash
   docker-compose logs ocr-service
   ./health-check.sh check -v
   ```

2. **Out of memory**:
   ```bash
   # Increase memory limits in docker-compose.yml
   # Or reduce OCR_MAX_PAGES
   ```

3. **Port conflicts**:
   ```bash
   # Change ports in .env file
   OCR_SERVICE_PORT=5002
   ```

## 🔄 Updates and Maintenance

### Update Services

```bash
# Pull latest images
docker-compose pull

# Restart with new images
docker-compose up -d
```

### Backup Data

```bash
# Backup models (to avoid re-downloading)
tar -czf models-backup.tar.gz volumes/models/

# Backup results
tar -czf results-backup.tar.gz volumes/results/
```

### Cleanup

```bash
# Remove stopped containers
docker-compose down --remove-orphans

# Clean up Docker system
docker system prune -f

# Clean temporary files
rm -rf volumes/temp/*
```

## 📈 Scaling Strategies

### Horizontal Scaling

```bash
# Scale OCR service instances
./scale.sh up 5

# Use load balancer (Nginx)
./deploy.sh -p proxy
```

### Vertical Scaling

```yaml
# Increase resources per container
deploy:
  resources:
    limits:
      memory: 8G
      cpus: '8.0'
```

## 🛡️ Security Best Practices

1. **Use API Keys**: Set strong API keys in production
2. **Network Security**: Use firewall rules to restrict access
3. **HTTPS**: Configure SSL certificates for public deployments
4. **Updates**: Regularly update Docker images and dependencies
5. **Monitoring**: Enable logging and monitoring in production
6. **Backup**: Implement automated backup strategies

## 🆘 Support

### Getting Help

1. Check logs: `docker-compose logs`
2. Run health check: `./health-check.sh check -v`
3. Check service status: `docker-compose ps`
4. Review configuration: `cat .env`

### Reporting Issues

Include the following information:
- Docker version: `docker --version`
- Compose version: `docker-compose --version`
- Service logs: `docker-compose logs`
- System resources: `docker stats`
- Configuration: `.env` file contents (redact secrets)

## 📄 License

This deployment configuration is part of the HomeSystem Remote App Services.