#!/bin/bash

# PaperAnalysis 启动脚本
# 论文收集与分析系统统一启动脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 函数定义
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

# 获取脚本目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 检查Python环境
log_info "检查Python环境..."
if ! command -v python &> /dev/null; then
    log_error "Python未安装或不在PATH中"
    exit 1
fi

PYTHON_VERSION=$(python -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
log_success "Python版本: $PYTHON_VERSION"

# 检查并安装依赖
log_info "检查Python依赖包..."
if [ -f "requirements.txt" ]; then
    if ! python -c "import flask, flask_moment, psycopg2, redis, loguru, mistune" &> /dev/null; then
        log_info "安装缺失的依赖包..."
        pip install -r requirements.txt
        if [ $? -eq 0 ]; then
            log_success "依赖包安装完成"
        else
            log_error "依赖包安装失败"
            exit 1
        fi
    else
        log_success "所有依赖包已安装"
    fi
else
    log_warning "未找到requirements.txt文件"
fi

# 检查HomeSystem模块
log_info "检查HomeSystem模块可用性..."
HOMESYSTEM_PATH="../.."
if [ -d "$HOMESYSTEM_PATH/HomeSystem" ]; then
    log_success "HomeSystem模块路径存在"
else
    log_error "HomeSystem模块路径不存在: $HOMESYSTEM_PATH/HomeSystem"
    log_info "当前目录内容:"
    ls -la $HOMESYSTEM_PATH/
    exit 1
fi

# 检查环境变量配置
log_info "检查环境变量配置..."
if [ -f ".env" ]; then
    log_success "找到.env配置文件"
    source .env
elif [ -f "$HOMESYSTEM_PATH/.env" ]; then
    log_success "使用根目录.env配置文件"
    source "$HOMESYSTEM_PATH/.env"
else
    log_warning "未找到.env文件，将使用默认配置"
fi

# 设置默认环境变量
export FLASK_HOST=${FLASK_HOST:-"0.0.0.0"}
export FLASK_PORT=${FLASK_PORT:-"5002"}
export FLASK_DEBUG=${FLASK_DEBUG:-"True"}
export DB_HOST=${DB_HOST:-"localhost"}
export DB_PORT=${DB_PORT:-"15432"}
export DB_NAME=${DB_NAME:-"homesystem"}
export DB_USER=${DB_USER:-"homesystem"}
export DB_PASSWORD=${DB_PASSWORD:-"homesystem123"}
export REDIS_HOST=${REDIS_HOST:-"localhost"}
export REDIS_PORT=${REDIS_PORT:-"16379"}
export REDIS_DB=${REDIS_DB:-"0"}

log_info "应用配置:"
log_info "  - 服务地址: http://$FLASK_HOST:$FLASK_PORT"
log_info "  - 数据库: $DB_HOST:$DB_PORT/$DB_NAME"
log_info "  - Redis: $REDIS_HOST:$REDIS_PORT/$REDIS_DB"

# 测试数据库连接
log_info "测试数据库连接..."
python -c "
import sys, os
sys.path.append(os.path.join(os.getcwd(), '..', '..'))
try:
    from services.paper_explore_service import PaperService
    service = PaperService()
    stats = service.get_overview_stats()
    print(f'✓ 数据库连接成功，共有 {stats[\"basic\"][\"total_papers\"]} 篇论文')
except Exception as e:
    print(f'✗ 数据库连接失败: {e}')
    print('⚠️  应用将继续启动，但数据库功能可能受限')
    exit(0)
" 2>/dev/null

if [ $? -eq 0 ]; then
    log_success "数据库连接测试通过"
else
    log_warning "数据库连接测试失败，但应用将继续启动"
fi

# 检查端口占用
log_info "检查端口 $FLASK_PORT 是否可用..."
if lsof -Pi :$FLASK_PORT -sTCP:LISTEN -t >/dev/null ; then
    log_warning "端口 $FLASK_PORT 已被占用"
    log_info "尝试查找占用进程..."
    lsof -Pi :$FLASK_PORT -sTCP:LISTEN
    log_info "如需继续，请先停止占用端口的进程或更改端口配置"
else
    log_success "端口 $FLASK_PORT 可用"
fi

# 创建日志目录
mkdir -p logs

# 启动应用
log_info "启动PaperAnalysis应用..."
log_info "按 Ctrl+C 停止应用"
echo "========================="

export FLASK_APP=app.py
export PYTHONPATH="$HOMESYSTEM_PATH:$PYTHONPATH"

# 启动Flask应用
python app.py