# HomeSystem

该项目同时利用本地和云端大模型打造家庭智能化系统。
该系统可以智能化整理分类家庭文档，
自动收集关注的话题相关的论文，新闻等功能。


## 完整安装指南

### 必需的 Python 依赖

#### 一键安装所有依赖
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
    urllib3
```

#### 分类安装
```bash
# 核心 LangChain 组件
pip install langchain-core langchain-community langchain-ollama langchain

# 网络请求和数据处理
pip install requests beautifulsoup4 faiss-cpu pydantic

# 工具库
pip install tqdm loguru urllib3
```

### 必需的外部服务

#### 1. SearxNG 搜索引擎
```bash
# 使用 Docker 运行 SearxNG
docker run -d --name searxng -p 8080:8080 searxng/searxng
```

#### 2. Ollama 本地大模型服务
```bash
# 安装 Ollama
# 参考: https://ollama.ai/

# 拉取嵌入模型
ollama pull bge-m3
```

#### 3. 可选服务（根据需要安装）

**Dify 工作流服务** (可选)
- 用于 AI 工作流功能
- 默认配置: `http://192.168.5.72`

**Paperless-ngx 文档管理** (可选)
- 用于文档管理功能
- 默认配置: `http://192.168.5.54:8000`

### 配置说明

项目中的服务地址配置可能需要根据你的环境调整：

```python
# 在对应文件中修改以下地址
SEARXNG_URL = "http://localhost:8080"        # SearxNG 地址
OLLAMA_URL = "http://localhost:11434"        # Ollama 地址
DIFY_URL = "http://your-dify-instance"       # Dify 服务地址
PAPERLESS_URL = "http://your-paperless"     # Paperless-ngx 地址
```

### 安装步骤

1. **安装 Python 依赖**
   ```bash
   pip install langchain-core langchain-community langchain-ollama langchain requests beautifulsoup4 faiss-cpu pydantic tqdm loguru urllib3
   ```

2. **启动 SearxNG 服务**
   ```bash
   docker run -d --name searxng -p 8080:8080 searxng/searxng
   ```

3. **安装和配置 Ollama**
   ```bash
   # 安装 Ollama 后
   ollama pull bge-m3
   ```

4. **验证安装**
   ```bash
   cd HomeSystem/utility/arxiv
   python arxiv.py
   ```

### SearxNG 设置

需要运行 SearxNG 实例：

```bash
# 使用 Docker 运行 SearxNG
docker run -d --name searxng -p 8080:8080 searxng/searxng
```

### 运行示例

```bash
cd HomeSystem/utility/arxiv
python arxiv.py
```

详细文档请参考 `HomeSystem/utility/arxiv/README.md`