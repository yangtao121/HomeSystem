# 智谱AI GLM-4.5系列集成指南

本指南介绍如何在HomeSystem中集成和使用智谱AI的GLM-4.5系列模型。

## 模型简介

智谱AI GLM-4.5系列是2025年7月发布的最新智能体原生大模型：

### GLM-4.5
- **参数规模**: 355B总参数/32B激活参数（MoE架构）
- **性能表现**: 全球综合评测排名第3，评分63.2
- **专长领域**: 智能体任务、复杂推理、工具调用
- **上下文长度**: 128K tokens

### GLM-4.5-Air  
- **参数规模**: 106B总参数/12B激活参数（轻量版）
- **性能表现**: 评分59.8，高效版本
- **专长领域**: 快速响应、成本优化场景
- **成本优势**: 比主流模型便宜85%

## 配置步骤

### 1. 获取API Key

1. 访问智谱AI开放平台：https://open.bigmodel.cn/
2. 注册账号并登录
3. 在控制台获取API Key

### 2. 环境变量配置

在项目根目录的`.env`文件中添加：

```bash
# 智谱AI配置
ZHIPUAI_API_KEY=your_zhipuai_api_key_here
ZHIPUAI_BASE_URL=https://open.bigmodel.cn/api/paas/v4  # 可选，使用默认值
```

### 3. 验证配置

运行以下命令验证配置是否正确：

```bash
python -c "
from HomeSystem.graph.llm_factory import LLMFactory
factory = LLMFactory()
factory.list_models()
"
```

如果配置正确，你应该能看到智谱AI模型在列表中：
- `zhipuai.GLM_4_5` (GLM-4.5)  
- `zhipuai.GLM_4_5_Air` (GLM-4.5-Air)

## 使用方法

### 基础用法

```python
from HomeSystem.graph.llm_factory import get_llm
from langchain_core.messages import HumanMessage

# 创建GLM-4.5模型实例
llm = get_llm("zhipuai.GLM_4_5", temperature=0.7)

# 发送消息
response = llm.invoke([HumanMessage(content="你好，请介绍一下你自己")])
print(response.content)
```

### 在LangGraph中使用

```python
from HomeSystem.graph.base_graph import BaseGraph
from HomeSystem.graph.llm_factory import get_llm

class MyAgent(BaseGraph):
    def __init__(self):
        super().__init__()
        
        # 智能体任务使用GLM-4.5
        self.agent_llm = get_llm("zhipuai.GLM_4_5")
        
        # 快速响应使用GLM-4.5-Air
        self.fast_llm = get_llm("zhipuai.GLM_4_5_Air")
```

### 多场景应用

```python
from HomeSystem.graph.llm_factory import get_llm

# 根据不同场景选择模型
def get_appropriate_model(task_type: str):
    if task_type == "agent":
        return get_llm("zhipuai.GLM_4_5")  # 复杂智能体任务
    elif task_type == "fast":
        return get_llm("zhipuai.GLM_4_5_Air")  # 快速响应
    else:
        return get_llm("deepseek.DeepSeek_V3")  # 通用任务
```

## 功能特性

### 混合推理模式
GLM-4.5系列支持两种推理模式：
- **思维模式**: 用于复杂推理和工具使用
- **非思维模式**: 用于实时交互响应

### 工具调用支持
```python
# GLM-4.5原生支持function calling
llm = get_llm("zhipuai.GLM_4_5")
llm_with_tools = llm.bind_tools([your_tools])
```

### 智能体优化
GLM-4.5专为Agent应用设计：
- 自动理解用户意图
- 规划复杂指令执行
- 支持多步骤任务

## 性能优势

1. **全球领先**: GLM-4.5全球排名第3
2. **成本优势**: 比主流模型便宜85%
3. **高效推理**: 支持100 tokens/秒
4. **智能体原生**: 专为Agent场景优化
5. **开源友好**: MIT许可证，无限制商用

## 定价信息

- **输入**: 0.8元/百万tokens
- **输出**: 2元/百万tokens
- **高速推理**: 可达100 tokens/秒

## 示例代码

查看完整示例：
```bash
python examples/zhipuai_integration_example.py
```

## 故障排除

### 常见问题

1. **模型未检测到**
   - 检查`.env`文件中的`ZHIPUAI_API_KEY`是否正确设置
   - 确认API Key有效且有足够余额

2. **导入错误**
   - 确保安装了`langchain-community`包：`pip install langchain-community`

3. **API调用失败**
   - 检查网络连接
   - 验证API Key是否有效
   - 确认账户余额充足

### 调试方法

启用详细日志：
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

检查模型配置：
```python
from HomeSystem.graph.llm_factory import LLMFactory
factory = LLMFactory()
print(factory.available_llm_models['zhipuai.GLM_4_5'])
```

## 更多资源

- [智谱AI官方文档](https://open.bigmodel.cn/dev/api)
- [GLM-4.5开源项目](https://github.com/zai-org/GLM-4.5)
- [LangChain智谱AI集成](https://python.langchain.com/docs/integrations/chat/zhipuai/)

## 更新日志

- **2025-08-03**: 初始版本，支持GLM-4.5和GLM-4.5-Air模型
- 集成ChatZhipuAI客户端，支持智能体原生功能
- 添加混合推理模式和工具调用支持