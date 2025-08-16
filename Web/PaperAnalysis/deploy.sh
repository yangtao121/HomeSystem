#!/bin/bash

# PaperAnalysis Docker Deploy Script
# 一键部署PaperAnalysis服务

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
ENVIRONMENT="development"
BUILD_IMAGE=false
RECREATE_CONTAINERS=false
PROFILE=""
COMPOSE_FILE="docker-compose.yml"

# 帮助信息
show_help() {
    cat << EOF
PaperAnalysis Docker Deploy Script

用法: $0 [选项]

选项:
    -e, --env ENV       设置环境 (development|production) (默认: development)
    -f, --file FILE     指定docker-compose文件 (默认: docker-compose.yml)
    -p, --profile PROF  启用docker-compose profile (如: proxy, monitoring)
    --build             部署前重新构建镜像
    --recreate          强制重建容器
    --down              停止并删除所有容器
    --logs              查看容器日志
    --status            查看服务状态
    -h, --help          显示此帮助信息

示例:
    $0                              # 开发环境部署
    $0 -e production                # 生产环境部署
    $0 --build                      # 重新构建并部署
    $0 -p proxy                     # 启用nginx代理
    $0 --down                       # 停止服务
    $0 --logs                       # 查看日志
    $0 --status                     # 查看状态

环境变量:
    通过 .env 文件配置服务参数，参考 .env.example

EOF
}

# 解析命令行参数
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -e|--env)
                ENVIRONMENT="$2"
                shift 2
                ;;
            -f|--file)
                COMPOSE_FILE="$2"
                shift 2
                ;;
            -p|--profile)
                PROFILE="$2"
                shift 2
                ;;
            --build)
                BUILD_IMAGE=true
                shift
                ;;
            --recreate)
                RECREATE_CONTAINERS=true
                shift
                ;;
            --down)
                stop_services
                exit 0
                ;;
            --logs)
                show_logs
                exit 0
                ;;
            --status)
                show_status
                exit 0
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
    
    # 检查Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker 未安装或不在PATH中"
        exit 1
    fi
    
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

# 检查环境配置
check_environment() {
    log_info "检查环境配置..."
    
    # 检查.env文件
    if [ ! -f ".env" ]; then
        log_warning ".env 文件不存在"
        
        if [ -f ".env.example" ]; then
            log_info "发现 .env.example 文件，是否复制为 .env? [y/N]"
            read -r response
            case "$response" in
                [yY][eE][sS]|[yY])
                    cp .env.example .env
                    log_warning "已复制 .env.example 为 .env，请根据实际情况修改配置"
                    log_warning "配置文件路径: $(pwd)/.env"
                    ;;
                *)
                    log_error "需要 .env 文件才能继续部署"
                    exit 1
                    ;;
            esac
        else
            log_error "缺少 .env 和 .env.example 文件"
            exit 1
        fi
    fi
    
    # 验证关键环境变量
    source .env
    
    # 必需的环境变量（连接相关）
    local required_vars=(
        "DB_HOST"
        "DB_PORT"
        "REDIS_HOST" 
        "REDIS_PORT"
    )
    
    # 可选的环境变量（有默认值）
    local optional_vars=(
        "SECRET_KEY"
    )
    
    local missing_vars=()
    
    # 检查必需变量
    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ]; then
            missing_vars+=("$var")
        fi
    done
    
    if [ ${#missing_vars[@]} -ne 0 ]; then
        log_error "以下关键环境变量未配置:"
        for var in "${missing_vars[@]}"; do
            log_error "  - $var"
        done
        log_error "请检查 .env 文件配置"
        exit 1
    fi
    
    # 检查可选变量并提供默认值
    if [ -z "${SECRET_KEY}" ]; then
        log_info "SECRET_KEY 未设置，使用开发环境默认值"
        export SECRET_KEY="paper-analysis-dev-key-$(date +%s)"
        log_info "生成的临时密钥: ${SECRET_KEY:0:20}..."
    fi
    
    log_success "环境配置检查通过"
}

# 检查权限
check_permissions() {
    log_info "检查目录权限..."
    
    if [ -f "./setup-permissions.sh" ]; then
        if ./setup-permissions.sh --check > /dev/null 2>&1; then
            log_success "目录权限检查通过"
        else
            log_warning "发现权限问题，尝试自动修复..."
            log_info "运行权限检查脚本..."
            ./setup-permissions.sh --check
            echo
            log_error "请先解决权限问题，然后重新运行部署"
            log_info "快速修复命令: ./setup-permissions.sh --fix"
            exit 1
        fi
    else
        log_warning "权限检查脚本不存在，跳过权限检查"
    fi
}

# 构建镜像
build_image() {
    if [ "$BUILD_IMAGE" = true ]; then
        log_info "构建Docker镜像..."
        
        if [ -f "build.sh" ]; then
            ./build.sh
        else
            docker compose -f "$COMPOSE_FILE" build
        fi
        
        log_success "镜像构建完成"
    fi
}

# 创建必要目录
create_directories() {
    log_info "创建必要目录..."
    
    local dirs=(
        "logs"
        "uploads"
        "static/uploads"
    )
    
    for dir in "${dirs[@]}"; do
        if [ ! -d "$dir" ]; then
            mkdir -p "$dir"
            log_info "创建目录: $dir"
        fi
    done
    
    log_success "目录创建完成"
}

# 部署服务
deploy_services() {
    log_info "部署服务..."
    
    local compose_cmd="docker compose -f $COMPOSE_FILE"
    
    # 添加profile
    if [ -n "$PROFILE" ]; then
        compose_cmd="$compose_cmd --profile $PROFILE"
    fi
    
    # 停止现有服务
    log_info "停止现有服务..."
    $compose_cmd down
    
    # 启动服务
    local up_args="up -d"
    
    if [ "$RECREATE_CONTAINERS" = true ]; then
        up_args="$up_args --force-recreate"
    fi
    
    log_info "启动服务..."
    if $compose_cmd $up_args; then
        log_success "服务启动成功"
    else
        log_error "服务启动失败"
        exit 1
    fi
}

# 等待服务就绪
wait_for_services() {
    log_info "等待服务就绪..."
    
    local max_attempts=30
    local attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if docker compose -f "$COMPOSE_FILE" exec -T paper-analysis curl -f http://localhost:5002/api/health &> /dev/null; then
            log_success "服务已就绪"
            return 0
        fi
        
        attempt=$((attempt + 1))
        log_info "等待服务启动... ($attempt/$max_attempts)"
        sleep 5
    done
    
    log_warning "服务可能未完全就绪，请检查日志"
}

# 显示服务状态
show_status() {
    log_info "服务状态:"
    docker compose -f "$COMPOSE_FILE" ps
    
    echo
    log_info "服务健康状态:"
    docker compose -f "$COMPOSE_FILE" exec -T paper-analysis curl -s http://localhost:5002/api/health | python3 -m json.tool 2>/dev/null || echo "健康检查失败"
}

# 显示日志
show_logs() {
    log_info "显示服务日志:"
    docker compose -f "$COMPOSE_FILE" logs -f --tail=100
}

# 停止服务
stop_services() {
    log_info "停止服务..."
    docker compose -f "$COMPOSE_FILE" down
    log_success "服务已停止"
}

# 显示部署信息
show_deployment_info() {
    source .env
    
    echo
    log_success "=== 部署完成 ==="
    echo
    log_info "服务信息:"
    echo "  - PaperAnalysis Web: http://localhost:${FLASK_PORT:-5002}"
    echo "  - 健康检查: http://localhost:${FLASK_PORT:-5002}/api/health"
    echo
    log_info "管理命令:"
    echo "  - 查看状态: ./deploy.sh --status"
    echo "  - 查看日志: ./deploy.sh --logs"
    echo "  - 停止服务: ./deploy.sh --down"
    echo "  - 重新部署: ./deploy.sh --recreate"
    echo
    log_info "配置文件:"
    echo "  - 环境配置: .env"
    echo "  - Docker配置: $COMPOSE_FILE"
}

# 主函数
main() {
    log_info "=== PaperAnalysis 部署脚本 ==="
    
    # 解析参数
    parse_args "$@"
    
    # 检查依赖
    check_dependencies
    
    # 检查环境
    check_environment
    
    # 检查权限
    check_permissions
    
    # 构建镜像
    build_image
    
    # 创建目录
    create_directories
    
    # 部署服务
    deploy_services
    
    # 等待服务就绪
    # wait_for_services
    
    # 显示状态
    show_status
    
    # 显示部署信息
    show_deployment_info
}

# 执行主函数
main "$@"