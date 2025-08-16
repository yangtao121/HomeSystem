#!/bin/bash

# HomeSystem Database Restore Script
# 恢复 PostgreSQL 和 Redis 数据

echo "🔄 HomeSystem Database Restore Tool"

# 检查当前目录
if [ ! -f "docker-compose.yml" ]; then
    echo "❌ Error: docker-compose.yml not found in current directory"
    echo "Please run this script from the database directory"
    exit 1
fi

# 检查备份目录
BACKUP_DIR="./backup"
if [ ! -d "$BACKUP_DIR" ]; then
    echo "❌ Error: Backup directory not found: $BACKUP_DIR"
    exit 1
fi

# 显示可用的备份文件
echo "📋 Available backup files:"
echo ""
echo "PostgreSQL backups:"
ls -la "$BACKUP_DIR"/*.sql 2>/dev/null | awk '{print "  " $9 " (" $5 " bytes, " $6 " " $7 " " $8 ")"}'

echo ""
echo "Redis backups:"
ls -la "$BACKUP_DIR"/*.rdb 2>/dev/null | awk '{print "  " $9 " (" $5 " bytes, " $6 " " $7 " " $8 ")"}'

echo ""
echo "📄 Backup manifests:"
ls -la "$BACKUP_DIR"/*.txt 2>/dev/null | awk '{print "  " $9 " (" $5 " bytes, " $6 " " $7 " " $8 ")"}'

# 如果没有参数，显示使用说明
if [ $# -eq 0 ]; then
    echo ""
    echo "Usage:"
    echo "  $0 postgres <backup_file.sql>    # Restore PostgreSQL"
    echo "  $0 redis <backup_file.rdb>       # Restore Redis"
    echo "  $0 both <timestamp>              # Restore both (using timestamp)"
    echo ""
    echo "Examples:"
    echo "  $0 postgres postgres_backup_20240127_143022.sql"
    echo "  $0 redis redis_backup_20240127_143022.rdb"
    echo "  $0 both 20240127_143022"
    exit 0
fi

# 检查服务是否运行
check_services() {
    if [ "$1" = "postgres" ] || [ "$1" = "both" ]; then
        if ! docker ps | grep -q "homesystem-postgres"; then
            echo "❌ Error: PostgreSQL container is not running"
            echo "Please start the database services first: ./start.sh"
            exit 1
        fi
    fi
    
    if [ "$1" = "redis" ] || [ "$1" = "both" ]; then
        if ! docker ps | grep -q "homesystem-redis"; then
            echo "❌ Error: Redis container is not running"
            echo "Please start the database services first: ./start.sh"
            exit 1
        fi
    fi
}

# 恢复 PostgreSQL
restore_postgres() {
    local backup_file="$1"
    
    if [ ! -f "$backup_file" ]; then
        echo "❌ Error: PostgreSQL backup file not found: $backup_file"
        exit 1
    fi
    
    echo "📦 Restoring PostgreSQL from: $backup_file"
    echo "⚠️  This will replace all existing data in the database!"
    
    read -p "Continue? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "❌ Restore cancelled"
        exit 1
    fi
    
    # 清空现有数据库
    echo "🗑️  Dropping existing database..."
    docker exec homesystem-postgres psql -U homesystem -c "DROP DATABASE IF EXISTS homesystem;"
    docker exec homesystem-postgres psql -U homesystem -c "CREATE DATABASE homesystem;"
    
    # 恢复数据
    echo "📥 Restoring data..."
    if cat "$backup_file" | docker exec -i homesystem-postgres psql -U homesystem homesystem; then
        echo "✅ PostgreSQL restore completed successfully!"
    else
        echo "❌ PostgreSQL restore failed"
        exit 1
    fi
}

# 恢复 Redis
restore_redis() {
    local backup_file="$1"
    
    if [ ! -f "$backup_file" ]; then
        echo "❌ Error: Redis backup file not found: $backup_file"
        exit 1
    fi
    
    echo "📦 Restoring Redis from: $backup_file"
    echo "⚠️  This will replace all existing data in Redis!"
    
    read -p "Continue? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "❌ Restore cancelled"
        exit 1
    fi
    
    # 停止 Redis 容器
    echo "🛑 Stopping Redis container..."
    docker stop homesystem-redis
    
    # 复制备份文件
    echo "📥 Copying backup file..."
    if docker cp "$backup_file" homesystem-redis:/data/dump.rdb; then
        echo "✅ Backup file copied successfully"
    else
        echo "❌ Failed to copy backup file"
        exit 1
    fi
    
    # 重启 Redis 容器
    echo "🚀 Starting Redis container..."
    docker start homesystem-redis
    
    # 等待服务启动
    sleep 5
    
    # 验证恢复
    if docker exec homesystem-redis redis-cli ping > /dev/null 2>&1; then
        echo "✅ Redis restore completed successfully!"
    else
        echo "❌ Redis restore failed"
        exit 1
    fi
}

# 处理命令行参数
case "$1" in
    "postgres")
        if [ -z "$2" ]; then
            echo "❌ Error: Please specify PostgreSQL backup file"
            exit 1
        fi
        check_services "postgres"
        restore_postgres "$BACKUP_DIR/$2"
        ;;
    "redis")
        if [ -z "$2" ]; then
            echo "❌ Error: Please specify Redis backup file"
            exit 1
        fi
        check_services "redis"
        restore_redis "$BACKUP_DIR/$2"
        ;;
    "both")
        if [ -z "$2" ]; then
            echo "❌ Error: Please specify timestamp (e.g., 20240127_143022)"
            exit 1
        fi
        timestamp="$2"
        postgres_file="$BACKUP_DIR/postgres_backup_${timestamp}.sql"
        redis_file="$BACKUP_DIR/redis_backup_${timestamp}.rdb"
        
        check_services "both"
        restore_postgres "$postgres_file"
        restore_redis "$redis_file"
        ;;
    *)
        echo "❌ Error: Invalid command: $1"
        echo "Use: $0 {postgres|redis|both} <backup_file_or_timestamp>"
        exit 1
        ;;
esac

echo ""
echo "✅ Database restore operation completed!"