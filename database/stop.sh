#!/bin/bash

# HomeSystem Database Services Shutdown Script
# 停止数据库服务 (PostgreSQL + Redis)

echo "🛑 Stopping HomeSystem Database Services..."

# 检查当前目录
if [ ! -f "docker-compose.yml" ]; then
    echo "❌ Error: docker-compose.yml not found in current directory"
    echo "Please run this script from the database directory"
    exit 1
fi

# 显示当前运行的服务
echo "📋 Current running services:"
docker compose ps

# 停止所有服务（包括可选的管理工具）
echo "🔄 Stopping all services..."
docker compose --profile tools down

# 检查是否还有相关容器在运行
echo "🔍 Checking for remaining containers..."
remaining=$(docker ps -q --filter "name=homesystem-")
if [ -n "$remaining" ]; then
    echo "⚠️  Found remaining containers, stopping them..."
    docker stop $remaining
else
    echo "✅ All containers stopped successfully"
fi

echo ""
echo "📊 Service Status:"
docker compose ps

echo ""
echo "🗂️  Data Preservation:"
echo "- PostgreSQL data: Docker named volume 'postgres_data'"
echo "- Redis data: Docker named volume 'redis_data'"
echo "- Both volumes are preserved for next startup"

echo ""
echo "🚀 To restart services, run:"
echo "   ./start.sh"
echo ""
echo "✅ Database services shutdown complete!"