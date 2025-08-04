#!/usr/bin/env python3
"""
智谱AI GLM-4.5系列集成示例
演示如何在HomeSystem中使用智谱AI的GLM-4.5和GLM-4.5-Air模型
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from HomeSystem.graph.llm_factory import get_llm, list_available_llm_models
from langchain_core.messages import HumanMessage


def setup_zhipuai_demo():
    """设置智谱AI演示环境（仅用于演示，不包含真实API Key）"""
    print("=" * 80)
    print("🔑 智谱AI GLM-4.5系列集成示例")
    print("=" * 80)
    
    print("""
📋 使用前准备:
1. 注册智谱AI账号: https://open.bigmodel.cn/
2. 获取API Key
3. 在.env文件中设置: ZHIPUAI_API_KEY=your_api_key_here
4. 可选设置base URL: ZHIPUAI_BASE_URL=https://open.bigmodel.cn/api/paas/v4

💡 模型介绍:
- GLM-4.5: 355B总参数/32B激活，智能体原生设计，全球排名第3
- GLM-4.5-Air: 106B总参数/12B激活，轻量高效版本
- 支持128K上下文长度，混合推理模式
- API定价: 输入0.8元/百万tokens，输出2元/百万tokens
""")


def demo_model_detection():
    """演示模型检测功能"""
    print("\n" + "=" * 60)
    print("🔍 模型检测演示")
    print("=" * 60)
    
    # 模拟设置API Key（实际使用时从.env文件读取）
    os.environ['ZHIPUAI_API_KEY'] = 'demo_key_for_testing'
    
    # 重新初始化工厂以检测新模型
    from HomeSystem.graph.llm_factory import LLMFactory
    factory = LLMFactory()
    
    print(f"\n📊 当前检测到的模型总数: {len(factory.get_available_llm_models())}")
    
    # 查找智谱AI模型
    zhipuai_models = [model for model in factory.get_available_llm_models() if 'zhipuai' in model]
    
    if zhipuai_models:
        print(f"\n✅ 智谱AI模型已检测到 ({len(zhipuai_models)} 个):")
        for model_key in zhipuai_models:
            config = factory.available_llm_models[model_key]
            print(f"  🤖 {model_key}")
            print(f"     显示名称: {config['display_name']}")
            print(f"     参数规模: {config.get('description', 'N/A')}")
            print(f"     上下文长度: {config.get('context_length', 'N/A')} tokens")
            print(f"     支持函数调用: {'是' if config.get('supports_functions', False) else '否'}")
            print()
    else:
        print("\n⚠️  未检测到智谱AI模型，请检查API Key配置")


def demo_model_creation():
    """演示模型创建功能"""
    print("\n" + "=" * 60)
    print("🏗️  模型创建演示")
    print("=" * 60)
    
    models_to_test = ['zhipuai.GLM_4_5', 'zhipuai.GLM_4_5_Air']
    
    for model_key in models_to_test:
        try:
            print(f"\n🔧 创建模型: {model_key}")
            llm = get_llm(model_key, temperature=0.7, max_tokens=1000)
            print(f"  ✅ 创建成功: {type(llm).__name__}")
            print(f"  📝 模型名称: {llm.model_name}")
            print(f"  🌡️  温度设置: {llm.temperature}")
            print(f"  📏 最大tokens: {llm.max_tokens}")
            
            # 注意：实际调用需要有效的API Key
            print(f"  💡 提示: 需要有效的ZHIPUAI_API_KEY才能发送请求")
            
        except Exception as e:
            print(f"  ❌ 创建失败: {e}")


def demo_langgraph_integration():
    """演示LangGraph集成"""
    print("\n" + "=" * 60)
    print("🔗 LangGraph集成演示")
    print("=" * 60)
    
    print("""
🎯 在LangGraph中使用智谱AI的示例代码:

```python
from HomeSystem.graph.base_graph import BaseGraph
from HomeSystem.graph.llm_factory import get_llm
from langchain_core.messages import HumanMessage

class ZhipuAIAgent(BaseGraph):
    def __init__(self):
        super().__init__()
        
        # 智能体任务使用GLM-4.5
        self.agent_llm = get_llm("zhipuai.GLM_4_5", temperature=0.3)
        
        # 快速响应使用GLM-4.5-Air
        self.fast_llm = get_llm("zhipuai.GLM_4_5_Air", temperature=0.1)
    
    def process_agent_task(self, task: str):
        \"\"\"处理复杂的智能体任务\"\"\"
        messages = [
            HumanMessage(content=f"作为智能体，请分析并执行以下任务: {task}")
        ]
        return self.agent_llm.invoke(messages)
    
    def quick_response(self, query: str):
        \"\"\"快速响应简单查询\"\"\"
        messages = [HumanMessage(content=query)]
        return self.fast_llm.invoke(messages)
```

✨ 智谱AI的优势:
- 🎯 智能体原生设计: GLM-4.5专为Agent任务优化
- ⚡ 高效推理: GLM-4.5-Air提供更快的响应速度
- 💰 成本优势: 比主流模型便宜85%，极具竞争力
- 🧠 混合推理: 支持思维模式和非思维模式
- 🔧 工具调用: 原生支持function calling
- 🌍 多语言: 优秀的中英文双语能力
- 📏 长上下文: 支持128K tokens上下文长度
""")


def demo_advanced_features():
    """演示高级功能"""
    print("\n" + "=" * 60)
    print("🚀 高级功能演示")
    print("=" * 60)
    
    print("""
🎨 智谱AI GLM-4.5系列的高级功能:

1. **智能体原生支持**
   - 专为Agent应用优化的架构
   - 自动理解和规划复杂指令
   - 支持多步骤任务执行

2. **混合推理模式**
   - 思维模式: 用于复杂推理和工具使用
   - 非思维模式: 用于实时交互响应
   - 根据任务自动选择最佳模式

3. **工具调用增强**
   - 原生function calling支持
   - 可调用网页浏览、Python解释器等工具
   - 文本转图像等多模态工具集成

4. **性能表现**
   - GLM-4.5: 全球综合评测排名第3 (63.2分)
   - GLM-4.5-Air: 轻量版本仍达到59.8分
   - 支持高达100 tokens/秒的推理速度

5. **企业级特性**
   - MIT开源许可证，无限制商用
   - 支持私有化部署
   - 完整的API文档和SDK支持

📊 基准测试结果:
- 代码能力: 与GPT-4相当
- 数学推理: 超越多数同类模型  
- 长文本理解: 128K上下文无损失
- 多语言能力: 中英文双语优秀
""")


def main():
    """主函数"""
    try:
        setup_zhipuai_demo()
        demo_model_detection()
        demo_model_creation()
        demo_langgraph_integration()
        demo_advanced_features()
        
        print("\n" + "=" * 80)
        print("✅ 智谱AI GLM-4.5系列集成演示完成！")
        print()
        print("🔧 下一步操作:")
        print("1. 在.env文件中设置 ZHIPUAI_API_KEY=your_actual_api_key")
        print("2. 运行 python examples/llm_usage_example.py 测试所有模型")
        print("3. 在你的Graph中使用 get_llm('zhipuai.GLM_4_5') 创建智谱AI模型")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ 运行出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()