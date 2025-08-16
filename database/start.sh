#!/bin/bash

# HomeSystem Database Services Startup Script
# 启动数据库服务 (PostgreSQL + Redis)

echo "🚀 Starting HomeSystem Database Services..."

# 检查当前目录
if [ ! -f "docker-compose.yml" ]; then
    echo "❌ Error: docker-compose.yml not found in current directory"
    echo "Please run this script from the database directory"
    exit 1
fi

# 检查环境变量文件
if [ ! -f "../.env" ]; then
    echo "⚠️  Warning: .env file not found in parent directory"
    echo "Using default database passwords"
fi

# 创建数据目录（如果不存在）
mkdir -p postgres/data redis/data backup

# 启动基础服务
echo "📦 Starting PostgreSQL and Redis..."
docker compose up -d postgres redis

# 等待服务启动
echo "⏳ Waiting for services to start..."
sleep 10

# 检查服务状态
echo "🔍 Checking service status..."
docker compose ps

# 健康检查
echo "🩺 Running health checks..."

# 检查 PostgreSQL
echo -n "PostgreSQL: "
if docker exec homesystem-postgres pg_isready -U homesystem -d homesystem > /dev/null 2>&1; then
    echo "✅ Ready"
else
    echo "❌ Not ready"
fi

# 检查 Redis
echo -n "Redis: "
if docker exec homesystem-redis redis-cli ping > /dev/null 2>&1; then
    echo "✅ Ready"
else
    echo "❌ Not ready"
fi

echo ""
echo "📊 Database Services Information:"
echo "- PostgreSQL: localhost:15432"
echo "- Redis: localhost:16379"
echo ""
echo "📋 To start optional admin tools, run:"
echo "   docker compose --profile tools up -d"
echo ""
echo "🛑 To stop services, run:"
echo "   ./stop.sh"
echo ""
echo "✅ Database services startup complete!"