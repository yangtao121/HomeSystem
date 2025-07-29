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
sys.path.append('/mnt/nfs_share/code/homesystem')
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

echo ""
echo "🌐 启动Web服务器..."
echo "访问地址: http://localhost:5000"
echo "按 Ctrl+C 停止服务"
echo ""

# 启动Flask应用
python app.py