#!/bin/bash

# ArXiv论文数据可视化Web应用启动脚本

echo "🚀 启动ArXiv论文数据可视化Web应用"
echo "=================================="

# 检查当前目录
if [ ! -f "app.py" ]; then
    echo "❌ 错误: 请在ExplorePaperData目录下运行此脚本"
    exit 1
fi

# 检查Python环境
if ! command -v python &> /dev/null; then
    echo "❌ 错误: 未找到Python，请确保Python已安装"
    exit 1
fi

# 检查依赖
echo "📦 检查依赖包..."
if ! python -c "import flask" &> /dev/null; then
    echo "⚠️  未找到Flask，正在安装依赖..."
    pip install -r requirements.txt
fi

# 检查数据库连接
echo "🔗 检查数据库连接..."
python -c "
import sys
import os
# 添加项目根目录到路径
project_root = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.append(project_root)
from database import DatabaseManager
try:
    db_manager = DatabaseManager()
    with db_manager.get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM arxiv_papers')
        count = cursor.fetchone()[0]
        print(f'✅ 数据库连接成功，发现 {count} 篇论文')
        cursor.close()
except Exception as e:
    print(f'❌ 数据库连接失败: {e}')
    print('请确保Docker服务正在运行: docker compose up -d')
    exit(1)
"

if [ $? -ne 0 ]; then
    exit 1
fi

# 设置环境变量
export FLASK_ENV=development
export FLASK_DEBUG=true

check_port() {
    local port=${1:-5000}
    echo "🔍 检查端口 $port..."
    
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo "⚠️  端口 $port 已被占用"
        read -p "是否终止占用进程？(y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            local pid=$(lsof -Pi :$port -sTCP:LISTEN -t)
            kill -9 $pid 2>/dev/null
            echo "✅ 已终止进程 $pid"
        else
            echo "ℹ️  请手动更改端口配置"
        fi
    else
        echo "✅ 端口 $port 可用"
    fi
}

 check_port ${FLASK_PORT:-5000}

echo ""
echo "🌐 启动Web服务器..."
echo "访问地址: http://localhost:5000"
echo "按 Ctrl+C 停止服务"
echo ""

# 启动Flask应用
python app.py