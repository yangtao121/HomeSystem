#!/usr/bin/env python
"""
深度论文分析 - 用户提示词功能示例

展示如何使用用户提示词功能让智能体关注论文的特定方面。
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.append(str(Path(__file__).parent.parent))

from HomeSystem.graph.deep_paper_analysis_agent import DeepPaperAnalysisAgent, DeepPaperAnalysisConfig
from loguru import logger


def example_with_config_file():
    """通过配置文件使用用户提示词"""
    logger.info("=== 示例1: 通过配置文件使用用户提示词 ===")
    
    # 使用包含用户提示词的配置文件
    config_path = "HomeSystem/graph/config/deep_paper_analysis_config_example.json"
    
    # 创建智能体
    agent = DeepPaperAnalysisAgent(config_path=config_path)
    
    # 分析论文
    folder_path = "/path/to/paper/folder"  # 替换为实际路径
    result = agent.analyze_paper_folder(folder_path)
    
    return result


def example_with_config_object():
    """通过配置对象使用用户提示词"""
    logger.info("=== 示例2: 通过配置对象使用用户提示词 ===")
    
    # 创建配置对象
    config = DeepPaperAnalysisConfig(
        analysis_model="deepseek.DeepSeek_V3",
        vision_model="ollama.Qwen2_5_VL_7B",
        enable_user_prompt=True,
        user_prompt="""请特别关注以下方面：
1. 算法的时间复杂度和空间复杂度分析
2. 实验结果的统计显著性
3. 代码开源情况和可复现性
4. 与 baseline 方法的公平比较
""",
        user_prompt_position="before_analysis"
    )
    
    # 创建智能体
    agent = DeepPaperAnalysisAgent(config=config)
    
    # 分析论文
    folder_path = "/path/to/paper/folder"  # 替换为实际路径
    result = agent.analyze_paper_folder(folder_path)
    
    return result


def example_with_runtime_override():
    """运行时动态传入用户提示词"""
    logger.info("=== 示例3: 运行时动态传入用户提示词 ===")
    
    # 创建默认配置的智能体
    agent = DeepPaperAnalysisAgent()
    
    # 根据论文类型动态生成提示词
    paper_type = "machine_learning"  # 可以根据实际情况判断
    
    user_prompts = {
        "machine_learning": """机器学习论文分析重点：
1. 模型架构的创新性和合理性
2. 训练策略和优化技巧
3. 消融实验的完整性
4. 在标准 benchmark 上的性能提升
5. 计算资源消耗和训练效率
""",
        "computer_vision": """计算机视觉论文分析重点：
1. 视觉特征提取方法
2. 数据增强策略
3. 在不同数据集上的泛化能力
4. 视觉效果的定性和定量评估
5. 实时性和部署可行性
""",
        "nlp": """自然语言处理论文分析重点：
1. 语言模型架构和预训练策略
2. 下游任务的适配方法
3. 多语言和跨语言能力
4. 模型大小与性能的权衡
5. 偏见和公平性分析
"""
    }
    
    # 选择对应的提示词
    user_prompt = user_prompts.get(paper_type, "请进行全面深入的分析")
    
    # 分析论文，运行时传入用户提示词
    folder_path = "/path/to/paper/folder"  # 替换为实际路径
    result = agent.analyze_paper_folder(
        folder_path, 
        thread_id="1",
        user_prompt=user_prompt  # 运行时传入，会覆盖配置中的默认值
    )
    
    return result


def example_disabled_user_prompt():
    """禁用用户提示词的示例"""
    logger.info("=== 示例4: 禁用用户提示词（默认行为）===")
    
    # 创建配置，明确禁用用户提示词
    config = DeepPaperAnalysisConfig(
        enable_user_prompt=False  # 默认就是 False
    )
    
    # 创建智能体
    agent = DeepPaperAnalysisAgent(config=config)
    
    # 即使传入 user_prompt，也不会使用（因为配置中禁用了）
    folder_path = "/path/to/paper/folder"  # 替换为实际路径
    result = agent.analyze_paper_folder(folder_path)
    
    return result


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="深度论文分析用户提示词示例")
    parser.add_argument("--mode", type=str, default="runtime",
                       choices=["config_file", "config_object", "runtime", "disabled"],
                       help="选择示例模式")
    parser.add_argument("--folder", type=str, required=True,
                       help="论文文件夹路径")
    
    args = parser.parse_args()
    
    # 更新文件夹路径
    folder_path = args.folder
    
    # 根据模式运行不同的示例
    if args.mode == "config_file":
        result = example_with_config_file()
    elif args.mode == "config_object":
        result = example_with_config_object()
    elif args.mode == "runtime":
        result = example_with_runtime_override()
    else:
        result = example_disabled_user_prompt()
    
    # 输出结果
    if "analysis_result" in result:
        logger.info("分析完成！")
        print("\n" + "="*80)
        print("分析结果:")
        print("="*80)
        print(result["analysis_result"])
    else:
        logger.error(f"分析失败: {result.get('error', 'Unknown error')}")