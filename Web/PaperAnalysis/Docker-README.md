# PaperAnalysis Docker 部署指南

PaperAnalysis 是一个统一的论文收集与分析系统，支持通过 Docker 进行一键部署。

## 快速开始

### 1. 环境准备

确保已安装以下软件：
- Docker (>= 20.10)
- Docker Compose (>= 2.0)

**注意：** 构建过程已经优化，从项目根目录进行构建以正确访问HomeSystem依赖模块。

### 2. 配置环境变量

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑配置文件
vim .env
```

**重要配置项：**
- `DB_HOST`, `DB_PORT`: PostgreSQL 数据库地址
- `REDIS_HOST`, `REDIS_PORT`: Redis 缓存地址  
- `REMOTE_OCR_ENDPOINT`: OCR 服务地址
- `SECRET_KEY`: Flask 密钥（生产环境必须修改）
- LLM API 密钥：根据需要配置各个 LLM 提供商的 API 密钥

### 3. 一键部署

```bash
# 构建并部署（推荐）
./deploy.sh --build

# 或者分步骤
./build.sh      # 构建镜像
./deploy.sh     # 部署服务
```

### 4. 验证部署

```bash
# 查看服务状态
./deploy.sh --status

# 查看日志
./deploy.sh --logs

# 健康检查
curl http://localhost:5002/api/health
```

## 部署架构

### 服务组件

- **PaperAnalysis**: 主应用服务 (端口 5002)
- **Nginx**: 反向代理 (可选，使用 `--profile proxy`)

### 依赖服务

PaperAnalysis 连接到以下外部服务：
- **PostgreSQL**: 论文数据存储
- **Redis**: 缓存和会话存储
- **OCR Service**: 文档OCR处理
- **LLM APIs**: 论文分析和摘要

### 数据持久化

PaperAnalysis 使用以下目录存储持久化数据：

#### 容器内路径
- `/app/data/paper_analyze/` - 论文分析结果（PDF、分析MD、OCR结果、图片等）
- `/app/data/paper_gather/` - 论文收集任务数据（历史记录、配置预设、定时任务）
- `/app/logs/` - 应用日志
- `/app/uploads/` - 用户上传文件
- `/app/static/uploads/` - 静态上传文件

#### 宿主机映射
- `../../data/` ↔ `/app/data/` - 数据目录映射到项目根目录
- `./logs/` ↔ `/app/logs/` - 日志目录
- `./uploads/` ↔ `/app/uploads/` - 上传目录

**注意：** 所有数据目录都已在 `.gitignore` 中配置，不会被版本控制跟踪。

### 网络配置

- 默认网络: `paper-analysis-network`
- 可通过环境变量配置远程服务连接
- 支持本地和分布式部署

## 使用指南

### 基本命令

```bash
# 构建镜像
./build.sh

# 部署服务
./deploy.sh

# 生产环境部署
./deploy.sh -e production

# 启用代理
./deploy.sh -p proxy

# 重新构建并部署
./deploy.sh --build --recreate

# 查看状态
./deploy.sh --status

# 查看日志
./deploy.sh --logs

# 停止服务
./deploy.sh --down
# 或
./stop.sh

# 完全清理
./stop.sh --clean-all
```

### 高级配置

#### 1. 自定义镜像标签

```bash
./build.sh -t v1.0.0
./build.sh -t latest --push
```

#### 2. 使用自定义 Compose 文件

```bash
./deploy.sh -f docker-compose.prod.yml
```

#### 3. 设置代理构建

```bash
./build.sh --build-arg HTTP_PROXY=http://proxy:8080
```

## 配置说明

### 环境变量配置

详细的环境变量说明请参考 `.env.example` 文件。

#### 关键配置项：

**数据库配置**
```env
DB_HOST=192.168.1.100      # PostgreSQL 主机
DB_PORT=15432              # PostgreSQL 端口
DB_USER=homesystem         # 数据库用户
DB_PASSWORD=homesystem123  # 数据库密码
```

**Redis 配置**
```env
REDIS_HOST=192.168.1.100   # Redis 主机
REDIS_PORT=16379           # Redis 端口
```

**OCR 服务配置**
```env
REMOTE_OCR_ENDPOINT=http://192.168.1.101:5001  # OCR 服务地址
```

**LLM API 配置**
```env
DEEPSEEK_API_KEY=sk-your-api-key-here
SILICONFLOW_API_KEY=sk-your-api-key-here
# ... 其他 LLM 提供商配置
```

### Docker Compose 配置

#### 基本部署
```bash
docker-compose up -d
```

#### 启用代理
```bash
docker-compose --profile proxy up -d
```

#### 生产环境
- 修改 `SECRET_KEY`
- 设置合适的资源限制
- 配置日志轮转
- 启用 HTTPS

## 故障排查

### 常见问题

#### 1. 服务无法启动

```bash
# 查看详细日志
docker-compose logs paper-analysis

# 检查容器状态
docker-compose ps

# 检查网络连接
docker-compose exec paper-analysis curl -v http://localhost:5002/api/health
```

#### 2. 数据库连接失败

```bash
# 检查数据库配置
grep DB_ .env

# 测试数据库连接
docker-compose exec paper-analysis pg_isready -h $DB_HOST -p $DB_PORT -U $DB_USER
```

#### 3. Redis 连接失败

```bash
# 检查 Redis 配置
grep REDIS_ .env

# 测试 Redis 连接
docker-compose exec paper-analysis redis-cli -h $REDIS_HOST -p $REDIS_PORT ping
```

#### 4. OCR 服务不可用

```bash
# 检查 OCR 服务配置
grep OCR .env

# 测试 OCR 服务
curl -f $REMOTE_OCR_ENDPOINT/api/health
```

### 日志查看

```bash
# 实时日志
./deploy.sh --logs

# 容器日志
docker-compose logs -f paper-analysis

# 应用日志
docker-compose exec paper-analysis tail -f /app/logs/app.log
```

### 性能监控

#### 资源使用情况
```bash
# 查看容器资源使用
docker stats

# 查看镜像大小
docker images homesystem-paper-analysis
```

#### 健康检查
```bash
# 应用健康状态
curl http://localhost:5002/api/health

# Docker 健康检查
docker-compose ps
```

## 维护操作

### 数据备份

#### 使用自动化备份脚本
```bash
# 基本备份（不包含日志）
./backup-data.sh

# 完整备份（包含日志）
./backup-data.sh --include-logs

# 自定义备份目录
./backup-data.sh -d /backup/homesystem

# 查看备份选项
./backup-data.sh --help
```

#### 手动备份
```bash
# 备份所有数据
tar -czf paperanalysis-backup-$(date +%Y%m%d).tar.gz \
    ../../data/ logs/ uploads/ static/uploads/

# 仅备份关键数据（不含日志）
tar -czf paperanalysis-data-$(date +%Y%m%d).tar.gz \
    ../../data/ uploads/ static/uploads/
```

#### 数据恢复
```bash
# 恢复备份（在项目根目录执行）
cd /path/to/homesystem
tar -xzf /path/to/backup.tar.gz
```

### 更新部署

```bash
# 更新代码后重新部署
git pull
./deploy.sh --build --recreate
```

### 清理操作

```bash
# 停止服务
./stop.sh

# 完全清理（包括数据）
./stop.sh --clean-all

# 清理 Docker 系统
docker system prune -f
```

## 安全考虑

1. **生产环境**：
   - 修改默认的 `SECRET_KEY`
   - 使用强密码
   - 启用 HTTPS
   - 限制网络访问

2. **API 密钥**：
   - 妥善保管 LLM API 密钥
   - 定期轮换密钥
   - 不要在日志中记录密钥

3. **网络安全**：
   - 使用防火墙限制端口访问
   - 配置 VPN 或内网访问
   - 启用访问日志

4. **数据安全**：
   - 定期备份重要数据
   - 确保备份文件的安全存储
   - 监控数据目录的磁盘空间使用
   - 考虑对敏感数据进行加密

## 数据管理最佳实践

1. **定期备份**：
   - 建议每日自动备份数据
   - 保留多个版本的备份文件
   - 测试备份恢复流程

2. **磁盘空间管理**：
   - 监控 `data/paper_analyze/` 目录大小（可能包含大量PDF和图片）
   - 定期清理旧的或不需要的分析结果
   - 考虑使用外部存储或NFS挂载

3. **版本控制**：
   - 所有数据目录已配置在 `.gitignore` 中
   - 不要将数据文件提交到版本控制系统
   - 配置文件和脚本可以版本控制，但要排除包含敏感信息的文件

## 支持

如有问题，请检查：
1. 环境变量配置是否正确
2. 依赖服务是否正常运行
3. 网络连接是否畅通
4. 日志中的错误信息

更多信息请参考项目文档或提交 Issue。