# HomeSystem LLM集成系统

HomeSystem图形系统的LLM模型管理和集成解决方案。

## ✨ 主要特性

- 🎯 **统一模型管理**: 支持多个中国LLM厂商的模型
- 🔧 **简单易用**: 一行代码获取任意可用模型  
- 📊 **智能检测**: 自动检测API Key可用性
- 🔄 **灵活配置**: YAML配置文件，支持厂商分离
- 🏷️ **清晰命名**: `provider.model`格式，易于区分
- 🚀 **LangGraph兼容**: 所有模型直接支持LangGraph

## 🏢 支持的厂商

### LLM模型厂商
- **DeepSeek**: DeepSeek V3 (671B), DeepSeek R1 (推理专用)
- **硅基流动**: DeepSeek V3/R1, 通义千问QwQ-32B, Qwen2.5-72B  
- **火山引擎**: 豆包1.6系列 (全能版/思考版/极速版)
- **月之暗面**: Kimi K2 (1T参数), Kimi v1 128K
- **Ollama**: 本地部署14B+参数模型

### Embedding模型厂商
- **Ollama**: BGE-M3, Nomic Embed Text, MxBai Embed Large
- **OpenAI**: Text Embedding 3 Large/Small
- **硅基流动**: BGE Large 中文 v1.5

## 📋 模型命名格式

统一采用 `provider.model` 格式:

```
deepseek.DeepSeek_V3          # DeepSeek V3
siliconflow.Qwen2_5_72B       # 硅基流动的通义千问2.5-72B
volcano.Doubao_1_6_Thinking   # 火山引擎豆包1.6思考版
moonshot.Kimi_K2              # 月之暗面Kimi K2
ollama.DeepSeek_R1_32B        # Ollama本地DeepSeek R1
ollama.BGE_M3                 # Ollama本地BGE-M3 Embedding
```

## 🚀 快速开始

### 1. 环境配置

复制并配置环境变量:
```bash
cp .env.example .env
# 编辑.env文件，填入您的API Keys
```

### 2. 基础使用

```python
from HomeSystem.graph.llm_factory import get_llm, get_embedding

# 使用默认模型
llm = get_llm()

# 使用指定模型
deepseek_llm = get_llm("deepseek.DeepSeek_V3")
qwen_llm = get_llm("siliconflow.Qwen2_5_72B")

# 使用embedding模型
embedding = get_embedding("ollama.BGE_M3")
```

### 3. 在Graph中使用

```python
from HomeSystem.graph.base_graph import BaseGraph
from HomeSystem.graph.llm_factory import get_llm, get_embedding

class MyGraph(BaseGraph):
    def __init__(self):
        super().__init__()
        
        # 根据任务需求选择不同模型
        self.main_llm = get_llm("deepseek.DeepSeek_V3")       # 通用对话
        self.code_llm = get_llm("siliconflow.Qwen2_5_72B")   # 代码生成  
        self.reasoning_llm = get_llm("deepseek.DeepSeek_R1") # 推理任务
        self.embedding = get_embedding("ollama.BGE_M3")      # 文本向量化
        
    def process_different_tasks(self, query: str):
        # 动态选择最适合的模型
        if "代码" in query:
            return self.code_llm.invoke([HumanMessage(content=query)])
        elif "推理" in query:
            return self.reasoning_llm.invoke([HumanMessage(content=query)])
        else:
            return self.main_llm.invoke([HumanMessage(content=query)])
```

## 📖 API文档

### 核心函数

#### `get_llm(model_name=None, **kwargs)`
创建LLM实例，返回LangGraph兼容的模型。

**参数:**
- `model_name`: 模型名称，使用`provider.model`格式，None时使用默认模型
- `**kwargs`: 模型参数(temperature, max_tokens等)

**返回:** `BaseChatModel` - 可直接用于LangGraph

#### `get_embedding(model_name=None, **kwargs)`
创建Embedding实例。

**参数:**
- `model_name`: 模型名称，None时使用默认模型  
- `**kwargs`: 模型参数

**返回:** `Embeddings` - Embedding模型实例

#### `list_available_llm_models()`
获取所有可用LLM模型列表。

**返回:** `List[str]` - 可用模型名称列表

#### `list_available_embedding_models()`
获取所有可用Embedding模型列表。

**返回:** `List[str]` - 可用Embedding模型名称列表

### LLMFactory类

```python
from HomeSystem.graph.llm_factory import LLMFactory

factory = LLMFactory()

# 查看可用模型
factory.list_models()

# 创建模型实例
llm = factory.create_llm("deepseek.DeepSeek_V3")
embedding = factory.create_embedding("ollama.BGE_M3")
```

## ⚙️ 配置文件

### llm_providers.yaml结构

```yaml
providers:
  deepseek:
    name: "DeepSeek"
    type: "openai_compatible"
    api_key_env: "DEEPSEEK_API_KEY"
    base_url: "https://api.deepseek.com"
    models:
      - name: "deepseek-chat"
        key: "deepseek.DeepSeek_V3"
        display_name: "DeepSeek V3"
        parameters: "671B总参数/37B激活"
        max_tokens: 131072
        supports_functions: true

defaults:
  llm:
    model_key: "deepseek.DeepSeek_V3"
    temperature: 0.7
    max_tokens: 4000
  embedding:
    model_key: "ollama.BGE_M3"
    dimensions: 1024
```

### .env配置

```bash
# DeepSeek
DEEPSEEK_API_KEY=sk-your-deepseek-key
DEEPSEEK_BASE_URL=https://api.deepseek.com

# 硅基流动
SILICONFLOW_API_KEY=sk-your-siliconflow-key  
SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1

# 火山引擎
VOLCANO_API_KEY=your-volcano-key
VOLCANO_BASE_URL=https://ark.cn-beijing.volces.com/api/v3

# 月之暗面
MOONSHOT_API_KEY=sk-your-moonshot-key
MOONSHOT_BASE_URL=https://api.moonshot.cn/v1

# Ollama本地
OLLAMA_BASE_URL=http://localhost:11434
```

## 💡 使用建议

### 模型选择指南

- **通用对话**: `deepseek.DeepSeek_V3` - 高性能，成本合理
- **深度推理**: `deepseek.DeepSeek_R1` - 专门优化推理能力
- **代码生成**: `siliconflow.Qwen2_5_72B` - 代码能力强
- **长文档**: `volcano.Doubao_1_6` - 256K上下文长度
- **本地部署**: `ollama.DeepSeek_R1_32B` - 无需API Key
- **文本向量**: `ollama.BGE_M3` - 中英文支持好

### 性能优化

1. **API Key管理**: 确保设置正确的环境变量
2. **本地模型**: 使用Ollama减少API调用成本
3. **模型切换**: 根据任务复杂度选择合适模型
4. **参数调优**: 适当调整temperature和max_tokens

## 🔧 故障排除

### 常见问题

**Q: 模型不可用/API Key错误**
```bash
# 检查环境变量
python -c "import os; print('DEEPSEEK_API_KEY:', os.getenv('DEEPSEEK_API_KEY')[:10] + '...' if os.getenv('DEEPSEEK_API_KEY') else 'None')"

# 测试模型可用性
python -c "from HomeSystem.graph.llm_factory import list_available_llm_models; print(list_available_llm_models())"
```

**Q: Ollama模型不可用**
```bash
# 确保Ollama服务运行
curl http://localhost:11434/api/tags

# 安装需要的模型
ollama pull deepseek-r1:32b
ollama pull bge-m3:latest
```

**Q: 版本兼容性问题**
```bash
# 安装正确的依赖版本
pip install langchain-openai langchain-ollama langchain-core
```

## 📝 示例代码

完整示例请查看:
- `examples/llm_usage_example.py` - 基础使用示例
- `examples/workflow_example.py` - 工作流集成示例

## 🤝 贡献

欢迎提交Issue和Pull Request来改进这个系统！

## 📄 许可证

遵循HomeSystem项目许可证。