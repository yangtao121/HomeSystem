# Home System 数据库集成快速设置指南

本指南帮助您快速设置和使用 Home System 的数据库集成功能。

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 设置环境变量

复制环境变量模板：
```bash
cp .env.example .env
```

编辑 `.env` 文件，根据需要修改配置：
```bash
# PostgreSQL 配置
DB_HOST=localhost
DB_PORT=5432
DB_NAME=homesystem
DB_USER=homesystem
DB_PASSWORD=homesystem123

# Redis 配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
```

### 3. 启动数据库服务

使用 Docker Compose 启动数据库服务：
```bash
docker-compose up -d
```

查看服务状态：
```bash
docker-compose ps
```

### 4. 验证连接

运行快速测试：
```bash
python quick_test.py
```

如果看到"🎉 数据库连接测试通过！"，说明配置成功。

### 5. 运行完整测试

```bash
python test_database_integration.py
```

### 6. 查看使用示例

```bash
python examples/database_usage_example.py
```

## 📖 基础使用

### 数据库操作

```python
from HomeSystem.integrations.database import DatabaseOperations, ArxivPaperModel

# 创建数据库操作实例
db_ops = DatabaseOperations()

# 创建论文记录
paper = ArxivPaperModel(
    arxiv_id="2301.12345",
    title="示例论文",
    abstract="论文摘要",
    categories="cs.LG"
)

# 保存到数据库
success = db_ops.create(paper)
```

### ArXiv 集成

```python
from HomeSystem.utility.arxiv import EnhancedArxivTool

# 创建增强版工具（支持数据库）
arxiv_tool = EnhancedArxivTool(enable_database=True)

# 搜索并自动保存到数据库
results = arxiv_tool.arxivSearch("machine learning", num_results=10)

# 跳过已处理的论文
results = arxiv_tool.arxivSearch("deep learning", skip_processed=True)
```

### 缓存操作

```python
from HomeSystem.integrations.database import CacheOperations

cache_ops = CacheOperations()

# 基础缓存
cache_ops.set("key", "value", expire=3600)
value = cache_ops.get("key")

# 集合操作
cache_ops.sadd("processed_papers", "paper_id")
is_processed = cache_ops.sismember("processed_papers", "paper_id")
```

## 🔧 管理工具

### Web 管理界面（可选）

启动 Web 管理工具：
```bash
docker-compose --profile tools up -d
```

- **pgAdmin**: http://localhost:8080
  - 邮箱: admin@homesystem.local
  - 密码: admin123

- **Redis Commander**: http://localhost:8081

### 数据库备份

```bash
# PostgreSQL 备份
docker exec homesystem-postgres pg_dump -U homesystem homesystem > backup.sql

# Redis 备份
docker exec homesystem-redis redis-cli BGSAVE
```

## 🛠️ 故障排除

### 连接失败

1. **检查容器状态**
   ```bash
   docker-compose ps
   ```

2. **查看日志**
   ```bash
   docker-compose logs postgres
   docker-compose logs redis
   ```

3. **重启服务**
   ```bash
   docker-compose restart
   ```

### 端口冲突

如果端口被占用，修改 `docker-compose.yml` 中的端口映射：
```yaml
ports:
  - "15432:5432"  # 使用不同的外部端口
```

### 权限问题

确保 Docker 有权限访问数据卷：
```bash
sudo chown -R $USER:$USER ./data
```

## 📚 文档链接

- [完整数据库集成指南](docs/database-integration-guide.md)
- [ArXiv API 文档](docs/arxiv-api-documentation.md)
- [项目结构说明](docs/project-structure.md)

## 🆘 获取帮助

如果遇到问题：

1. 查看完整文档：`docs/database-integration-guide.md`
2. 运行诊断脚本：`python test_database_integration.py`
3. 检查 Docker 日志：`docker-compose logs`

---

🎉 **恭喜！** 您已成功设置 Home System 数据库集成。现在可以开始使用增强的 ArXiv 论文管理功能了！