#!/bin/bash

# HomeSystem Database Backup Script
# 备份 PostgreSQL 和 Redis 数据

# 设置备份目录和时间戳
BACKUP_DIR="./backup"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
POSTGRES_BACKUP="${BACKUP_DIR}/postgres_backup_${TIMESTAMP}.sql"
REDIS_BACKUP="${BACKUP_DIR}/redis_backup_${TIMESTAMP}.rdb"

echo "💾 Starting HomeSystem Database Backup..."

# 检查当前目录
if [ ! -f "docker-compose.yml" ]; then
    echo "❌ Error: docker-compose.yml not found in current directory"
    echo "Please run this script from the database directory"
    exit 1
fi

# 创建备份目录
mkdir -p "$BACKUP_DIR"

# 检查 PostgreSQL 容器是否运行
if ! docker ps | grep -q "homesystem-postgres"; then
    echo "❌ Error: PostgreSQL container is not running"
    echo "Please start the database services first: ./start.sh"
    exit 1
fi

# 检查 Redis 容器是否运行
if ! docker ps | grep -q "homesystem-redis"; then
    echo "❌ Error: Redis container is not running"
    echo "Please start the database services first: ./start.sh"
    exit 1
fi

echo "📦 Backing up PostgreSQL database..."
if docker exec homesystem-postgres pg_dump -U homesystem homesystem > "$POSTGRES_BACKUP"; then
    echo "✅ PostgreSQL backup completed: $POSTGRES_BACKUP"
    POSTGRES_SIZE=$(du -h "$POSTGRES_BACKUP" | cut -f1)
    echo "   Size: $POSTGRES_SIZE"
else
    echo "❌ PostgreSQL backup failed"
    exit 1
fi

echo "📦 Backing up Redis database..."
# 触发 Redis 保存
if docker exec homesystem-redis redis-cli BGSAVE > /dev/null; then
    echo "⏳ Waiting for Redis background save to complete..."
    
    # 等待后台保存完成
    sleep 3
    
    # 等待 BGSAVE 完成的正确方法
    last_save=$(docker exec homesystem-redis redis-cli LASTSAVE)
    while [ "$(docker exec homesystem-redis redis-cli LASTSAVE)" = "$last_save" ]; do
        sleep 1
    done
    
    # 复制 Redis 数据文件
    if docker cp homesystem-redis:/data/dump.rdb "$REDIS_BACKUP"; then
        echo "✅ Redis backup completed: $REDIS_BACKUP"
        REDIS_SIZE=$(du -h "$REDIS_BACKUP" | cut -f1)
        echo "   Size: $REDIS_SIZE"
    else
        echo "❌ Redis backup failed"
        exit 1
    fi
else
    echo "❌ Redis backup command failed"
    exit 1
fi

# 创建备份清单
MANIFEST="${BACKUP_DIR}/backup_manifest_${TIMESTAMP}.txt"
cat > "$MANIFEST" << EOF
HomeSystem Database Backup Manifest
Generated: $(date)
Timestamp: $TIMESTAMP

PostgreSQL Backup:
- File: postgres_backup_${TIMESTAMP}.sql
- Size: $POSTGRES_SIZE
- Database: homesystem
- User: homesystem

Redis Backup:
- File: redis_backup_${TIMESTAMP}.rdb
- Size: $REDIS_SIZE
- Format: RDB dump

Restore Instructions:
1. PostgreSQL: cat postgres_backup_${TIMESTAMP}.sql | docker exec -i homesystem-postgres psql -U homesystem homesystem
2. Redis: docker cp redis_backup_${TIMESTAMP}.rdb homesystem-redis:/data/dump.rdb && docker restart homesystem-redis

EOF

echo "📄 Backup manifest created: $MANIFEST"
echo ""
echo "📊 Backup Summary:"
echo "- PostgreSQL: $POSTGRES_BACKUP ($POSTGRES_SIZE)"
echo "- Redis: $REDIS_BACKUP ($REDIS_SIZE)"
echo "- Manifest: $MANIFEST"
echo ""
echo "✅ Database backup completed successfully!"

# 清理旧备份（保留最近7天）
echo "🧹 Cleaning up old backups (keeping last 7 days)..."
find "$BACKUP_DIR" -name "*.sql" -mtime +7 -delete 2>/dev/null
find "$BACKUP_DIR" -name "*.rdb" -mtime +7 -delete 2>/dev/null
find "$BACKUP_DIR" -name "*.txt" -mtime +7 -delete 2>/dev/null
echo "✅ Cleanup completed!"