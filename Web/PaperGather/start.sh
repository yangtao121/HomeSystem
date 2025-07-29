#!/bin/bash

# PaperGather Web应用启动脚本

# 设置脚本目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印带颜色的信息
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查Python环境
check_python() {
    print_info "检查Python环境..."
    
    if ! command -v python3 &> /dev/null; then
        print_error "Python3 未安装，请先安装Python 3.8+"
        exit 1
    fi
    
    PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
    print_success "Python版本: $PYTHON_VERSION"
}

# 检查虚拟环境
check_venv() {
    print_info "检查虚拟环境..."
    
    if [[ "$VIRTUAL_ENV" != "" ]]; then
        print_success "已在虚拟环境中: $VIRTUAL_ENV"
    else
        print_warning "建议在虚拟环境中运行"
        
        # 如果是交互式终端，询问用户
        if [[ -t 0 ]]; then
            read -p "是否继续？(y/N): " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                print_info "取消启动"
                exit 0
            fi
        else
            print_info "非交互式模式，自动继续..."
        fi
    fi
}

# 安装依赖
install_deps() {
    print_info "检查并安装依赖..."
    
    if [[ ! -f "requirements.txt" ]]; then
        print_error "requirements.txt 文件不存在"
        exit 1
    fi
    
    # 检查是否需要安装依赖
    if python3 -c "import flask" 2>/dev/null; then
        print_success "依赖已安装"
    else
        print_info "安装Python依赖..."
        pip3 install -r requirements.txt
        
        if [[ $? -eq 0 ]]; then
            print_success "依赖安装完成"
        else
            print_error "依赖安装失败"
            exit 1
        fi
    fi
}

# 检查数据库连接
check_database() {
    print_info "检查数据库连接..."
    
    python3 -c "
import sys
import os

# 添加HomeSystem到路径
current_dir = os.getcwd()
homesystem_path = os.path.join(current_dir, '..', '..')
sys.path.append(homesystem_path)

try:
    from HomeSystem.integrations.database import DatabaseOperations
    db_ops = DatabaseOperations()
    print('数据库连接成功')
except Exception as e:
    print(f'数据库连接失败: {e}')
    sys.exit(1)
" 2>/dev/null

    if [[ $? -eq 0 ]]; then
        print_success "数据库连接正常"
    else
        print_error "数据库连接失败，请检查:"
        echo "  1. 数据库服务是否启动 (docker compose up -d)"
        echo "  2. 环境变量是否正确配置"
        echo "  3. 网络连接是否正常"
        exit 1
    fi
}

# 检查端口占用
check_port() {
    local port=${1:-5001}
    print_info "检查端口 $port..."
    
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        print_warning "端口 $port 已被占用"
        read -p "是否终止占用进程？(y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            local pid=$(lsof -Pi :$port -sTCP:LISTEN -t)
            kill -9 $pid 2>/dev/null
            print_success "已终止进程 $pid"
        else
            print_info "请手动更改端口配置"
        fi
    else
        print_success "端口 $port 可用"
    fi
}

# 设置环境变量
setup_env() {
    print_info "设置环境变量..."
    
    # 检查.env文件
    if [[ ! -f ".env" ]]; then
        print_info "创建默认.env文件..."
        cat > .env << EOF
# 数据库配置
DB_HOST=localhost
DB_PORT=15432
DB_NAME=homesystem
DB_USER=homesystem
DB_PASSWORD=homesystem123

# Redis配置
REDIS_HOST=localhost
REDIS_PORT=16379
REDIS_DB=0

# Flask配置
FLASK_HOST=0.0.0.0
FLASK_PORT=5001
FLASK_DEBUG=True
SECRET_KEY=papergather-dev-key-change-in-production
EOF
        print_success "已创建默认.env文件"
    fi
    
    # 加载环境变量
    if [[ -f ".env" ]]; then
        export $(cat .env | grep -v '^#' | xargs)
        print_success "环境变量加载完成"
    fi
}

# 启动应用
start_app() {
    print_info "启动PaperGather Web应用..."
    
    # 设置Flask环境
    export FLASK_APP=app.py
    export FLASK_ENV=development
    
    # 显示启动信息
    local host=${FLASK_HOST:-0.0.0.0}
    local port=${FLASK_PORT:-5001}
    
    print_success "PaperGather Web应用启动中..."
    echo
    echo "  访问地址: http://$host:$port"
    echo "  本地地址: http://localhost:$port"  
    echo
    print_info "按 Ctrl+C 停止应用"
    echo
    
    # 启动Flask应用
    python3 app.py
}

# 主函数
main() {
    echo "=================================================="
    echo "         PaperGather Web应用启动器"
    echo "=================================================="
    echo
    
    # 执行检查和启动流程
    check_python
    check_venv
    install_deps
    setup_env
    check_database
    check_port ${FLASK_PORT:-5001}
    
    echo
    print_success "所有检查通过，准备启动应用..."
    echo
    
    # 启动应用
    start_app
}

# 错误处理
trap 'print_error "启动过程中发生错误"; exit 1' ERR

# 运行主函数
main "$@"