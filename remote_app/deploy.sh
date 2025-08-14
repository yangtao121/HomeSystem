#!/bin/bash
# Remote App Services Deployment Script
# This script provides easy deployment options for the OCR service

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
print_header() {
    echo -e "${BLUE}"
    echo "============================================"
    echo "  Remote App Services Deployment"
    echo "============================================"
    echo -e "${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
    exit 1
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

# Check requirements
check_requirements() {
    print_info "Checking requirements..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker first."
    fi
    print_success "Docker found"
    
    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        if ! docker compose version &> /dev/null; then
            print_error "Docker Compose is not installed. Please install Docker Compose first."
        else
            DOCKER_COMPOSE_CMD="docker compose"
        fi
    else
        DOCKER_COMPOSE_CMD="docker-compose"
    fi
    print_success "Docker Compose found"
    
    # Check if Docker daemon is running
    if ! docker info &> /dev/null; then
        print_error "Docker daemon is not running. Please start Docker first."
    fi
    print_success "Docker daemon is running"
}

# Create directory structure
create_directories() {
    print_info "Creating directory structure..."
    
    # Create volume directories
    mkdir -p volumes/{models,hub,results,temp,logs,prometheus,grafana}
    mkdir -p config
    mkdir -p nginx/{conf.d,ssl}
    mkdir -p monitoring/{grafana/dashboards,grafana/datasources}
    
    # Set permissions
    chmod 755 volumes
    chmod 755 volumes/*
    
    print_success "Directory structure created"
}

# Setup configuration
setup_config() {
    print_info "Setting up configuration..."
    
    # Copy environment file
    if [ ! -f .env ]; then
        if [ "$1" = "production" ]; then
            cp .env.production .env
            print_warning "Production environment configured. Please review and update .env file with your settings."
            print_warning "IMPORTANT: Update API_KEY and GRAFANA_PASSWORD in .env file!"
        else
            cp .env.docker .env
            print_success "Development environment configured"
        fi
    else
        print_warning ".env file already exists, skipping configuration copy"
    fi
}

# Create Nginx configuration
create_nginx_config() {
    print_info "Creating Nginx configuration..."
    
    cat > nginx/nginx.conf << 'EOF'
user nginx;
worker_processes auto;
error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events {
    worker_connections 1024;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;
    
    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent" "$http_x_forwarded_for"';
    
    access_log /var/log/nginx/access.log main;
    
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;
    
    # Upstream OCR services
    upstream ocr_backend {
        server ocr-service:5001;
        # Add more servers for load balancing:
        # server ocr-service-2:5001;
        # server ocr-service-3:5001;
    }
    
    include /etc/nginx/conf.d/*.conf;
}
EOF

    cat > nginx/conf.d/default.conf << 'EOF'
server {
    listen 80;
    server_name localhost;
    
    # Client upload limit
    client_max_body_size 200M;
    client_body_timeout 300s;
    
    # Proxy settings
    proxy_connect_timeout 300s;
    proxy_send_timeout 300s;
    proxy_read_timeout 300s;
    
    # OCR service proxy
    location /api/ {
        proxy_pass http://ocr_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # Health check endpoint
    location /health {
        proxy_pass http://ocr_backend/api/health;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
    
    # Default response for non-API requests
    location / {
        return 200 '{"status":"Remote OCR Service","version":"1.0","endpoints":["/api/health","/api/ocr/process"]}';
        add_header Content-Type application/json;
    }
}
EOF
    
    print_success "Nginx configuration created"
}

# Create monitoring configuration
create_monitoring_config() {
    print_info "Creating monitoring configuration..."
    
    # Prometheus configuration
    cat > monitoring/prometheus.yml << 'EOF'
global:
  scrape_interval: 15s
  external_labels:
    monitor: 'remote-app-monitor'

scrape_configs:
  - job_name: 'ocr-service'
    static_configs:
      - targets: ['ocr-service:5001']
    scrape_interval: 30s
    metrics_path: '/metrics'

  - job_name: 'nginx'
    static_configs:
      - targets: ['nginx:80']
    scrape_interval: 30s
EOF
    
    print_success "Monitoring configuration created"
}

# Build and start services
deploy_services() {
    local profile=$1
    local mode=$2
    
    print_info "Building and starting services..."
    
    # Build the image
    print_info "Building OCR service image..."
    $DOCKER_COMPOSE_CMD build ocr-service
    print_success "Image built successfully"
    
    # Start services based on profile
    if [ "$profile" = "full" ]; then
        print_info "Starting all services (OCR + Nginx + Monitoring)..."
        $DOCKER_COMPOSE_CMD --profile proxy --profile monitoring up -d
    elif [ "$profile" = "proxy" ]; then
        print_info "Starting services with proxy (OCR + Nginx)..."
        $DOCKER_COMPOSE_CMD --profile proxy up -d
    elif [ "$profile" = "monitoring" ]; then
        print_info "Starting services with monitoring (OCR + Monitoring)..."
        $DOCKER_COMPOSE_CMD --profile monitoring up -d
    else
        print_info "Starting OCR service only..."
        $DOCKER_COMPOSE_CMD up -d ocr-service
    fi
    
    print_success "Services started successfully"
}

# Check service health
check_health() {
    print_info "Checking service health..."
    
    # Wait for services to start
    sleep 10
    
    # Get OCR service port
    OCR_PORT=$(grep OCR_SERVICE_PORT .env | cut -d'=' -f2 | tr -d ' ' || echo "5001")
    
    # Check OCR service
    if curl -f -s "http://localhost:$OCR_PORT/api/health" > /dev/null; then
        print_success "OCR service is healthy (port $OCR_PORT)"
    else
        print_warning "OCR service health check failed (port $OCR_PORT)"
        print_info "Service may still be starting up, check with: docker-compose logs ocr-service"
    fi
    
    # Check Nginx if proxy profile is used
    if $DOCKER_COMPOSE_CMD ps nginx &> /dev/null && [ "$($DOCKER_COMPOSE_CMD ps nginx | wc -l)" -gt 1 ]; then
        NGINX_PORT=$(grep NGINX_PORT .env | cut -d'=' -f2 | tr -d ' ' || echo "80")
        if curl -f -s "http://localhost:$NGINX_PORT/health" > /dev/null; then
            print_success "Nginx proxy is healthy (port $NGINX_PORT)"
        else
            print_warning "Nginx proxy health check failed (port $NGINX_PORT)"
        fi
    fi
}

# Show service information
show_info() {
    print_info "Deployment completed!"
    echo
    echo "Service Information:"
    echo "==================="
    
    # Get ports from .env
    OCR_PORT=$(grep OCR_SERVICE_PORT .env | cut -d'=' -f2 | tr -d ' ' || echo "5001")
    NGINX_PORT=$(grep NGINX_PORT .env | cut -d'=' -f2 | tr -d ' ' || echo "80")
    GRAFANA_PORT=$(grep GRAFANA_PORT .env | cut -d'=' -f2 | tr -d ' ' || echo "3000")
    PROMETHEUS_PORT=$(grep PROMETHEUS_PORT .env | cut -d'=' -f2 | tr -d ' ' || echo "9090")
    
    echo "• OCR Service: http://localhost:$OCR_PORT"
    echo "  - Health: http://localhost:$OCR_PORT/api/health"
    echo "  - Process: http://localhost:$OCR_PORT/api/ocr/process"
    
    if $DOCKER_COMPOSE_CMD ps nginx &> /dev/null && [ "$($DOCKER_COMPOSE_CMD ps nginx | wc -l)" -gt 1 ]; then
        echo "• Nginx Proxy: http://localhost:$NGINX_PORT"
        echo "  - Health: http://localhost:$NGINX_PORT/health"
    fi
    
    if $DOCKER_COMPOSE_CMD ps grafana &> /dev/null && [ "$($DOCKER_COMPOSE_CMD ps grafana | wc -l)" -gt 1 ]; then
        echo "• Grafana: http://localhost:$GRAFANA_PORT (admin/admin123)"
    fi
    
    if $DOCKER_COMPOSE_CMD ps prometheus &> /dev/null && [ "$($DOCKER_COMPOSE_CMD ps prometheus | wc -l)" -gt 1 ]; then
        echo "• Prometheus: http://localhost:$PROMETHEUS_PORT"
    fi
    
    echo
    echo "Management Commands:"
    echo "===================="
    echo "• View logs: docker-compose logs -f"
    echo "• Stop services: docker-compose down"
    echo "• Restart: docker-compose restart"
    echo "• Update: docker-compose pull && docker-compose up -d"
    echo "• Scale OCR: docker-compose up -d --scale ocr-service=3"
}

# Usage information
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo
    echo "OPTIONS:"
    echo "  -p, --profile PROFILE    Deployment profile (default|proxy|monitoring|full)"
    echo "  -e, --env ENV           Environment (development|production)"
    echo "  -h, --help              Show this help message"
    echo
    echo "PROFILES:"
    echo "  default                 OCR service only"
    echo "  proxy                   OCR service + Nginx reverse proxy"
    echo "  monitoring              OCR service + Prometheus + Grafana"
    echo "  full                    All services"
    echo
    echo "EXAMPLES:"
    echo "  $0                      # Deploy OCR service only (development)"
    echo "  $0 -p proxy             # Deploy with Nginx proxy"
    echo "  $0 -p full -e production # Full deployment for production"
    echo "  $0 -e production        # Production deployment (OCR only)"
}

# Main script
main() {
    local profile="default"
    local env="development"
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -p|--profile)
                profile="$2"
                shift 2
                ;;
            -e|--env)
                env="$2"
                shift 2
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                ;;
        esac
    done
    
    # Validate profile
    if [[ ! "$profile" =~ ^(default|proxy|monitoring|full)$ ]]; then
        print_error "Invalid profile: $profile. Use: default, proxy, monitoring, or full"
    fi
    
    # Validate environment
    if [[ ! "$env" =~ ^(development|production)$ ]]; then
        print_error "Invalid environment: $env. Use: development or production"
    fi
    
    print_header
    print_info "Deployment profile: $profile"
    print_info "Environment: $env"
    echo
    
    # Run deployment steps
    check_requirements
    create_directories
    setup_config "$env"
    create_nginx_config
    create_monitoring_config
    deploy_services "$profile" "$env"
    check_health
    show_info
    
    print_success "Deployment completed successfully!"
    
    if [ "$env" = "production" ]; then
        print_warning "PRODUCTION DEPLOYMENT REMINDERS:"
        print_warning "1. Update API_KEY in .env file"
        print_warning "2. Update GRAFANA_PASSWORD in .env file"
        print_warning "3. Configure SSL certificates if using HTTPS"
        print_warning "4. Review security settings and firewall rules"
    fi
}

# Run main function
main "$@"