#!/bin/bash
# Remote App Services Health Check Script
# This script monitors the health of OCR services

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

# Check if Docker Compose is available
check_docker_compose() {
    if command -v docker-compose &> /dev/null; then
        echo "docker-compose"
    elif docker compose version &> /dev/null 2>&1; then
        echo "docker compose"
    else
        print_error "Docker Compose is not installed"
        exit 1
    fi
}

# Check service health via HTTP
check_http_health() {
    local url=$1
    local service_name=$2
    local timeout=${3:-10}
    
    if curl -f -s --max-time "$timeout" "$url" > /dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Get service health response
get_health_response() {
    local url=$1
    local timeout=${2:-10}
    
    curl -f -s --max-time "$timeout" "$url" 2>/dev/null || echo "{\"error\":\"unreachable\"}"
}

# Check container health
check_container_health() {
    local container_name=$1
    local health_status
    
    health_status=$(docker inspect --format='{{.State.Health.Status}}' "$container_name" 2>/dev/null || echo "unknown")
    
    case $health_status in
        "healthy")
            return 0
            ;;
        "unhealthy")
            return 1
            ;;
        "starting")
            return 2
            ;;
        *)
            return 3
            ;;
    esac
}

# Main health check
perform_health_check() {
    local compose_cmd=$1
    local verbose=${2:-false}
    local overall_status=0
    
    print_info "Performing health check..."
    echo
    
    # Check if services are running
    if ! $compose_cmd ps | grep -q ocr-service; then
        print_error "No OCR services are running"
        return 1
    fi
    
    # Get OCR service port from environment
    local ocr_port=5001
    if [ -f .env ]; then
        ocr_port=$(grep -E '^OCR_SERVICE_PORT=' .env | cut -d'=' -f2 | tr -d ' ' || echo "5001")
    fi
    
    # Check external access
    print_info "Checking external access on port $ocr_port..."
    if check_http_health "http://localhost:$ocr_port/api/health" "OCR Service (external)"; then
        print_success "OCR service is accessible externally on port $ocr_port"
        if [ "$verbose" = true ]; then
            local response
            response=$(get_health_response "http://localhost:$ocr_port/api/health")
            echo "    Response: $response"
        fi
    else
        print_error "OCR service is NOT accessible externally on port $ocr_port"
        overall_status=1
    fi
    
    echo
    
    # Check individual containers
    print_info "Checking individual containers..."
    
    local container_ids
    container_ids=$($compose_cmd ps -q ocr-service 2>/dev/null || echo "")
    
    if [ -z "$container_ids" ]; then
        print_error "No OCR service containers found"
        return 1
    fi
    
    local healthy_count=0
    local total_count=0
    
    for container_id in $container_ids; do
        ((total_count++))
        
        local container_name
        container_name=$(docker inspect --format='{{.Name}}' "$container_id" 2>/dev/null | sed 's/^\/*//')
        
        local container_ip
        container_ip=$(docker inspect --format='{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$container_id" 2>/dev/null)
        
        # Check container Docker health status
        local docker_health_code
        check_container_health "$container_id"
        docker_health_code=$?
        
        case $docker_health_code in
            0)
                local docker_health_status="healthy"
                ;;
            1)
                local docker_health_status="unhealthy"
                ;;
            2)
                local docker_health_status="starting"
                ;;
            *)
                local docker_health_status="unknown"
                ;;
        esac
        
        # Check HTTP endpoint
        if [ -n "$container_ip" ]; then
            if check_http_health "http://$container_ip:5001/api/health" "$container_name"; then
                print_success "Container $container_name is healthy (IP: $container_ip, Docker: $docker_health_status)"
                ((healthy_count++))
                
                if [ "$verbose" = true ]; then
                    local response
                    response=$(get_health_response "http://$container_ip:5001/api/health")
                    echo "    Response: $response"
                fi
            else
                print_error "Container $container_name is not responding (IP: $container_ip, Docker: $docker_health_status)"
                overall_status=1
                
                if [ "$verbose" = true ]; then
                    # Show container logs
                    print_info "Last 5 log lines for $container_name:"
                    docker logs --tail=5 "$container_id" 2>&1 | sed 's/^/    /'
                fi
            fi
        else
            print_error "Container $container_name has no IP address (Docker: $docker_health_status)"
            overall_status=1
        fi
    done
    
    echo
    print_info "Health check summary:"
    print_info "Total containers: $total_count"
    print_info "Healthy containers: $healthy_count"
    
    if [ "$healthy_count" -eq "$total_count" ]; then
        print_success "All containers are healthy"
    else
        print_warning "$((total_count - healthy_count)) container(s) are unhealthy"
        overall_status=1
    fi
    
    # Check Nginx if it's running
    if $compose_cmd ps nginx &> /dev/null 2>&1 && [ "$($compose_cmd ps nginx | wc -l)" -gt 1 ]; then
        echo
        print_info "Checking Nginx proxy..."
        
        local nginx_port=80
        if [ -f .env ]; then
            nginx_port=$(grep -E '^NGINX_PORT=' .env | cut -d'=' -f2 | tr -d ' ' || echo "80")
        fi
        
        if check_http_health "http://localhost:$nginx_port/health" "Nginx Proxy"; then
            print_success "Nginx proxy is healthy on port $nginx_port"
        else
            print_error "Nginx proxy is not responding on port $nginx_port"
            overall_status=1
        fi
    fi
    
    return $overall_status
}

# Continuous monitoring
continuous_monitor() {
    local compose_cmd=$1
    local interval=${2:-30}
    local verbose=${3:-false}
    
    print_info "Starting continuous monitoring (interval: ${interval}s)"
    print_info "Press Ctrl+C to stop"
    echo
    
    while true; do
        local timestamp
        timestamp=$(date '+%Y-%m-%d %H:%M:%S')
        echo "[$timestamp] Health Check"
        echo "=========================="
        
        if perform_health_check "$compose_cmd" "$verbose"; then
            print_success "All services healthy"
        else
            print_warning "Some services are unhealthy"
        fi
        
        echo
        print_info "Waiting ${interval} seconds..."
        sleep "$interval"
        echo
    done
}

# Usage information
usage() {
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo
    echo "COMMANDS:"
    echo "  check                   Perform a single health check (default)"
    echo "  monitor [INTERVAL]      Continuous monitoring (default interval: 30s)"
    echo
    echo "OPTIONS:"
    echo "  -v, --verbose           Show detailed responses and logs"
    echo "  -h, --help              Show this help message"
    echo
    echo "EXAMPLES:"
    echo "  $0                      # Single health check"
    echo "  $0 check -v             # Verbose health check"
    echo "  $0 monitor 60           # Monitor every 60 seconds"
    echo "  $0 monitor 30 -v        # Verbose monitoring every 30 seconds"
}

# Main script
main() {
    local command="check"
    local interval=30
    local verbose=false
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            check)
                command="check"
                shift
                ;;
            monitor)
                command="monitor"
                if [[ $# -gt 1 && "$2" =~ ^[0-9]+$ ]]; then
                    interval="$2"
                    shift 2
                else
                    shift
                fi
                ;;
            -v|--verbose)
                verbose=true
                shift
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            *)
                if [[ "$1" =~ ^[0-9]+$ ]] && [ "$command" = "monitor" ]; then
                    interval="$1"
                    shift
                else
                    echo "Unknown option: $1"
                    usage
                    exit 1
                fi
                ;;
        esac
    done
    
    # Check Docker Compose
    local compose_cmd
    compose_cmd=$(check_docker_compose)
    
    # Execute command
    case $command in
        check)
            if perform_health_check "$compose_cmd" "$verbose"; then
                exit 0
            else
                exit 1
            fi
            ;;
        monitor)
            continuous_monitor "$compose_cmd" "$interval" "$verbose"
            ;;
        *)
            usage
            exit 1
            ;;
    esac
}

# Handle Ctrl+C gracefully
trap 'echo; print_info "Health check stopped"; exit 0' INT

# Run main function
main "$@"