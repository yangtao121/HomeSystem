# Home System 数据库集成指南

## 概述

Home System 提供了统一的数据库基础设施，支持 PostgreSQL 和 Redis，为系统各个模块提供数据持久化和缓存服务。本指南详细介绍了数据库集成的设计理念、部署方式和使用方法。

## 架构设计

### 核心组件

```
HomeSystem/
├── integration/
│   └── database/
│       ├── __init__.py           # 包导出
│       ├── connection.py         # 数据库连接管理
│       ├── models.py            # 数据模型基类
│       └── operations.py        # 数据库操作接口
├── utility/
│   └── arxiv/
│       └── database_integration.py  # ArXiv 模块数据库集成
└── docs/
    └── database-integration-guide.md  # 本文档
```

### 设计原则

1. **统一接口**: 提供一致的数据库操作接口
2. **多数据库支持**: 同时支持 PostgreSQL (主存储) 和 Redis (缓存)
3. **异步/同步兼容**: 支持异步和同步两种操作模式
4. **容器化部署**: 使用 Docker 容器化数据库服务
5. **可扩展性**: 易于添加新的数据模型和操作

## 快速开始

### 1. 环境准备

#### 安装依赖
```bash
pip install asyncpg psycopg2-binary redis python-dotenv
```

#### 创建环境配置
创建 `.env` 文件：
```bash
# 数据库配置
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

### 2. 启动数据库服务

#### Docker Compose 配置
创建 `docker-compose.yml`：

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    container_name: homesystem-postgres
    environment:
      POSTGRES_DB: homesystem
      POSTGRES_USER: homesystem
      POSTGRES_PASSWORD: ${DB_PASSWORD:-homesystem123}
      POSTGRES_INITDB_ARGS: "--encoding=UTF-8"
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./sql/init:/docker-entrypoint-initdb.d
    restart: unless-stopped
    networks:
      - homesystem-network

  redis:
    image: redis:7-alpine
    container_name: homesystem-redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    restart: unless-stopped
    networks:
      - homesystem-network

volumes:
  postgres_data:
  redis_data:

networks:
  homesystem-network:
    driver: bridge
```

#### 启动服务
```bash
# 启动数据库容器
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f postgres
docker-compose logs -f redis
```

### 3. 基础使用示例

```python
from HomeSystem.integration.database import DatabaseManager, DatabaseOperations
from HomeSystem.integration.database.models import ArxivPaperModel

# 初始化数据库连接
db_ops = DatabaseOperations()

# 初始化表结构
db_ops.init_tables([ArxivPaperModel()])

# 创建论文记录
paper = ArxivPaperModel(
    arxiv_id="2301.12345",
    title="Advanced Machine Learning Techniques",
    abstract="This paper presents...",
    categories="cs.LG, cs.AI"
)

# 保存到数据库
success = db_ops.create(paper)
print(f"保存结果: {success}")

# 查询论文
existing_paper = db_ops.get_by_field(ArxivPaperModel, 'arxiv_id', "2301.12345")
if existing_paper:
    print(f"找到论文: {existing_paper.title}")
```

## 核心组件详解

### 1. 数据库连接管理 (connection.py)

#### DatabaseManager 类
负责管理 PostgreSQL 和 Redis 连接。

**主要功能**:
- 连接池管理
- 异步/同步连接支持
- 自动重连和错误处理
- 配置管理

**核心方法**:

```python
from HomeSystem.integration.database.connection import db_manager

# PostgreSQL 同步操作
with db_manager.get_postgres_sync() as cursor:
    cursor.execute("SELECT * FROM arxiv_papers LIMIT 10")
    results = cursor.fetchall()

# PostgreSQL 异步操作
async with db_manager.get_postgres_async() as conn:
    results = await conn.fetch("SELECT * FROM arxiv_papers LIMIT 10")

# Redis 操作
redis_client = db_manager.get_redis()
redis_client.set("key", "value")
```

#### 连接配置

支持环境变量和默认值：

| 环境变量 | 默认值 | 说明 |
|---------|--------|------|
| DB_HOST | localhost | PostgreSQL 主机 |
| DB_PORT | 5432 | PostgreSQL 端口 |
| DB_NAME | homesystem | 数据库名 |
| DB_USER | homesystem | 用户名 |
| DB_PASSWORD | homesystem123 | 密码 |
| REDIS_HOST | localhost | Redis 主机 |
| REDIS_PORT | 6379 | Redis 端口 |
| REDIS_DB | 0 | Redis 数据库编号 |

### 2. 数据模型 (models.py)

#### BaseModel 抽象基类

所有数据模型的基类，定义通用接口：

```python
from HomeSystem.integration.database.models import BaseModel

class CustomModel(BaseModel):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.custom_field = kwargs.get('custom_field', '')
    
    @property
    def table_name(self) -> str:
        return 'custom_table'
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'custom_field': self.custom_field,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        return cls(**data)
    
    def get_create_table_sql(self) -> str:
        return """
        CREATE TABLE IF NOT EXISTS custom_table (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            custom_field VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
```

#### ArxivPaperModel 示例

内置的 ArXiv 论文模型：

```python
from HomeSystem.integration.database.models import ArxivPaperModel

# 创建论文实例
paper = ArxivPaperModel(
    arxiv_id="2301.12345",
    title="Machine Learning Research",
    authors="John Doe, Jane Smith",
    abstract="This paper presents novel approaches...",
    categories="cs.LG, cs.AI",
    published_date="2023年01月",
    pdf_url="https://arxiv.org/pdf/2301.12345.pdf",
    processing_status="pending",
    tags=["机器学习", "深度学习"],
    metadata={"conference": "ICML 2023"}
)

# 转换为字典
paper_dict = paper.to_dict()

# 从字典创建实例
paper_copy = ArxivPaperModel.from_dict(paper_dict)
```

### 3. 数据库操作 (operations.py)

#### DatabaseOperations 类

提供标准的 CRUD 操作：

##### 初始化表结构
```python
from HomeSystem.integration.database import DatabaseOperations
from HomeSystem.integration.database.models import ArxivPaperModel

db_ops = DatabaseOperations()
db_ops.init_tables([ArxivPaperModel()])
```

##### 创建记录
```python
paper = ArxivPaperModel(arxiv_id="2301.12345", title="Test Paper")
success = db_ops.create(paper)
```

##### 查询记录
```python
# 根据 ID 查询
paper = db_ops.get_by_id(ArxivPaperModel, "some-uuid")

# 根据字段查询
paper = db_ops.get_by_field(ArxivPaperModel, 'arxiv_id', "2301.12345")

# 列出所有记录
papers = db_ops.list_all(ArxivPaperModel, limit=50, offset=0)

# 检查记录是否存在
exists = db_ops.exists(ArxivPaperModel, 'arxiv_id', "2301.12345")
```

##### 更新记录
```python
updates = {
    'processing_status': 'completed',
    'tags': '["processed", "downloaded"]'
}
success = db_ops.update(paper, updates)
```

##### 删除记录
```python
success = db_ops.delete(paper)
```

#### CacheOperations 类

Redis 缓存操作：

```python
from HomeSystem.integration.database.operations import CacheOperations

cache_ops = CacheOperations()

# 基础键值操作
cache_ops.set("key", "value", expire=3600)  # 1小时过期
value = cache_ops.get("key")
cache_ops.delete("key")
exists = cache_ops.exists("key")

# 集合操作
cache_ops.sadd("processed_papers", "2301.12345", "2301.12346")
is_member = cache_ops.sismember("processed_papers", "2301.12345")
```

## ArXiv 模块集成示例

### ArxivDatabaseManager

专门为 ArXiv 模块设计的数据库管理器：

```python
from HomeSystem.utility.arxiv.database_integration import ArxivDatabaseManager
from HomeSystem.utility.arxiv.arxiv import ArxivTool

# 创建集成数据库的 ArXiv 工具
arxiv_tool = ArxivTool(enable_database=True)

# 搜索时自动去重
results = arxiv_tool.arxivSearch("machine learning", skip_processed=True)
print(f"找到 {results.num_results} 篇新论文")

# 处理论文并自动标记
for paper in results:
    def process_paper(p):
        # 下载 PDF
        p.downloadPdf("./downloads")
        # 添加标签
        p.setTag(["ML", "已处理"])
        return "处理完成"
    
    # 处理并标记为已完成
    result = arxiv_tool.process_paper(paper, process_paper)
    print(f"处理结果: {result}")

# 查看处理状态
db_manager = ArxivDatabaseManager()
unprocessed = db_manager.get_unprocessed_papers(limit=10)
print(f"还有 {len(unprocessed)} 篇论文待处理")
```

### 重复处理预防

系统通过以下机制防止重复处理：

1. **数据库主键约束**: ArXiv ID 设为唯一键
2. **Redis 缓存**: 快速检查已处理状态
3. **状态管理**: 跟踪处理状态（pending, completed, failed）
4. **自动过滤**: 搜索时自动跳过已处理论文

```python
# 检查是否已处理
if db_manager.is_processed("2301.12345"):
    print("论文已处理，跳过")
else:
    # 处理论文
    process_paper(paper)
    # 标记为已处理
    db_manager.mark_processed("2301.12345")
```

## 高级功能

### 1. 异步操作支持

```python
import asyncio
from HomeSystem.integration.database.connection import db_manager

async def async_operations():
    # 初始化异步连接
    await db_manager.init_postgres_async()
    
    # 异步查询
    async with db_manager.get_postgres_async() as conn:
        results = await conn.fetch("SELECT * FROM arxiv_papers LIMIT 10")
        for row in results:
            print(f"论文: {row['title']}")

# 运行异步操作
asyncio.run(async_operations())
```

### 2. 事务处理

```python
from HomeSystem.integration.database.connection import db_manager

def batch_operations():
    with db_manager.get_postgres_sync() as cursor:
        try:
            # 开始事务（自动）
            cursor.execute("INSERT INTO arxiv_papers (arxiv_id, title) VALUES (%s, %s)", 
                          ("2301.001", "Paper 1"))
            cursor.execute("INSERT INTO arxiv_papers (arxiv_id, title) VALUES (%s, %s)", 
                          ("2301.002", "Paper 2"))
            # 事务自动提交
            print("批量操作成功")
        except Exception as e:
            # 事务自动回滚
            print(f"批量操作失败: {e}")
```

### 3. 自定义查询

```python
def get_papers_by_category(category: str, limit: int = 10):
    """根据分类获取论文"""
    with db_manager.get_postgres_sync() as cursor:
        cursor.execute("""
            SELECT * FROM arxiv_papers 
            WHERE categories LIKE %s 
            ORDER BY created_at DESC 
            LIMIT %s
        """, (f"%{category}%", limit))
        
        results = cursor.fetchall()
        return [ArxivPaperModel.from_dict(dict(row)) for row in results]

# 使用示例
ml_papers = get_papers_by_category("cs.LG", limit=20)
print(f"找到 {len(ml_papers)} 篇机器学习论文")
```

### 4. 缓存策略

```python
from HomeSystem.integration.database.operations import CacheOperations

cache_ops = CacheOperations()

def get_paper_with_cache(arxiv_id: str):
    """带缓存的论文查询"""
    cache_key = f"paper:{arxiv_id}"
    
    # 先检查缓存
    cached = cache_ops.get(cache_key)
    if cached:
        import json
        return ArxivPaperModel.from_dict(json.loads(cached))
    
    # 从数据库查询
    paper = db_ops.get_by_field(ArxivPaperModel, 'arxiv_id', arxiv_id)
    if paper:
        # 写入缓存（10分钟过期）
        cache_ops.set(cache_key, json.dumps(paper.to_dict()), expire=600)
    
    return paper
```

## 性能优化

### 1. 连接池配置

```python
# 在 connection.py 中调整连接池参数
self.postgres_pool = await asyncpg.create_pool(
    **self._config['postgres'],
    min_size=5,        # 最小连接数
    max_size=20,       # 最大连接数
    command_timeout=60  # 命令超时时间
)
```

### 2. 索引优化

ArXiv 论文表的推荐索引：

```sql
-- 基础索引（已包含在模型中）
CREATE INDEX IF NOT EXISTS idx_arxiv_papers_arxiv_id ON arxiv_papers(arxiv_id);
CREATE INDEX IF NOT EXISTS idx_arxiv_papers_status ON arxiv_papers(processing_status);
CREATE INDEX IF NOT EXISTS idx_arxiv_papers_categories ON arxiv_papers(categories);

-- 额外的性能索引
CREATE INDEX IF NOT EXISTS idx_arxiv_papers_created_at ON arxiv_papers(created_at);
CREATE INDEX IF NOT EXISTS idx_arxiv_papers_published_date ON arxiv_papers(published_date);

-- 复合索引
CREATE INDEX IF NOT EXISTS idx_arxiv_papers_status_created ON arxiv_papers(processing_status, created_at);
```

### 3. 批量操作

```python
def batch_insert_papers(papers: List[ArxivPaperModel]) -> int:
    """批量插入论文"""
    with db_manager.get_postgres_sync() as cursor:
        data = [
            (p.arxiv_id, p.title, p.abstract, p.categories, p.published_date, 
             p.pdf_url, p.processing_status, json.dumps(p.tags), json.dumps(p.metadata))
            for p in papers
        ]
        
        cursor.executemany("""
            INSERT INTO arxiv_papers 
            (arxiv_id, title, abstract, categories, published_date, pdf_url, 
             processing_status, tags, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (arxiv_id) DO NOTHING
        """, data)
        
        return cursor.rowcount
```

## 监控和维护

### 1. 数据库状态监控

```python
def check_database_health():
    """检查数据库健康状态"""
    try:
        # 检查 PostgreSQL
        with db_manager.get_postgres_sync() as cursor:
            cursor.execute("SELECT 1")
            postgres_ok = True
    except:
        postgres_ok = False
    
    try:
        # 检查 Redis
        redis_client = db_manager.get_redis()
        redis_client.ping()
        redis_ok = True
    except:
        redis_ok = False
    
    return {
        'postgres': postgres_ok,
        'redis': redis_ok,
        'overall': postgres_ok and redis_ok
    }

# 使用示例
health = check_database_health()
print(f"数据库状态: {health}")
```

### 2. 数据库备份

```bash
# PostgreSQL 备份
docker exec homesystem-postgres pg_dump -U homesystem homesystem > backup.sql

# 恢复
docker exec -i homesystem-postgres psql -U homesystem homesystem < backup.sql

# Redis 备份（RDB 文件）
docker exec homesystem-redis redis-cli BGSAVE
```

### 3. 日志分析

```python
from loguru import logger

# 在操作中添加详细日志
logger.add("database.log", rotation="1 day", retention="7 days")

def enhanced_create(model: BaseModel) -> bool:
    start_time = time.time()
    try:
        result = db_ops.create(model)
        duration = time.time() - start_time
        logger.info(f"创建记录成功: {model.table_name}, 耗时: {duration:.3f}s")
        return result
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"创建记录失败: {model.table_name}, 耗时: {duration:.3f}s, 错误: {e}")
        raise
```

## 故障排除

### 常见问题

#### 1. 连接失败
```python
# 检查连接配置
import os
print("数据库配置:")
print(f"DB_HOST: {os.getenv('DB_HOST', 'localhost')}")
print(f"DB_PORT: {os.getenv('DB_PORT', 5432)}")
print(f"DB_NAME: {os.getenv('DB_NAME', 'homesystem')}")

# 测试连接
try:
    with db_manager.get_postgres_sync() as cursor:
        cursor.execute("SELECT version()")
        version = cursor.fetchone()
        print(f"PostgreSQL 版本: {version}")
except Exception as e:
    print(f"连接失败: {e}")
```

#### 2. 表不存在
```python
# 手动初始化表
from HomeSystem.integration.database.models import ArxivPaperModel

db_ops = DatabaseOperations()
db_ops.init_tables([ArxivPaperModel()])
print("表初始化完成")
```

#### 3. Redis 连接问题
```python
# 测试 Redis 连接
try:
    redis_client = db_manager.get_redis()
    info = redis_client.info()
    print(f"Redis 版本: {info['redis_version']}")
    print(f"已用内存: {info['used_memory_human']}")
except Exception as e:
    print(f"Redis 连接失败: {e}")
```

### 调试技巧

#### 启用 SQL 日志
```python
import logging

# 启用 asyncpg 日志
logging.getLogger('asyncpg').setLevel(logging.DEBUG)

# 启用 psycopg2 日志
logging.basicConfig(level=logging.DEBUG)
```

#### 性能分析
```python
import time
from functools import wraps

def profile_db_operation(func):
    """数据库操作性能分析装饰器"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        duration = time.time() - start_time
        logger.info(f"{func.__name__} 执行时间: {duration:.3f}s")
        return result
    return wrapper

# 使用示例
@profile_db_operation
def slow_query():
    with db_manager.get_postgres_sync() as cursor:
        cursor.execute("SELECT * FROM arxiv_papers ORDER BY created_at")
        return cursor.fetchall()
```

## 扩展开发

### 1. 添加新的数据模型

```python
from HomeSystem.integration.database.models import BaseModel

class UserModel(BaseModel):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.username = kwargs.get('username', '')
        self.email = kwargs.get('email', '')
        self.preferences = kwargs.get('preferences', {})
    
    @property
    def table_name(self) -> str:
        return 'users'
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'preferences': json.dumps(self.preferences),
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        if 'preferences' in data and isinstance(data['preferences'], str):
            data['preferences'] = json.loads(data['preferences'])
        return cls(**data)
    
    def get_create_table_sql(self) -> str:
        return """
        CREATE TABLE IF NOT EXISTS users (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            username VARCHAR(100) UNIQUE NOT NULL,
            email VARCHAR(255) UNIQUE NOT NULL,
            preferences JSONB DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
        CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
        """
```

### 2. 自定义操作类

```python
from HomeSystem.integration.database.operations import DatabaseOperations

class CustomOperations(DatabaseOperations):
    def get_papers_by_date_range(self, start_date: str, end_date: str) -> List[ArxivPaperModel]:
        """根据日期范围获取论文"""
        with self.db_manager.get_postgres_sync() as cursor:
            cursor.execute("""
                SELECT * FROM arxiv_papers 
                WHERE created_at BETWEEN %s AND %s
                ORDER BY created_at DESC
            """, (start_date, end_date))
            
            results = cursor.fetchall()
            return [ArxivPaperModel.from_dict(dict(row)) for row in results]
    
    def get_popular_categories(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取热门分类统计"""
        with self.db_manager.get_postgres_sync() as cursor:
            cursor.execute("""
                SELECT categories, COUNT(*) as count
                FROM arxiv_papers 
                WHERE categories IS NOT NULL
                GROUP BY categories
                ORDER BY count DESC
                LIMIT %s
            """, (limit,))
            
            return [{'category': row['categories'], 'count': row['count']} 
                   for row in cursor.fetchall()]
```

## 最佳实践

### 1. 错误处理
```python
def safe_database_operation(operation_func):
    """安全的数据库操作包装器"""
    try:
        return operation_func()
    except Exception as e:
        logger.error(f"数据库操作失败: {e}")
        # 根据错误类型决定是否重试
        if "connection" in str(e).lower():
            # 连接错误，尝试重连
            db_manager.postgres_sync_conn = None
            return operation_func()  # 重试一次
        raise
```

### 2. 资源管理
```python
def cleanup_old_records():
    """清理旧记录"""
    with db_manager.get_postgres_sync() as cursor:
        # 删除30天前的已处理记录
        cursor.execute("""
            DELETE FROM arxiv_papers 
            WHERE processing_status = 'completed' 
            AND created_at < NOW() - INTERVAL '30 days'
        """)
        
        deleted_count = cursor.rowcount
        logger.info(f"清理了 {deleted_count} 条旧记录")
        return deleted_count
```

### 3. 配置管理
```python
# config.py
import os
from typing import Dict, Any

class DatabaseConfig:
    @staticmethod
    def get_postgres_config() -> Dict[str, Any]:
        return {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': int(os.getenv('DB_PORT', 5432)),
            'database': os.getenv('DB_NAME', 'homesystem'),
            'user': os.getenv('DB_USER', 'homesystem'),
            'password': os.getenv('DB_PASSWORD', 'homesystem123'),
        }
    
    @staticmethod
    def get_redis_config() -> Dict[str, Any]:
        return {
            'host': os.getenv('REDIS_HOST', 'localhost'),
            'port': int(os.getenv('REDIS_PORT', 6379)),
            'db': int(os.getenv('REDIS_DB', 0)),
        }
```

## 总结

Home System 数据库集成提供了：

1. **统一的数据访问层**: 简化数据库操作
2. **多数据库支持**: PostgreSQL + Redis 组合
3. **容器化部署**: 易于管理和扩展
4. **性能优化**: 连接池、缓存、索引
5. **可扩展架构**: 易于添加新功能

通过这套系统，可以有效解决重复处理问题，提高系统整体性能和可维护性。

## 参考资源

- [PostgreSQL 官方文档](https://www.postgresql.org/docs/)
- [Redis 官方文档](https://redis.io/documentation)
- [asyncpg 文档](https://magicstack.github.io/asyncpg/)
- [psycopg2 文档](https://www.psycopg.org/docs/)
- [Docker Compose 文档](https://docs.docker.com/compose/)