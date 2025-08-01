# SiYuan Notes API Integration Guide

SiYuan Notes（思源笔记）集成指南，提供完整的API使用说明和最佳实践。

## 目录
- [概述](#概述)
- [环境配置](#环境配置)
- [快速开始](#快速开始)
- [核心功能](#核心功能)
- [高级用法](#高级用法)
- [最佳实践](#最佳实践)
- [故障排除](#故障排除)
- [API参考](#api参考)

## 概述

SiYuan Notes 是一款功能强大的本地笔记软件，支持丰富的API接口用于笔记管理和数据操作。HomeSystem集成了SiYuan API，提供统一的Python接口进行笔记管理、搜索、SQL查询等操作。

### 核心特性
- **完整CRUD操作**：创建、读取、更新、删除笔记
- **全文搜索**：支持关键词搜索和高级查询
- **SQL查询**：直接查询SiYuan内部数据库
- **笔记本管理**：管理笔记本结构和状态
- **数据导出**：支持Markdown等格式导出
- **健康监控**：连接状态检查和性能监控

## 环境配置

### 1. SiYuan Notes 设置

在SiYuan笔记软件中启用API访问：

1. 打开 SiYuan Notes 应用
2. 进入 `设置` → `关于` → `API令牌`
3. 生成API令牌并复制保存
4. 确保API服务已启用（默认端口：6806）

### 2. 环境变量配置

在项目根目录的 `.env` 文件中添加：

```env
# SiYuan Notes API 配置
SIYUAN_API_URL=http://192.168.5.54:6806
SIYUAN_API_TOKEN=your_api_token_here
SIYUAN_TIMEOUT=30
SIYUAN_MAX_RETRIES=3
```

**配置说明**：
- `SIYUAN_API_URL`: SiYuan API服务地址
- `SIYUAN_API_TOKEN`: API访问令牌
- `SIYUAN_TIMEOUT`: 请求超时时间（秒）
- `SIYUAN_MAX_RETRIES`: 最大重试次数

### 3. 依赖安装

```bash
pip install requests loguru python-dotenv
```

## 快速开始

### 基础连接测试

```python
from HomeSystem.integrations.siyuan import SiYuanClient

# 从环境变量创建客户端
client = SiYuanClient.from_environment()

# 测试连接
is_connected = await client.test_connection()
print(f"连接状态: {'成功' if is_connected else '失败'}")

# 健康检查
health = await client.health_check()
print(f"健康状态: {health.is_healthy}")
print(f"响应时间: {health.response_time:.2f}ms")
```

### 获取笔记本列表

```python
# 获取所有笔记本
notebooks = await client.get_notebooks()
for notebook in notebooks:
    print(f"笔记本: {notebook['name']} (ID: {notebook['id']})")
    status = "已关闭" if notebook.get('closed', False) else "已打开"
    print(f"状态: {status}")
```

## 核心功能

### 1. 笔记CRUD操作

#### 创建笔记

```python
# 创建新笔记
note = await client.create_note(
    notebook_id="20240101-notebook-id",
    title="我的新笔记",
    content="""# 笔记标题

这是笔记内容，支持Markdown格式。

## 子标题
- 项目1
- 项目2

表格示例：
| 列1 | 列2 |
|-----|-----|
| 值1 | 值2 |
""",
    tags=["标签1", "标签2", "重要"]
)

print(f"笔记已创建: {note.title}")
print(f"笔记ID: {note.note_id}")
```

#### 读取笔记

```python
# 根据ID获取笔记详情
note_detail = await client.get_note("20240101-note-id")
print(f"标题: {note_detail.title}")
print(f"内容长度: {len(note_detail.content or '')} 字符")
print(f"创建时间: {note_detail.created_time}")
print(f"标签: {', '.join(note_detail.tags)}")
```

#### 更新笔记

```python
# 更新笔记内容
updated_note = await client.update_note(
    note_id="20240101-note-id",
    title="更新后的标题",
    content="更新后的内容...",
    tags=["新标签", "更新"]
)
print(f"笔记已更新: {updated_note.title}")
```

#### 删除笔记

```python
# 删除笔记
success = await client.delete_note("20240101-note-id")
print(f"删除结果: {'成功' if success else '失败'}")
```

### 2. 搜索功能

#### 全文搜索

```python
# 搜索笔记
search_result = await client.search_notes(
    query="机器学习",
    limit=10
)

print(f"找到 {search_result.total_count} 条结果")
print(f"搜索耗时: {search_result.search_time:.2f}ms")

# 遍历搜索结果
for result in search_result.results:
    print(f"- {result.get('title', '无标题')}")
    print(f"  ID: {result.get('id', '')}")
    print(f"  摘要: {result.get('content', '')[:100]}...")
```

#### 高级搜索

```python
# 带过滤条件的搜索
search_result = await client.search_notes(
    query="深度学习 AND 神经网络",
    limit=20,
    notebook_ids=["notebook1", "notebook2"],  # 限制搜索范围
    include_content=True  # 包含内容摘要
)
```

### 3. SQL查询

SiYuan支持直接SQL查询内部SQLite数据库：

#### 基础查询

```python
# 查询总文档数
result = await client.execute_sql(
    "SELECT COUNT(*) as count FROM blocks WHERE type = 'd'"
)
doc_count = result[0]['count']
print(f"总文档数: {doc_count}")
```

#### 复杂查询示例

```python
# 按笔记本统计文档数量
sql = """
SELECT 
    box as notebook_id,
    COUNT(*) as note_count,
    MAX(updated) as last_updated
FROM blocks 
WHERE type = 'd' 
GROUP BY box 
ORDER BY note_count DESC 
LIMIT 10
"""

results = await client.execute_sql(sql)
for row in results:
    print(f"笔记本 {row['notebook_id']}: {row['note_count']} 篇笔记")
    print(f"最后更新: {row['last_updated']}")
```

#### 常用SQL查询模板

```python
# 1. 获取最近更新的笔记
recent_notes_sql = """
SELECT id, content, updated
FROM blocks 
WHERE type = 'd' 
ORDER BY updated DESC 
LIMIT 10
"""

# 2. 按标签统计
tag_stats_sql = """
SELECT tag, COUNT(*) as count 
FROM blocks 
WHERE tag IS NOT NULL AND tag != '' 
GROUP BY tag 
ORDER BY count DESC
"""

# 3. 查找包含特定关键词的笔记
keyword_search_sql = """
SELECT id, content 
FROM blocks 
WHERE type = 'd' AND content LIKE '%关键词%'
ORDER BY updated DESC
"""
```

## 高级用法

### 1. 批量操作

```python
# 批量创建笔记
notes_data = [
    {"title": "笔记1", "content": "内容1", "tags": ["批量", "测试"]},
    {"title": "笔记2", "content": "内容2", "tags": ["批量", "演示"]},
    {"title": "笔记3", "content": "内容3", "tags": ["批量", "示例"]},
]

created_notes = []
for note_data in notes_data:
    note = await client.create_note(
        notebook_id="target-notebook-id",
        **note_data
    )
    created_notes.append(note)
    print(f"已创建: {note.title}")

print(f"批量创建完成，共 {len(created_notes)} 篇笔记")
```

### 2. 数据导出

```python
# 导出笔记为Markdown
exported_content = await client.export_note(
    note_id="20240101-note-id",
    format='md'
)

# 保存到文件
with open('/tmp/exported_note.md', 'w', encoding='utf-8') as f:
    f.write(exported_content)
print("笔记已导出到文件")
```

### 3. 数据同步

```python
# 配置同步参数
sync_config = {
    'type': 'incremental',  # 增量同步
    'notebook_ids': [],     # 空表示所有笔记本
    'last_sync_time': None  # None表示获取所有数据
}

# 执行同步
sync_result = await client.sync_data(sync_config)
print(f"同步状态: {sync_result.status.value}")
print(f"处理项目: {sync_result.items_processed}")
print(f"创建项目: {sync_result.items_created}")
print(f"失败项目: {sync_result.items_failed}")
print(f"耗时: {sync_result.duration_seconds:.2f}秒")
```

### 4. 自定义客户端配置

```python
# 使用自定义配置创建客户端
client = SiYuanClient(
    base_url="http://custom-host:6806",
    api_token="custom-token",
    timeout=60,  # 60秒超时
    max_retries=5  # 最大重试5次
)
```

## 最佳实践

### 1. 错误处理

```python
from HomeSystem.integrations.siyuan import SiYuanAPIError

try:
    note = await client.create_note(
        notebook_id="invalid-id",
        title="测试笔记",
        content="测试内容"
    )
except SiYuanAPIError as e:
    print(f"API错误: {e}")
    if e.response:
        print(f"状态码: {e.response.status_code}")
        print(f"响应内容: {e.response.text}")
except Exception as e:
    print(f"其他错误: {e}")
```

### 2. 连接状态监控

```python
import asyncio

async def monitor_connection():
    """定期检查连接状态"""
    while True:
        try:
            health = await client.health_check()
            if not health.is_healthy:
                print(f"⚠️ 连接异常: {health.error_message}")
            else:
                print(f"✅ 连接正常 ({health.response_time:.2f}ms)")
        except Exception as e:
            print(f"❌ 健康检查失败: {e}")
        
        await asyncio.sleep(30)  # 30秒检查一次

# 启动监控
asyncio.create_task(monitor_connection())
```

### 3. 数据缓存策略

```python
import time
from functools import wraps

def cache_result(ttl_seconds=300):
    """简单的结果缓存装饰器"""
    def decorator(func):
        cache = {}
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_key = str(args) + str(kwargs)
            now = time.time()
            
            if cache_key in cache:
                result, timestamp = cache[cache_key]
                if now - timestamp < ttl_seconds:
                    return result
            
            result = await func(*args, **kwargs)
            cache[cache_key] = (result, now)
            return result
        
        return wrapper
    return decorator

# 使用缓存
@cache_result(ttl_seconds=600)  # 10分钟缓存
async def get_notebooks_cached():
    return await client.get_notebooks()
```

### 4. 批量处理优化

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

async def process_notes_parallel(note_ids, max_workers=5):
    """并行处理多个笔记"""
    
    async def process_single_note(note_id):
        try:
            note = await client.get_note(note_id)
            # 处理笔记逻辑
            return {"id": note_id, "status": "success", "title": note.title}
        except Exception as e:
            return {"id": note_id, "status": "error", "error": str(e)}
    
    # 创建任务列表
    tasks = [process_single_note(note_id) for note_id in note_ids]
    
    # 并行执行（限制并发数）
    semaphore = asyncio.Semaphore(max_workers)
    
    async def bounded_task(task):
        async with semaphore:
            return await task
    
    bounded_tasks = [bounded_task(task) for task in tasks]
    results = await asyncio.gather(*bounded_tasks, return_exceptions=True)
    
    return results

# 使用示例
note_ids = ["id1", "id2", "id3", "id4", "id5"]
results = await process_notes_parallel(note_ids)
for result in results:
    if isinstance(result, dict):
        print(f"笔记 {result['id']}: {result['status']}")
```

## 故障排除

### 常见问题及解决方案

#### 1. 连接失败

**问题**: `Connection refused` 或超时错误

**解决方案**:
- 确认SiYuan应用正在运行
- 检查API服务是否启用
- 验证IP地址和端口号
- 检查防火墙设置

```python
# 测试网络连接
import requests

try:
    response = requests.get("http://192.168.5.54:6806/api/system/getConf", timeout=5)
    print(f"网络连接正常: {response.status_code}")
except requests.exceptions.RequestException as e:
    print(f"网络连接失败: {e}")
```

#### 2. 认证失败

**问题**: `401 Unauthorized` 错误

**解决方案**:
- 验证API令牌是否正确
- 重新生成API令牌
- 检查令牌格式（不包含多余空格）

```python
# 验证令牌
import os
token = os.getenv('SIYUAN_API_TOKEN')
print(f"令牌长度: {len(token) if token else 0}")
print(f"令牌格式: {'正确' if token and len(token) == 16 else '错误'}")
```

#### 3. SQL查询错误

**问题**: SQL语法错误或表不存在

**解决方案**:
- 查看SiYuan数据库结构
- 使用正确的表名和字段名
- 测试简单查询后再复杂化

```python
# 查看数据库结构
tables_sql = "SELECT name FROM sqlite_master WHERE type='table'"
tables = await client.execute_sql(tables_sql)
print("可用数据表:")
for table in tables:
    print(f"- {table['name']}")
```

#### 4. 性能问题

**问题**: 响应缓慢或超时

**解决方案**:
- 增加超时时间
- 减少查询结果数量
- 使用分页获取数据
- 优化SQL查询

```python
# 性能优化示例
# 使用分页而不是一次获取所有数据
async def get_all_notes_optimized():
    all_notes = []
    page_size = 50
    page = 1
    
    while True:
        sql = f"""
        SELECT id, content, updated 
        FROM blocks 
        WHERE type = 'd' 
        ORDER BY updated DESC 
        LIMIT {page_size} OFFSET {(page-1) * page_size}
        """
        
        results = await client.execute_sql(sql)
        if not results:
            break
            
        all_notes.extend(results)
        page += 1
        
        # 避免过度占用资源
        await asyncio.sleep(0.1)
    
    return all_notes
```

### 日志调试

启用详细日志帮助诊断问题：

```python
import logging
from loguru import logger

# 配置日志级别
logger.add("siyuan_debug.log", level="DEBUG", rotation="10 MB")

# 在代码中添加调试信息
logger.debug(f"正在连接到: {client.base_url}")
logger.debug(f"使用令牌: {client.api_token[:4]}****")
```

## API参考

### SiYuanClient 类

#### 初始化

```python
SiYuanClient(
    base_url: str,           # API服务地址
    api_token: str,          # API访问令牌
    timeout: int = 30,       # 请求超时时间
    max_retries: int = 3     # 最大重试次数
)
```

#### 类方法

##### `from_environment() -> SiYuanClient`
从环境变量创建客户端实例

##### `test_connection() -> bool`
测试API连接状态

##### `health_check() -> HealthStatus`
获取健康状态信息

#### 笔记本操作

##### `get_notebooks() -> List[Dict]`
获取所有笔记本列表

##### `create_notebook(name: str, **kwargs) -> Dict`
创建新笔记本

#### 笔记操作

##### `create_note(notebook_id: str, title: str, content: str, tags: List[str] = None) -> NoteModel`
创建新笔记

##### `get_note(note_id: str) -> NoteModel`
根据ID获取笔记详情

##### `update_note(note_id: str, **kwargs) -> NoteModel`
更新笔记信息

##### `delete_note(note_id: str) -> bool`
删除指定笔记

#### 搜索操作

##### `search_notes(query: str, limit: int = 20, **kwargs) -> SearchResult`
全文搜索笔记

#### 数据库操作

##### `execute_sql(sql: str) -> List[Dict]`
执行SQL查询

#### 导出操作

##### `export_note(note_id: str, format: str = 'md') -> str`
导出笔记内容

##### `sync_data(config: Dict) -> SyncResult`
执行数据同步

### 数据模型

#### NoteModel
```python
class NoteModel:
    note_id: str          # 笔记ID
    title: str            # 笔记标题
    content: str          # 笔记内容
    tags: List[str]       # 标签列表
    created_time: str     # 创建时间
    updated_time: str     # 更新时间
    notebook_id: str      # 所属笔记本ID
    notebook_name: str    # 所属笔记本名称
```

#### SearchResult
```python
class SearchResult:
    results: List[Dict]   # 搜索结果列表
    total_count: int      # 总结果数量
    search_time: float    # 搜索耗时(ms)
    query: str            # 搜索查询
```

#### HealthStatus
```python
class HealthStatus:
    is_healthy: bool      # 是否健康
    response_time: float  # 响应时间(ms)
    error_message: str    # 错误消息（如有）
```

#### SyncResult
```python
class SyncResult:
    status: SyncStatus         # 同步状态
    items_processed: int       # 处理项目数
    items_created: int         # 创建项目数
    items_updated: int         # 更新项目数
    items_failed: int          # 失败项目数
    duration_seconds: float    # 耗时（秒）
    success_rate: float        # 成功率
    details: Dict             # 详细信息
```

### 异常类型

#### `SiYuanAPIError`
API调用异常的基础异常类

#### `SiYuanConnectionError`
连接相关异常

#### `SiYuanAuthError`
认证相关异常

#### `SiYuanTimeoutError`
超时相关异常

## 示例代码

完整的示例代码可以在以下位置找到：

- **基础示例**: `examples/siyuan_integration_example.py`
- **快速测试**: `examples/siyuan_quick_test.py`
- **配置助手**: `examples/siyuan_config_helper.py`

运行示例：

```bash
# 快速测试
cd /mnt/nfs_share/code/homesystem
python examples/siyuan_quick_test.py

# 完整演示
python examples/siyuan_integration_example.py

# 配置助手
python examples/siyuan_config_helper.py
```

## 参考资源

- **SiYuan Notes 官方网站**: https://b3log.org/siyuan/
- **SiYuan API 文档**: https://docs.siyuan-note.club/zh-Hans/reference/api/kernel/
- **HomeSystem 项目文档**: `docs/`
- **本地服务API信息**: `docs/local-services-api.md`

---

*更新时间: 2024年8月*
*版本: 1.0*