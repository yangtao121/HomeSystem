#!/usr/bin/env python3
"""
LLM Factory 使用示例
演示如何在HomeSystem中使用不同厂商的LLM模型
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from HomeSystem.graph.llm_factory import get_llm, get_embedding, list_available_llm_models
from langchain_core.messages import HumanMessage


def demo_basic_usage():
    """基础使用示例"""
    print("=" * 60)
    print("🚀 LLM Factory 基础使用示例")
    print("=" * 60)
    
    # 1. 查看所有可用模型
    print("\n📋 可用的LLM模型:")
    models = list_available_llm_models()
    for i, model in enumerate(models, 1):
        print(f"  {i:2d}. {model}")
    
    # 2. 使用默认模型
    print(f"\n🔧 使用默认模型:")
    default_llm = get_llm()
    print(f"  默认LLM类型: {type(default_llm).__name__}")
    
    # 3. 使用指定模型
    print(f"\n🎯 使用指定模型:")
    if "deepseek.DeepSeek_V3" in models:
        deepseek_llm = get_llm("deepseek.DeepSeek_V3")
        print(f"  DeepSeek V3: {type(deepseek_llm).__name__}")
    
    if "siliconflow.Qwen2_5_72B" in models:
        qwen_llm = get_llm("siliconflow.Qwen2_5_72B")
        print(f"  通义千问 2.5-72B: {type(qwen_llm).__name__}")
    
    # 4. 使用embedding模型
    print(f"\n🔍 使用Embedding模型:")
    embedding = get_embedding("ollama.BGE_M3")
    print(f"  BGE-M3 Embedding: {type(embedding).__name__}")


def demo_multi_model_conversation():
    """多模型对话示例"""
    print("\n" + "=" * 60)
    print("💬 多模型对话示例")
    print("=" * 60)
    
    # 准备测试消息
    test_message = "你好，请用一句话介绍你自己"
    message = HumanMessage(content=test_message)
    
    # 测试不同模型
    models_to_test = [
        "deepseek.DeepSeek_V3",
        "siliconflow.DeepSeek_V3", 
        "moonshot.Kimi_K2",
        "zhipuai.GLM_4_5",
        "zhipuai.GLM_4_5_Air"
    ]
    
    available_models = list_available_llm_models()
    
    for model_name in models_to_test:
        if model_name in available_models:
            try:
                print(f"\n🤖 {model_name}:")
                llm = get_llm(model_name, temperature=0.7, max_tokens=100)
                print(f"  模型已创建: {type(llm).__name__}")
                print(f"  测试消息: {test_message}")
                print("  注意: 需要有效的API Key才能实际发送请求")
                
            except Exception as e:
                print(f"  ❌ 创建失败: {e}")
        else:
            print(f"\n⚠️  {model_name}: 模型不可用（可能缺少API Key）")


def demo_graph_integration():
    """Graph集成示例"""
    print("\n" + "=" * 60)
    print("🔗 Graph集成示例")
    print("=" * 60)
    
    print("""
在Graph中使用LLM的示例代码:

```python
from HomeSystem.graph.llm_factory import get_llm, get_embedding

class MyGraph(BaseGraph):
    def __init__(self):
        super().__init__()
        
        # 可以在需要时动态获取不同的LLM
        self.main_llm = get_llm("deepseek.DeepSeek_V3")       # 主要推理
        self.code_llm = get_llm("siliconflow.Qwen2_5_72B")   # 代码生成
        self.reasoning_llm = get_llm("deepseek.DeepSeek_R1") # 深度推理
        self.agent_llm = get_llm("zhipuai.GLM_4_5")          # 智能体任务
        self.efficient_llm = get_llm("zhipuai.GLM_4_5_Air")  # 高效处理
        
        # 获取embedding模型
        self.embedding = get_embedding("ollama.BGE_M3")
    
    def process_query(self, query: str):
        # 根据任务类型选择不同的模型
        if "代码" in query or "code" in query.lower():
            return self.code_llm.invoke([HumanMessage(content=query)])
        elif "推理" in query or "reasoning" in query.lower():
            return self.reasoning_llm.invoke([HumanMessage(content=query)])
        elif "智能体" in query or "agent" in query.lower():
            return self.agent_llm.invoke([HumanMessage(content=query)])
        elif "快速" in query or "efficient" in query.lower():
            return self.efficient_llm.invoke([HumanMessage(content=query)])
        else:
            return self.main_llm.invoke([HumanMessage(content=query)])
```

✨ 优势:
  - 同一个graph可以使用多个不同的LLM
  - 根据任务类型动态选择最适合的模型
  - 支持所有厂商: DeepSeek, 硅基流动, 火山引擎, 月之暗面, 智谱AI, Ollama
  - 统一的provider.model命名格式，易于区分和管理
  - 智谱AI GLM-4.5: 专为智能体任务优化，全球排名第3
  - GLM-4.5-Air: 高效轻量版本，成本优势明显
""")


def main():
    """主函数"""
    try:
        demo_basic_usage()
        demo_multi_model_conversation()
        demo_graph_integration()
        
        print("\n" + "=" * 60)
        print("✅ 所有示例运行完成！")
        print("💡 提示: 确保.env文件中配置了相应的API Key")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 运行出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()