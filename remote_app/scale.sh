#!/bin/bash
# Remote App Services Scaling Script
# This script helps scale OCR services up or down

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${BLUE}"
    echo "============================================"
    echo "  Remote App Services Scaling"
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

# Check Docker Compose command
get_docker_compose_cmd() {
    if command -v docker-compose &> /dev/null; then
        echo "docker-compose"
    elif docker compose version &> /dev/null; then
        echo "docker compose"
    else
        print_error "Docker Compose is not installed"
    fi
}

# Get current scale
get_current_scale() {
    local compose_cmd=$1
    local service_count
    
    service_count=$($compose_cmd ps ocr-service 2>/dev/null | grep -v "Name\|----" | wc -l || echo "0")
    echo "$service_count"
}

# Scale services
scale_services() {
    local compose_cmd=$1
    local target_scale=$2
    local current_scale
    
    current_scale=$(get_current_scale "$compose_cmd")
    
    print_info "Current OCR service instances: $current_scale"
    print_info "Target OCR service instances: $target_scale"
    
    if [ "$current_scale" -eq "$target_scale" ]; then
        print_success "Already running $target_scale instance(s)"
        return 0
    fi
    
    print_info "Scaling OCR service to $target_scale instance(s)..."
    
    # Scale the service
    if [ "$target_scale" -eq 0 ]; then
        $compose_cmd stop ocr-service
        print_success "Stopped all OCR service instances"
    else
        $compose_cmd up -d --scale ocr-service="$target_scale"
        print_success "Scaled OCR service to $target_scale instance(s)"
    fi
    
    # Wait for services to be ready
    if [ "$target_scale" -gt 0 ]; then
        print_info "Waiting for services to be ready..."
        sleep 10
        
        # Check health of instances
        check_instances_health "$compose_cmd"
    fi
}

# Check health of all instances
check_instances_health() {
    local compose_cmd=$1
    local healthy_count=0
    local total_count
    
    total_count=$(get_current_scale "$compose_cmd")
    
    print_info "Checking health of $total_count instance(s)..."
    
    # Get container IDs
    local container_ids
    container_ids=$($compose_cmd ps -q ocr-service)
    
    for container_id in $container_ids; do
        local container_name
        container_name=$(docker inspect --format='{{.Name}}' "$container_id" | sed 's/^\/*//')
        
        local container_ip
        container_ip=$(docker inspect --format='{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$container_id")
        
        if [ -n "$container_ip" ]; then
            if curl -f -s "http://$container_ip:5001/api/health" > /dev/null; then
                print_success "Instance $container_name is healthy"
                ((healthy_count++))
            else
                print_warning "Instance $container_name is not responding"
            fi
        else
            print_warning "Could not get IP for instance $container_name"
        fi
    done
    
    if [ "$healthy_count" -eq "$total_count" ]; then
        print_success "All $total_count instance(s) are healthy"
    else
        print_warning "$healthy_count out of $total_count instance(s) are healthy"
    fi
}

# Show current status
show_status() {
    local compose_cmd=$1
    
    print_info "Current service status:"
    echo
    
    $compose_cmd ps
    
    echo
    print_info "Service logs (last 10 lines):"
    $compose_cmd logs --tail=10 ocr-service
}

# Auto-scale based on load (placeholder for future implementation)
auto_scale() {
    local compose_cmd=$1
    local target_cpu=$2
    local max_instances=$3
    
    print_info "Auto-scaling not yet implemented"
    print_info "Target CPU threshold: ${target_cpu}%"
    print_info "Max instances: $max_instances"
    
    # Future implementation could monitor CPU/memory usage
    # and automatically scale based on load
    print_warning "Use manual scaling for now"
}

# Usage information
usage() {
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo
    echo "COMMANDS:"
    echo "  up NUMBER               Scale up to NUMBER instances"
    echo "  down NUMBER             Scale down to NUMBER instances"
    echo "  stop                    Stop all OCR service instances"
    echo "  status                  Show current service status"
    echo "  health                  Check health of all instances"
    echo "  auto                    Auto-scale based on load (not implemented)"
    echo
    echo "OPTIONS:"
    echo "  -h, --help              Show this help message"
    echo
    echo "EXAMPLES:"
    echo "  $0 up 3                 # Scale up to 3 instances"
    echo "  $0 down 1               # Scale down to 1 instance"
    echo "  $0 stop                 # Stop all instances"
    echo "  $0 status               # Show current status"
    echo "  $0 health               # Check health of all instances"
}

# Main script
main() {
    local command=""
    local scale_number=""
    
    if [ $# -eq 0 ]; then
        usage
        exit 1
    fi
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            up)
                command="scale"
                scale_number="$2"
                if [[ ! "$scale_number" =~ ^[0-9]+$ ]]; then
                    print_error "Scale number must be a positive integer"
                fi
                shift 2
                ;;
            down)
                command="scale"
                scale_number="$2"
                if [[ ! "$scale_number" =~ ^[0-9]+$ ]]; then
                    print_error "Scale number must be a positive integer"
                fi
                shift 2
                ;;
            stop)
                command="scale"
                scale_number="0"
                shift
                ;;
            status)
                command="status"
                shift
                ;;
            health)
                command="health"
                shift
                ;;
            auto)
                command="auto"
                shift
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            *)
                print_error "Unknown command: $1"
                ;;
        esac
    done
    
    print_header
    
    # Get Docker Compose command
    local compose_cmd
    compose_cmd=$(get_docker_compose_cmd)
    
    # Execute command
    case $command in
        scale)
            scale_services "$compose_cmd" "$scale_number"
            ;;
        status)
            show_status "$compose_cmd"
            ;;
        health)
            check_instances_health "$compose_cmd"
            ;;
        auto)
            auto_scale "$compose_cmd" "70" "5"
            ;;
        *)
            print_error "No valid command specified"
            ;;
    esac
    
    echo
    print_success "Operation completed"
}

# Run main function
main "$@"