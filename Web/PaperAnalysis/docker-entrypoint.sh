#!/bin/bash

# PaperAnalysis Docker Entrypoint Script
# 启动前检查依赖服务并初始化应用

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

# 检查环境变量
check_env_vars() {
    log_info "检查环境变量配置..."
    
    local required_vars=(
        "DB_HOST"
        "DB_PORT"
        "DB_NAME"
        "DB_USER"
        "DB_PASSWORD"
        "REDIS_HOST"
        "REDIS_PORT"
    )
    
    local missing_vars=()
    
    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ]; then
            missing_vars+=("$var")
        fi
    done
    
    if [ ${#missing_vars[@]} -ne 0 ]; then
        log_error "缺少必需的环境变量:"
        for var in "${missing_vars[@]}"; do
            log_error "  - $var"
        done
        exit 1
    fi
    
    log_success "环境变量检查通过"
}

# 等待服务可用
wait_for_service() {
    local host=$1
    local port=$2
    local service_name=$3
    local timeout=${4:-60}
    
    log_info "等待 $service_name 服务可用 ($host:$port)..."
    
    local count=0
    while ! nc -z "$host" "$port" >/dev/null 2>&1; do
        if [ $count -ge $timeout ]; then
            log_error "$service_name 服务在 $timeout 秒内未响应"
            return 1
        fi
        
        log_info "等待 $service_name 服务启动... (${count}s/${timeout}s)"
        sleep 2
        count=$((count + 2))
    done
    
    log_success "$service_name 服务已可用"
}

# 检查数据库连接
check_database() {
    log_info "检查数据库连接..."
    
    # 等待PostgreSQL服务
    if ! wait_for_service "$DB_HOST" "$DB_PORT" "PostgreSQL" 60; then
        log_error "无法连接到PostgreSQL数据库"
        exit 1
    fi
    
    # 测试数据库连接
    export PGPASSWORD="$DB_PASSWORD"
    if pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" >/dev/null 2>&1; then
        log_success "数据库连接正常"
    else
        log_error "数据库连接失败"
        exit 1
    fi
}

# 检查Redis连接
check_redis() {
    log_info "检查Redis连接..."
    
    # 等待Redis服务
    if ! wait_for_service "$REDIS_HOST" "$REDIS_PORT" "Redis" 30; then
        log_error "无法连接到Redis服务"
        exit 1
    fi
    
    # 测试Redis连接
    if redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ping >/dev/null 2>&1; then
        log_success "Redis连接正常"
    else
        log_error "Redis连接失败"
        exit 1
    fi
}

# 检查OCR服务（可选）
check_ocr_service() {
    if [ -n "$REMOTE_OCR_ENDPOINT" ]; then
        log_info "检查OCR服务连接..."
        
        # 从URL中提取主机和端口
        local ocr_host=$(echo "$REMOTE_OCR_ENDPOINT" | sed -n 's|.*://\([^:]*\):\([0-9]*\).*|\1|p')
        local ocr_port=$(echo "$REMOTE_OCR_ENDPOINT" | sed -n 's|.*://\([^:]*\):\([0-9]*\).*|\2|p')
        
        if [ -n "$ocr_host" ] && [ -n "$ocr_port" ]; then
            if wait_for_service "$ocr_host" "$ocr_port" "OCR" 30; then
                log_success "OCR服务连接正常"
            else
                log_warning "OCR服务暂时不可用，应用仍可正常运行"
            fi
        else
            log_warning "无法解析OCR服务地址: $REMOTE_OCR_ENDPOINT"
        fi
    else
        log_info "未配置OCR服务，跳过检查"
    fi
}

# 初始化应用
init_app() {
    log_info "初始化应用..."
    
    # 创建必要的目录
    mkdir -p /app/logs /app/uploads /app/static/uploads
    
    # 创建数据目录结构
    log_info "创建数据目录结构..."
    mkdir -p /app/data/paper_analyze
    mkdir -p /app/data/paper_gather/task_history
    mkdir -p /app/data/paper_gather/config_presets
    mkdir -p /app/data/paper_gather/scheduled_tasks
    
    # 设置权限
    chmod 755 /app/logs /app/uploads /app/static/uploads
    chmod 755 /app/data /app/data/paper_analyze /app/data/paper_gather
    chmod 755 /app/data/paper_gather/task_history /app/data/paper_gather/config_presets /app/data/paper_gather/scheduled_tasks
    
    log_success "应用初始化完成"
}

# 健康检查端点
setup_health_check() {
    log_info "设置健康检查..."
    
    # 添加健康检查路由到app.py（如果不存在）
    if ! grep -q "/api/health" /app/app.py; then
        log_info "添加健康检查端点..."
        cat >> /app/app.py << 'EOF'

# 健康检查端点
@app.route('/api/health')
def health_check():
    """健康检查端点"""
    try:
        from services.paper_explore_service import PaperService
        
        # 检查数据库连接
        paper_service = PaperService()
        
        # 基本的连接测试
        return jsonify({
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "service": "paper-analysis"
        }), 200
    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
            "service": "paper-analysis"
        }), 503
EOF
    fi
    
    log_success "健康检查设置完成"
}

# 主函数
main() {
    log_info "=== PaperAnalysis 容器启动 ==="
    
    # 检查环境变量
    check_env_vars
    
    # 检查依赖服务
    check_database
    check_redis
    check_ocr_service
    
    # 初始化应用
    init_app
    setup_health_check
    
    log_success "=== 所有检查通过，启动应用 ==="
    
    # 执行传入的命令
    exec "$@"
}

# 如果是直接执行此脚本
if [ "${BASH_SOURCE[0]}" == "${0}" ]; then
    main "$@"
fi