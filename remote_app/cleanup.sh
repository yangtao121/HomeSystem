#!/bin/bash
# Remote App Services Cleanup Script
# This script helps clean up Docker resources for the OCR service

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
    echo "  Remote App Services Cleanup"
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

# Get confirmation from user
confirm_action() {
    local message=$1
    local default=${2:-"n"}
    
    if [ "$FORCE_YES" = true ]; then
        return 0
    fi
    
    while true; do
        if [ "$default" = "y" ]; then
            read -p "$message [Y/n]: " choice
            choice=${choice:-"y"}
        else
            read -p "$message [y/N]: " choice
            choice=${choice:-"n"}
        fi
        
        case $choice in
            [Yy]* ) return 0;;
            [Nn]* ) return 1;;
            * ) echo "Please answer yes (y) or no (n).";;
        esac
    done
}

# Stop and remove containers
stop_containers() {
    local compose_cmd=$1
    
    print_info "Stopping and removing containers..."
    
    if $compose_cmd ps -q &> /dev/null && [ "$($compose_cmd ps -q | wc -l)" -gt 0 ]; then
        # Stop all services including profiles
        $compose_cmd --profile proxy --profile monitoring down --remove-orphans
        print_success "All containers stopped and removed"
    else
        print_info "No containers are running"
    fi
}

# Remove images
remove_images() {
    local compose_cmd=$1
    local remove_all=${2:-false}
    
    print_info "Removing Docker images..."
    
    # Remove specific project images
    if docker images | grep -q "remote-app-ocr"; then
        if confirm_action "Remove remote-app-ocr image?"; then
            docker rmi remote-app-ocr:latest 2>/dev/null || print_warning "Failed to remove remote-app-ocr image"
            print_success "Removed remote-app-ocr image"
        fi
    fi
    
    # Remove other related images
    local related_images
    related_images=$(docker images --format "table {{.Repository}}:{{.Tag}}" | grep -E "(nginx|prometheus|grafana|redis)" | grep -v "REPOSITORY" || echo "")
    
    if [ -n "$related_images" ]; then
        echo "$related_images" | while read -r image; do
            if [ -n "$image" ]; then
                if confirm_action "Remove image $image?"; then
                    docker rmi "$image" 2>/dev/null || print_warning "Failed to remove image $image"
                    print_success "Removed image $image"
                fi
            fi
        done
    fi
    
    # Remove dangling images if requested
    if [ "$remove_all" = true ]; then
        print_info "Removing dangling images..."
        docker image prune -f &> /dev/null || true
        print_success "Removed dangling images"
    fi
}

# Remove volumes
remove_volumes() {
    local compose_cmd=$1
    local keep_data=${2:-true}
    
    if [ "$keep_data" = false ]; then
        print_info "Removing Docker volumes..."
        
        # Remove named volumes
        local volumes=("remote-app-models" "remote-app-results")
        for volume in "${volumes[@]}"; do
            if docker volume inspect "$volume" &> /dev/null; then
                if confirm_action "Remove volume $volume? (This will delete all data)"; then
                    docker volume rm "$volume" 2>/dev/null || print_warning "Failed to remove volume $volume"
                    print_success "Removed volume $volume"
                fi
            fi
        done
        
        # Remove anonymous volumes
        print_info "Removing anonymous volumes..."
        docker volume prune -f &> /dev/null || true
        print_success "Removed anonymous volumes"
    else
        print_info "Keeping Docker volumes (data preserved)"
    fi
}

# Remove networks
remove_networks() {
    local compose_cmd=$1
    
    print_info "Removing Docker networks..."
    
    # Remove project networks
    if docker network inspect remote-app-network &> /dev/null; then
        if confirm_action "Remove network remote-app-network?"; then
            docker network rm remote-app-network 2>/dev/null || print_warning "Failed to remove network remote-app-network"
            print_success "Removed network remote-app-network"
        fi
    fi
    
    # Remove unused networks
    print_info "Removing unused networks..."
    docker network prune -f &> /dev/null || true
    print_success "Removed unused networks"
}

# Clean up local files
cleanup_local_files() {
    local remove_volumes=${1:-false}
    local remove_logs=${2:-false}
    local remove_config=${3:-false}
    
    print_info "Cleaning up local files..."
    
    # Clean temporary files
    if [ -d "volumes/temp" ]; then
        if confirm_action "Clean temporary files in volumes/temp/?"; then
            rm -rf volumes/temp/* 2>/dev/null || true
            print_success "Cleaned temporary files"
        fi
    fi
    
    # Clean logs
    if [ "$remove_logs" = true ] && [ -d "volumes/logs" ]; then
        if confirm_action "Remove all log files?"; then
            rm -rf volumes/logs/* 2>/dev/null || true
            print_success "Removed log files"
        fi
    fi
    
    # Remove all volumes directory
    if [ "$remove_volumes" = true ] && [ -d "volumes" ]; then
        if confirm_action "Remove entire volumes directory? (This will delete ALL data including models)"; then
            rm -rf volumes/ 2>/dev/null || true
            print_success "Removed volumes directory"
        fi
    fi
    
    # Remove configuration
    if [ "$remove_config" = true ]; then
        if [ -f ".env" ] && confirm_action "Remove .env configuration file?"; then
            rm -f .env
            print_success "Removed .env file"
        fi
        
        if [ -d "nginx" ] && confirm_action "Remove nginx configuration?"; then
            rm -rf nginx/ 2>/dev/null || true
            print_success "Removed nginx configuration"
        fi
        
        if [ -d "monitoring" ] && confirm_action "Remove monitoring configuration?"; then
            rm -rf monitoring/ 2>/dev/null || true
            print_success "Removed monitoring configuration"
        fi
    fi
}

# Complete system cleanup
complete_cleanup() {
    print_warning "COMPLETE CLEANUP - This will remove EVERYTHING including data!"
    print_warning "This includes:"
    print_warning "- All containers and images"
    print_warning "- All data volumes (OCR models, results)"
    print_warning "- All configuration files"
    print_warning "- All log files"
    echo
    
    if ! confirm_action "Are you sure you want to perform complete cleanup?"; then
        print_info "Complete cleanup cancelled"
        return 0
    fi
    
    local compose_cmd
    compose_cmd=$(check_docker_compose)
    
    # Stop everything
    stop_containers "$compose_cmd"
    
    # Remove images
    remove_images "$compose_cmd" true
    
    # Remove volumes (delete data)
    remove_volumes "$compose_cmd" false
    
    # Remove networks
    remove_networks "$compose_cmd"
    
    # Remove local files
    cleanup_local_files true true true
    
    # Docker system cleanup
    print_info "Performing Docker system cleanup..."
    docker system prune -af --volumes &> /dev/null || true
    print_success "Docker system cleanup completed"
    
    print_success "Complete cleanup finished!"
    print_info "The system is now in a clean state."
    print_info "You can run './deploy.sh' to start fresh."
}

# Show current status
show_status() {
    local compose_cmd
    compose_cmd=$(check_docker_compose)
    
    print_info "Current Docker status:"
    echo
    
    # Show running containers
    echo "Running containers:"
    if $compose_cmd ps 2>/dev/null | grep -q "Up\|running"; then
        $compose_cmd ps
    else
        echo "  No containers running"
    fi
    echo
    
    # Show images
    echo "Docker images:"
    if docker images | grep -E "(remote-app|nginx|prometheus|grafana)" | grep -v "REPOSITORY"; then
        echo "Found related images"
    else
        echo "  No related images found"
    fi
    echo
    
    # Show volumes
    echo "Docker volumes:"
    if docker volume ls | grep -E "(remote-app|ocr)"; then
        echo "Found related volumes"
    else
        echo "  No related volumes found"
    fi
    echo
    
    # Show networks
    echo "Docker networks:"
    if docker network ls | grep -E "(remote-app)"; then
        echo "Found related networks"
    else
        echo "  No custom networks found"
    fi
    echo
    
    # Show disk usage
    echo "Docker disk usage:"
    docker system df 2>/dev/null || echo "  Could not get disk usage"
    echo
    
    # Show local files
    echo "Local files status:"
    if [ -d volumes ]; then
        local volume_size
        volume_size=$(du -sh volumes 2>/dev/null | cut -f1 || echo "unknown")
        echo "  Volumes directory: $volume_size"
        echo "    - Models: $(if [ -d volumes/models ]; then du -sh volumes/models 2>/dev/null | cut -f1; else echo "empty"; fi)"
        echo "    - Results: $(if [ -d volumes/results ]; then ls volumes/results 2>/dev/null | wc -l; else echo "0"; fi) files"
        echo "    - Logs: $(if [ -d volumes/logs ]; then ls volumes/logs 2>/dev/null | wc -l; else echo "0"; fi) files"
    else
        echo "  Volumes directory: not found"
    fi
    
    echo "  Config files:"
    echo "    - .env: $(if [ -f .env ]; then echo "exists"; else echo "not found"; fi)"
    echo "    - nginx/: $(if [ -d nginx ]; then echo "exists"; else echo "not found"; fi)"
    echo "    - monitoring/: $(if [ -d monitoring ]; then echo "exists"; else echo "not found"; fi)"
}

# Usage information
usage() {
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo
    echo "COMMANDS:"
    echo "  stop                    Stop and remove containers only"
    echo "  images                  Remove Docker images"
    echo "  volumes                 Remove Docker volumes (delete data)"
    echo "  networks                Remove Docker networks"
    echo "  files                   Clean up local files"
    echo "  complete                Complete cleanup (everything)"
    echo "  status                  Show current status"
    echo
    echo "OPTIONS:"
    echo "  -y, --yes               Assume yes to all prompts (dangerous)"
    echo "  --keep-data             Keep volumes and data when cleaning"
    echo "  --remove-logs           Remove log files"
    echo "  --remove-config         Remove configuration files"
    echo "  -h, --help              Show this help message"
    echo
    echo "EXAMPLES:"
    echo "  $0 stop                 # Stop containers only"
    echo "  $0 images               # Remove images only"
    echo "  $0 complete -y          # Complete cleanup without prompts"
    echo "  $0 files --remove-logs  # Clean files and remove logs"
    echo "  $0 status               # Show current status"
    echo
    echo "SAFETY NOTES:"
    echo "  • Use 'stop' to just stop services without data loss"
    echo "  • Use 'complete' only when you want to remove everything"
    echo "  • Always backup important data before cleanup"
    echo "  • Use --keep-data to preserve volumes during cleanup"
}

# Main script
main() {
    local command=""
    local keep_data=true
    local remove_logs=false
    local remove_config=false
    
    # Global flag for force yes
    FORCE_YES=false
    
    if [ $# -eq 0 ]; then
        usage
        exit 1
    fi
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            stop)
                command="stop"
                shift
                ;;
            images)
                command="images"
                shift
                ;;
            volumes)
                command="volumes"
                keep_data=false
                shift
                ;;
            networks)
                command="networks"
                shift
                ;;
            files)
                command="files"
                shift
                ;;
            complete)
                command="complete"
                shift
                ;;
            status)
                command="status"
                shift
                ;;
            -y|--yes)
                FORCE_YES=true
                shift
                ;;
            --keep-data)
                keep_data=true
                shift
                ;;
            --remove-logs)
                remove_logs=true
                shift
                ;;
            --remove-config)
                remove_config=true
                shift
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                usage
                exit 1
                ;;
        esac
    done
    
    print_header
    print_info "Selected command: $command"
    echo
    
    # Get Docker Compose command
    local compose_cmd
    compose_cmd=$(check_docker_compose)
    
    # Execute command
    case $command in
        stop)
            stop_containers "$compose_cmd"
            ;;
        images)
            remove_images "$compose_cmd"
            ;;
        volumes)
            remove_volumes "$compose_cmd" "$keep_data"
            ;;
        networks)
            remove_networks "$compose_cmd"
            ;;
        files)
            cleanup_local_files false "$remove_logs" "$remove_config"
            ;;
        complete)
            complete_cleanup
            ;;
        status)
            show_status
            ;;
        *)
            print_error "No valid command specified"
            usage
            exit 1
            ;;
    esac
    
    echo
    print_success "Cleanup operation completed"
    
    if [ "$command" != "status" ]; then
        print_info "Run '$0 status' to see current state"
        print_info "Run './deploy.sh' to start services again"
    fi
}

# Handle Ctrl+C gracefully
trap 'echo; print_info "Cleanup interrupted"; exit 0' INT

# Run main function
main "$@"