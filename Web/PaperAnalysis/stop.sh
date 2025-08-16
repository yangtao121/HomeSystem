#!/bin/bash

# PaperAnalysis Docker Stop Script
# 停止PaperAnalysis服务

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 默认配置
COMPOSE_FILE="docker-compose.yml"
REMOVE_VOLUMES=false
REMOVE_IMAGES=false
CLEAN_ALL=false

# 帮助信息
show_help() {
    cat << EOF
PaperAnalysis Docker Stop Script

用法: $0 [选项]

选项:
    -f, --file FILE     指定docker-compose文件 (默认: docker-compose.yml)
    --remove-volumes    同时删除数据卷
    --remove-images     同时删除镜像
    --clean-all         清理所有相关资源 (容器、网络、卷、镜像)
    -h, --help          显示此帮助信息

示例:
    $0                      # 基本停止
    $0 --remove-volumes     # 停止并删除数据卷
    $0 --clean-all          # 完全清理

警告:
    --remove-volumes 将删除所有持久化数据
    --clean-all 将删除所有相关Docker资源

EOF
}

# 解析命令行参数
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -f|--file)
                COMPOSE_FILE="$2"
                shift 2
                ;;
            --remove-volumes)
                REMOVE_VOLUMES=true
                shift
                ;;
            --remove-images)
                REMOVE_IMAGES=true
                shift
                ;;
            --clean-all)
                CLEAN_ALL=true
                REMOVE_VOLUMES=true
                REMOVE_IMAGES=true
                shift
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                log_error "未知参数: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

# 检查依赖
check_dependencies() {
    log_info "检查依赖..."
    
    # 检查Docker Compose
    if ! docker compose version &> /dev/null; then
        log_error "Docker Compose 未安装或不在PATH中"
        exit 1
    fi
    
    # 检查配置文件
    if [ ! -f "$COMPOSE_FILE" ]; then
        log_error "Docker Compose 文件不存在: $COMPOSE_FILE"
        exit 1
    fi
    
    log_success "依赖检查通过"
}

# 显示当前状态
show_current_status() {
    log_info "当前服务状态:"
    docker compose -f "$COMPOSE_FILE" ps 2>/dev/null || log_warning "没有运行的服务"
}

# 停止服务
stop_services() {
    log_info "停止PaperAnalysis服务..."
    
    # 检查是否有运行的服务
    if ! docker compose -f "$COMPOSE_FILE" ps --services --filter "status=running" 2>/dev/null | grep -q .; then
        log_warning "没有运行的服务需要停止"
        return
    fi
    
    # 停止服务
    if docker compose -f "$COMPOSE_FILE" stop; then
        log_success "服务停止成功"
    else
        log_warning "服务停止过程中出现问题"
    fi
}

# 删除容器
remove_containers() {
    log_info "删除容器..."
    
    local down_args="down"
    
    if [ "$REMOVE_VOLUMES" = true ]; then
        down_args="$down_args --volumes"
        log_warning "将删除所有数据卷"
    fi
    
    if [ "$REMOVE_IMAGES" = true ]; then
        down_args="$down_args --rmi all"
        log_warning "将删除所有镜像"
    fi
    
    if docker compose -f "$COMPOSE_FILE" $down_args; then
        log_success "容器删除成功"
    else
        log_error "容器删除失败"
        exit 1
    fi
}

# 清理网络
clean_networks() {
    if [ "$CLEAN_ALL" = true ]; then
        log_info "清理Docker网络..."
        
        # 获取项目相关的网络
        local networks=$(docker network ls --filter "label=com.homesystem.network=paper-analysis" -q 2>/dev/null)
        
        if [ -n "$networks" ]; then
            echo "$networks" | xargs docker network rm 2>/dev/null || log_warning "部分网络清理失败"
            log_success "网络清理完成"
        else
            log_info "没有需要清理的网络"
        fi
    fi
}

# 清理孤立镜像
clean_orphaned_images() {
    if [ "$CLEAN_ALL" = true ]; then
        log_info "清理孤立镜像..."
        
        # 清理悬空镜像
        if docker images -f "dangling=true" -q | grep -q .; then
            docker rmi $(docker images -f "dangling=true" -q) 2>/dev/null || log_warning "部分悬空镜像清理失败"
            log_success "悬空镜像清理完成"
        else
            log_info "没有悬空镜像需要清理"
        fi
    fi
}

# 清理构建缓存
clean_build_cache() {
    if [ "$CLEAN_ALL" = true ]; then
        log_info "是否清理Docker构建缓存? [y/N]"
        read -r response
        case "$response" in
            [yY][eE][sS]|[yY])
                log_info "清理构建缓存..."
                docker builder prune -f
                log_success "构建缓存清理完成"
                ;;
            *)
                log_info "跳过构建缓存清理"
                ;;
        esac
    fi
}

# 显示清理摘要
show_cleanup_summary() {
    echo
    log_success "=== 清理完成 ==="
    
    log_info "清理摘要:"
    echo "  - 服务已停止: ✓"
    echo "  - 容器已删除: ✓"
    
    if [ "$REMOVE_VOLUMES" = true ]; then
        echo "  - 数据卷已删除: ✓"
        log_warning "注意: 所有持久化数据已被删除"
    fi
    
    if [ "$REMOVE_IMAGES" = true ]; then
        echo "  - 镜像已删除: ✓"
    fi
    
    if [ "$CLEAN_ALL" = true ]; then
        echo "  - 网络已清理: ✓"
        echo "  - 孤立镜像已清理: ✓"
    fi
    
    echo
    log_info "下次部署时运行: ./deploy.sh"
}

# 确认操作
confirm_action() {
    if [ "$REMOVE_VOLUMES" = true ] || [ "$CLEAN_ALL" = true ]; then
        echo
        log_warning "警告: 此操作将删除持久化数据!"
        log_warning "包括: 日志文件、上传的文件等"
        echo
        log_info "确认继续吗? [y/N]"
        read -r response
        case "$response" in
            [yY][eE][sS]|[yY])
                log_info "继续执行清理操作..."
                ;;
            *)
                log_info "操作已取消"
                exit 0
                ;;
        esac
    fi
}

# 主函数
main() {
    log_info "=== PaperAnalysis 停止脚本 ==="
    
    # 解析参数
    parse_args "$@"
    
    # 检查依赖
    check_dependencies
    
    # 显示当前状态
    show_current_status
    
    # 确认操作
    confirm_action
    
    # 停止服务
    stop_services
    
    # 删除容器
    remove_containers
    
    # 清理网络
    clean_networks
    
    # 清理镜像
    clean_orphaned_images
    
    # 清理构建缓存
    clean_build_cache
    
    # 显示摘要
    show_cleanup_summary
}

# 执行主函数
main "$@"