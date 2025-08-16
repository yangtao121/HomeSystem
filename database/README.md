# HomeSystem Database Deployment

本目录包含 HomeSystem 项目的完整数据库部署配置，提供 PostgreSQL 和 Redis 数据库服务的持久化部署方案。

## 📁 目录结构

```
database/
├── docker-compose.yml          # Docker Compose 配置文件
├── postgres/
│   └── data/                  # PostgreSQL 数据持久化目录
├── redis/
│   └── data/                  # Redis 数据持久化目录
├── init/                      # 数据库初始化脚本
│   ├── 01-init-extensions.sql # PostgreSQL 扩展初始化
│   └── 02-create-tables.sql   # 数据表创建脚本
├── backup/                    # 数据库备份目录
├── start.sh                   # 启动数据库服务
├── stop.sh                    # 停止数据库服务
├── backup.sh                  # 备份数据库
├── restore.sh                 # 恢复数据库
├── check-tables.sh            # 检查表结构
└── README.md                  # 本文档
```

## 🚀 快速开始

### 1. 启动数据库服务

```bash
cd database
./start.sh
```

### 2. 检查服务状态

```bash
# 查看容器状态
docker compose ps

# 检查服务健康状态
./check-tables.sh
```

### 3. 停止数据库服务

```bash
./stop.sh
```

## 📊 服务配置

### 端口映射

| 服务 | 内部端口 | 外部端口 | 说明 |
|------|---------|---------|------|
| PostgreSQL | 5432 | 15432 | 主数据库 |
| Redis | 6379 | 16379 | 缓存数据库 |
| pgAdmin | 80 | 8080 | PostgreSQL 管理界面 (可选) |
| Redis Commander | 8081 | 8081 | Redis 管理界面 (可选) |

### 数据库连接信息

**PostgreSQL:**
- 主机: `192.168.5.118` (或 `localhost`)
- 端口: `15432`
- 数据库: `homesystem`
- 用户: `homesystem`
- 密码: `homesystem123` (来自 `.env` 文件)

**Redis:**
- 主机: `192.168.5.118` (或 `localhost`)
- 端口: `16379`
- 数据库: `0`

## 🗄️ 数据表结构

### arxiv_papers 表

主要的论文数据表，包含以下核心字段分组：

**基础信息字段:**
- `id` (UUID) - 主键
- `arxiv_id` (VARCHAR) - ArXiv 论文ID (唯一)
- `title` (TEXT) - 论文标题
- `authors` (TEXT) - 作者信息
- `abstract` (TEXT) - 论文摘要
- `categories` (VARCHAR) - 论文分类
- `published_date` (VARCHAR) - 发布日期
- `pdf_url` (TEXT) - PDF 下载链接
- `processing_status` (VARCHAR) - 处理状态 (pending/completed/failed)

**任务追踪字段:**
- `task_name` (VARCHAR) - 任务名称
- `task_id` (VARCHAR) - 任务执行ID

**结构化分析字段:**
- `research_background` (TEXT) - 研究背景
- `research_objectives` (TEXT) - 研究目标
- `methods` (TEXT) - 研究方法
- `key_findings` (TEXT) - 主要发现
- `conclusions` (TEXT) - 结论
- `limitations` (TEXT) - 局限性
- `future_work` (TEXT) - 未来工作
- `keywords` (TEXT) - 关键词

**相关性评分字段:**
- `full_paper_relevance_score` (DECIMAL) - 完整论文相关性评分 (0.000-1.000)
- `full_paper_relevance_justification` (TEXT) - 评分理由

**Dify 知识库追踪字段:**
- `dify_dataset_id` (VARCHAR) - Dify 数据集ID
- `dify_document_id` (VARCHAR) - Dify 文档ID
- `dify_upload_time` (TIMESTAMP) - 上传时间
- `dify_document_name` (VARCHAR) - Dify 中的文档名
- `dify_character_count` (INTEGER) - 字符数
- `dify_segment_count` (INTEGER) - 分片数量
- `dify_metadata` (JSONB) - Dify 相关元数据

**深度分析字段:**
- `deep_analysis_result` (TEXT) - 深度分析结果内容
- `deep_analysis_status` (VARCHAR) - 分析状态
- `deep_analysis_created_at` (TIMESTAMP) - 分析创建时间
- `deep_analysis_updated_at` (TIMESTAMP) - 分析更新时间

**系统字段:**
- `tags` (JSONB) - 标签数组
- `metadata` (JSONB) - 其他元数据
- `created_at` (TIMESTAMP) - 创建时间
- `updated_at` (TIMESTAMP) - 更新时间 (自动触发器更新)

## 🔧 管理工具

### 启动可选管理界面

```bash
# 启动 pgAdmin 和 Redis Commander
docker compose --profile tools up -d

# 访问管理界面
# pgAdmin: http://localhost:8080 (admin@homesystem.local / admin123)
# Redis Commander: http://localhost:8081
```

### 数据库备份

```bash
# 创建完整备份
./backup.sh

# 备份文件保存在 backup/ 目录
# - postgres_backup_YYYYMMDD_HHMMSS.sql
# - redis_backup_YYYYMMDD_HHMMSS.rdb
# - backup_manifest_YYYYMMDD_HHMMSS.txt
```

### 数据库恢复

```bash
# 查看可用备份
./restore.sh

# 恢复 PostgreSQL
./restore.sh postgres postgres_backup_20240127_143022.sql

# 恢复 Redis
./restore.sh redis redis_backup_20240127_143022.rdb

# 同时恢复两个数据库
./restore.sh both 20240127_143022
```

### 表结构验证

```bash
# 检查所有必需的表和索引
./check-tables.sh

# 输出包括:
# - 数据库连接状态
# - 表存在性检查
# - 字段完整性验证
# - 索引状态检查
# - 触发器验证
# - 数据统计信息
```

## 📈 数据持久化

### Docker 命名卷存储

所有数据库数据存储在 Docker 命名卷中，确保容器重启后数据不丢失并避免权限问题：

- **PostgreSQL 数据**: Docker 命名卷 `postgres_data`
- **Redis 数据**: Docker 命名卷 `redis_data`

可以使用以下命令查看命名卷：
```bash
docker volume ls | grep postgres_data
docker volume ls | grep redis_data
```

### 备份策略

- 自动清理：保留最近 7 天的备份文件
- 手动备份：使用 `./backup.sh` 创建即时备份
- 定时备份：可配置 cron 任务定期执行备份

## 🔍 故障排除

### 常见问题

**1. 服务启动失败**
```bash
# 查看容器日志
docker compose logs postgres
docker compose logs redis

# 检查端口占用
netstat -tulpn | grep 15432
netstat -tulpn | grep 16379
```

**2. 数据库连接失败**
```bash
# 检查容器状态
docker compose ps

# 测试数据库连接
docker exec homesystem-postgres pg_isready -U homesystem -d homesystem
docker exec homesystem-redis redis-cli ping
```

**3. 表不存在错误**
```bash
# 运行表结构检查
./check-tables.sh

# 手动创建表结构
docker exec -i homesystem-postgres psql -U homesystem homesystem < init/02-create-tables.sql
```

**4. 权限问题**
```bash
# 检查数据目录权限
ls -la postgres/data/
ls -la redis/data/

# 修复权限（如果需要）
sudo chown -R 999:999 postgres/data/
sudo chown -R 999:999 redis/data/
```

### 性能监控

```sql
-- 在 PostgreSQL 中执行
-- 查看活跃连接
SELECT count(*) FROM pg_stat_activity;

-- 查看表大小
SELECT schemaname,tablename,pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size 
FROM pg_tables WHERE schemaname='public';

-- 查看索引使用情况
SELECT schemaname,tablename,indexname,idx_scan,idx_tup_read,idx_tup_fetch 
FROM pg_stat_user_indexes;
```

## 🌐 环境变量

数据库配置通过父目录的 `.env` 文件管理：

```bash
# Database Configuration
DB_HOST=192.168.5.118
DB_PORT=15432
DB_NAME=homesystem
DB_USER=homesystem
DB_PASSWORD=homesystem123

# Redis Configuration  
REDIS_HOST=192.168.5.118
REDIS_PORT=16379
REDIS_DB=0
```

## 🔄 升级和迁移

### 数据库版本升级

1. 创建完整备份
2. 停止现有服务
3. 更新 Docker 镜像版本
4. 启动新版本服务
5. 验证数据完整性

### 数据迁移

```bash
# 从旧部署迁移到新部署
# 1. 在旧系统创建备份
docker exec old-postgres pg_dump -U homesystem homesystem > migration_backup.sql

# 2. 在新系统恢复数据
cat migration_backup.sql | docker exec -i homesystem-postgres psql -U homesystem homesystem

# 3. 验证迁移结果
./check-tables.sh
```

## 📚 相关文档

- [数据库集成指南](../docs/database-integration-guide.md)
- [主项目文档](../README.md)
- [Web 应用文档](../Web/README.md)

## 🛡️ 安全注意事项

1. **密码管理**: 生产环境中应使用强密码
2. **网络安全**: 限制数据库端口的外部访问
3. **备份加密**: 敏感数据备份应进行加密
4. **访问控制**: 配置适当的用户权限和访问限制
5. **监控告警**: 设置数据库性能和安全监控

## ✅ 验证清单

部署完成后，请验证以下项目：

- [ ] PostgreSQL 服务正常启动 (端口 15432)
- [ ] Redis 服务正常启动 (端口 16379)
- [ ] `arxiv_papers` 表创建成功
- [ ] 所有必需的索引已创建
- [ ] 更新时间戳触发器工作正常
- [ ] 数据持久化目录权限正确
- [ ] 备份脚本执行成功
- [ ] 表结构验证通过
- [ ] Web 应用能正常连接数据库

---

🎉 **恭喜！** HomeSystem 数据库部署已完成。数据库现在已准备好支持所有 HomeSystem 应用程序和服务。