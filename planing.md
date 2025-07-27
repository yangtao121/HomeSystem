 # 英文论文总结分析Agent实现方案（确定版）

## 核心架构

参考 chat_agent.py 的实现方式，创建专门的英文论文分析agent paper_analysis_agent.py，继承自 BaseGraph，使用 LangGraph 实现迭代工作流。

## 主要功能组件

### 1. 状态管理 (State)

- 论文文本: 输入的OCR处理后的英文论文文本
- 迭代轮次: 当前分析轮次（默认3轮）
- 分析结果: 累积的结构化分析数据
- 改进历史: 记录每轮迭代的优化过程

### 2. 核心工具

- LLM结构化分析工具: 使用精心设计的prompt指导LLM提取结构化信息
- 质量评估工具: LLM自我评估和优化建议
- 学术搜索工具: 集成现有ArXiv搜索（可选，用于补充相关工作）

### 3. 迭代工作流设计

论文文本输入 → LLM结构化分析 → 质量评估 → 优化改进 → 最终输出

### 4. 确定的输出格式

```json
{
  "keywords": ["keyword1", "keyword2", "keyword3"],
  "research_background": "研究背景描述",
  "research_objectives": "研究目标",
  "methods": "研究方法详述",
  "key_findings": "主要研究发现",
  "conclusions": "结论和学术贡献",
  "limitations": "研究局限性",
  "future_work": "未来工作方向"
}
```

## 技术实现要点

### 核心组件

1. PaperAnalysisAgent: 主agent类，继承自BaseGraph
2. PaperAnalysisConfig: 配置类，包含模型选择、迭代次数等设置
3. StructuredAnalysisTool: LLM驱动的结构化分析工具

### 迭代机制

- 第1轮: LLM初步结构化分析，提取所有8个字段
- 第2轮: 质量评估和内容优化，补充不足之处
- 第3轮: 最终检查和格式规范化

### Prompt设计

- 专门设计的分析prompt，明确指导LLM按照8个字段进行分析
- 迭代优化prompt，在后续轮次中针对性改进

### 文件结构

- HomeSystem/graph/paper_analysis_agent.py: 主agent实现
- HomeSystem/graph/tool/paper_analysis_tools.py: 分析工具（主要是prompt工程）
- HomeSystem/graph/config/paper_analysis_config.json: 配置文件
- examples/paper_analysis_example.py: 使用示例

### 实现重点

- 专注于LLM驱动的8字段结构化分析
- 通过迭代优化确保分析质量和完整性
- 简洁的工具集，主要依靠prompt工程
- 标准化的JSON输出格式

这个方案简化了工具复杂度，专注于通过精心设计的prompt和迭代机制，让LLM输出您指定的8个字段的高质量结构化分析结果。     