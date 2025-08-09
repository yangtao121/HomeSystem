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

# 端口检查和清理函数
check_and_kill_port() {
    local port=${1:-5002}
    log_info "检查端口 $port..."
    
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        log_warning "端口 $port 已被占用"
        local pid=$(lsof -Pi :$port -sTCP:LISTEN -t 2>/dev/null)
        if [ -n "$pid" ]; then
            echo -e "${YELLOW}占用进程 PID: $pid${NC}"
            read -p "是否终止占用进程？(y/N): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                kill -9 $pid 2>/dev/null && log_success "已终止进程 $pid" || log_error "终止进程失败"
            else
                log_info "请手动更改端口配置或终止占用进程"
                exit 1
            fi
        fi
    else
        log_success "端口 $port 可用"
    fi
}

# 获取脚本目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🚀 启动PaperAnalysis论文分析应用"
echo "=================================="

# 检查当前目录
if [ ! -f "app.py" ]; then
    log_error "请在PaperAnalysis目录下运行此脚本"
    exit 1
fi

# 检查Python环境
log_info "检查Python环境..."
if ! command -v python &> /dev/null; then
    log_error "Python未安装或不在PATH中"
    exit 1
fi

PYTHON_VERSION=$(python -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
log_success "Python版本: $PYTHON_VERSION"

# 检查并安装依赖
log_info "📦 检查依赖包..."
if [ -f "requirements.txt" ]; then
    if ! python -c "import flask" &> /dev/null; then
        log_info "⚠️  未找到Flask，正在安装依赖..."
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
log_info "🔗 检查数据库连接..."
python -c "
import sys, os
sys.path.append(os.path.join(os.getcwd(), '..', '..'))
try:
    from services.paper_explore_service import PaperService
    service = PaperService()
    stats = service.get_overview_stats()
    print(f'✅ 数据库连接成功，发现 {stats[\"basic\"][\"total_papers\"]} 篇论文')
except Exception as e:
    print(f'❌ 数据库连接失败: {e}')
    print('请确保Docker服务正在运行: docker compose up -d')
    exit(1)
" 2>/dev/null

if [ $? -ne 0 ]; then
    log_warning "数据库连接测试失败，请检查Docker服务状态"
    exit 1
fi

# 检查端口占用并提供清理选项
check_and_kill_port $FLASK_PORT

# 创建日志目录
mkdir -p logs

# 启动应用
echo ""
log_info "🌐 启动PaperAnalysis Web服务器..."
log_info "访问地址: http://$FLASK_HOST:$FLASK_PORT"
log_info "按 Ctrl+C 停止服务"
echo "========================="

export FLASK_APP=app.py
export PYTHONPATH="$HOMESYSTEM_PATH:$PYTHONPATH"

# 启动Flask应用
python app.py