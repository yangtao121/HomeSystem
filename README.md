# HomeSystem

基于 Python 的智能家庭自动化系统，集成本地和云端大模型，提供文档管理、论文收集和工作流自动化功能。

## ✨ 核心功能

- 🤖 **智能文档管理**: 自动整理分类家庭文档
- 📚 **论文自动收集**: 基于ArXiv的智能论文收集和分析
- 🔄 **工作流自动化**: 可定制的任务调度和执行
- 🗄️ **数据库集成**: PostgreSQL + Redis 双数据库架构
- 🌐 **多LLM支持**: 支持本地Ollama和云端模型
- 📊 **结构化分析**: 论文的智能摘要和关键信息提取

## 🚀 快速开始

### 1. 环境准备

#### Python 依赖安装

**一键安装所有依赖**:
```bash
pip install \
    langchain-core \
    langchain-community \
    langchain-ollama \
    langchain \
    requests \
    beautifulsoup4 \
    faiss-cpu \
    pydantic \
    tqdm \
    loguru \
    urllib3 \
    psycopg2-binary \
    redis \
    asyncpg \
    python-dotenv
```

**分类安装**:
```bash
# 核心 LangChain 组件
pip install langchain-core langchain-community langchain-ollama langchain

# 网络请求和数据处理
pip install requests beautifulsoup4 faiss-cpu pydantic

# 数据库组件
pip install psycopg2-binary redis asyncpg python-dotenv

# 工具库
pip install tqdm loguru urllib3
```

### 2. 数据库服务部署

#### 使用 Docker Compose 一键启动

```bash
# 启动数据库服务（PostgreSQL + Redis）
docker compose up -d

# 查看服务状态
docker compose ps

# 查看服务日志
docker compose logs postgres
docker compose logs redis
```

#### 验证数据库连接

```bash
# 检查 PostgreSQL 连接
docker exec homesystem-postgres psql -U homesystem -d homesystem -c "\l"

# 检查 Redis 连接
docker exec homesystem-redis redis-cli ping
```

### 3. 外部服务（按需配置）

#### SearxNG 搜索引擎（推荐）
```bash
# 使用 Docker 运行 SearxNG
docker run -d --name searxng -p 8080:8080 searxng/searxng
```

#### Ollama 本地大模型服务（推荐）
```bash
# 安装 Ollama
# 参考: https://ollama.ai/

# 拉取嵌入模型
ollama pull bge-m3
```

#### 可选服务

**Dify 工作流服务** (可选)
- 用于 AI 工作流功能
- 默认配置: `http://192.168.5.72`

**Paperless-ngx 文档管理** (可选)
- 用于文档管理功能
- 默认配置: `http://192.168.5.54:8000`

### 4. 环境配置

#### 数据库配置（自动检测）

系统会自动检测Docker容器端口，但也可以通过 `.env` 文件自定义：

```bash
# 创建 .env 文件（可选）
cat > .env << EOF
# PostgreSQL 配置
DB_HOST=localhost
DB_PORT=15432
DB_NAME=homesystem
DB_USER=homesystem
DB_PASSWORD=homesystem123

# Redis 配置
REDIS_HOST=localhost
REDIS_PORT=16379
REDIS_DB=0
EOF
```

#### 外部服务配置

项目中的服务地址配置可能需要根据你的环境调整：

```python
# 在对应文件中修改以下地址
SEARXNG_URL = "http://localhost:8080"        # SearxNG 地址
OLLAMA_URL = "http://localhost:11434"        # Ollama 地址
DIFY_URL = "http://your-dify-instance"       # Dify 服务地址
PAPERLESS_URL = "http://your-paperless"     # Paperless-ngx 地址
```

## 📋 完整部署步骤

### 1. 克隆项目
```bash
git clone <repository-url>
cd homesystem
```

### 2. 安装 Python 依赖
```bash
pip install langchain-core langchain-community langchain-ollama langchain requests beautifulsoup4 faiss-cpu pydantic tqdm loguru urllib3 psycopg2-binary redis asyncpg python-dotenv
```

### 3. 启动数据库服务
```bash
# 启动 PostgreSQL + Redis
docker compose up -d
```

### 4. 验证数据库集成
```bash
# 运行集成测试
python test_arxiv_database_integration.py

# 期望输出：所有测试通过 ✅
```

### 5. 启动外部服务（可选）
```bash
# 启动 SearxNG 搜索引擎
docker run -d --name searxng -p 8080:8080 searxng/searxng

# 安装和启动 Ollama
# 参考: https://ollama.ai/
ollama pull bge-m3
```

### 6. 运行示例
```bash
# ArXiv 论文收集示例
cd HomeSystem/utility/arxiv
python arxiv.py

# 数据库操作示例
python examples/simple_arxiv_demo.py
```

## 🏗️ 系统架构

### 核心组件

- **HomeSystem/graph/**: LangGraph智能代理系统
  - 聊天代理和图形可视化
  - 多LLM提供商支持
  - 工具集成（搜索、网页提取）

- **HomeSystem/workflow/**: 任务调度框架
  - 异步任务管理
  - 信号处理和优雅关闭
  - 论文收集工作流

- **HomeSystem/integrations/**: 外部集成
  - **database/**: PostgreSQL + Redis 集成
  - **paperless/**: 文档管理系统集成
  - **dify/**: AI工作流平台集成

- **HomeSystem/utility/**: 工具模块
  - **arxiv/**: ArXiv论文搜索和数据库集成
  - **ollama/**: Ollama模型管理工具

### 数据库架构

```
PostgreSQL (主存储)     Redis (缓存)
├── arxiv_papers       ├── 处理状态缓存
├── 结构化分析字段      ├── 热点数据
├── 索引优化           └── 会话数据
└── 触发器
```

## 🔧 Web管理界面（可选）

启动管理工具：

```bash
# 启动 Web 管理界面
docker compose --profile tools up -d

# 访问地址：
# pgAdmin: http://localhost:8080 (用户名: admin@homesystem.local, 密码: admin123)
# Redis Commander: http://localhost:8081
```

## 🛠️ Ollama模型管理工具

自动查询和更新Ollama模型配置的工具：

```bash
# 列出所有14B+模型
python -m HomeSystem.utility.ollama.cli list

# 比较当前模型与配置文件
python -m HomeSystem.utility.ollama.cli compare

# 更新配置文件（预览模式）
python -m HomeSystem.utility.ollama.cli update --dry-run

# 实际更新配置文件
python -m HomeSystem.utility.ollama.cli update

# 运行交互式示例
python examples/update_ollama_models.py
```

**功能特性**:
- 🔍 自动发现Ollama中的14B+大模型
- 🔄 智能更新`llm_providers.yaml`配置文件
- 💾 自动备份，保持文件其他部分不变
- 🧪 Dry-run模式预览更改
- ⚡ 支持CLI和Python API两种使用方式

## 📚 文档

- **数据库集成**: `docs/database-integration-guide.md` - 完整的数据库使用指南
- **ArXiv模块**: `HomeSystem/utility/arxiv/README.md` - ArXiv功能详细说明
- **Ollama工具**: `HomeSystem/utility/ollama/` - Ollama模型管理工具
- **示例代码**: `examples/` - 各组件使用示例

## 🧪 测试

```bash
# 数据库集成测试
python test_arxiv_database_integration.py

# ArXiv 功能测试
cd HomeSystem/utility/arxiv
python arxiv.py
```