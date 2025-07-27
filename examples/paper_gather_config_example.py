#!/usr/bin/env python3
"""
论文收集任务配置示例

演示如何使用PaperGatherTaskConfig配置论文收集任务
"""

import sys
import os
import asyncio

# 添加项目根目录到路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from HomeSystem.workflow.paper_gather_task.paper_gather_task import PaperGatherTask, PaperGatherTaskConfig
from loguru import logger


async def example_default_config():
    """使用默认配置的示例"""
    logger.info("=== 默认配置示例 ===")
    
    # 使用默认配置
    task = PaperGatherTask()
    
    # 显示配置
    config = task.get_config()
    logger.info(f"默认配置: {config.get_config_dict()}")
    
    # 执行任务
    result = await task.run()
    logger.info(f"任务结果: 找到 {result['total_papers']} 篇论文，其中 {result['relevant_papers']} 篇相关")


async def example_custom_config():
    """使用自定义配置的示例"""
    logger.info("=== 自定义配置示例 ===")
    
    # 创建自定义配置
    custom_config = PaperGatherTaskConfig(
        interval_seconds=1800,  # 30分钟执行一次
        search_query="deep learning computer vision",  # 深度学习计算机视觉
        max_papers_per_search=15,  # 每次搜索最多15篇论文
        user_requirements="寻找深度学习在计算机视觉领域的最新研究，特别是目标检测和图像分割相关的论文",
        llm_model_name="ollama.Qwen3_30B",
        relevance_threshold=0.8,  # 相关性阈值提高到0.8
        max_papers_in_response=30,  # 返回最多30篇论文
        max_relevant_papers_in_response=5,  # 返回最多5篇相关论文
        custom_settings={
            "priority": "high",
            "notification_enabled": True
        }
    )
    
    # 创建任务
    task = PaperGatherTask(config=custom_config)
    
    # 显示配置
    logger.info(f"自定义配置: {custom_config.get_config_dict()}")
    
    # 执行任务
    result = await task.run()
    logger.info(f"任务结果: 找到 {result['total_papers']} 篇论文，其中 {result['relevant_papers']} 篇相关")


async def example_config_update():
    """配置更新示例"""
    logger.info("=== 配置更新示例 ===")
    
    # 创建初始配置
    config = PaperGatherTaskConfig(
        search_query="machine learning",
        max_papers_per_search=10
    )
    
    task = PaperGatherTask(config=config)
    logger.info(f"初始配置: {task.get_config().get_config_dict()}")
    
    # 更新配置
    task.update_config(
        search_query="natural language processing",
        max_papers_per_search=25,
        user_requirements="寻找自然语言处理领域的最新研究，特别是大语言模型相关的论文",
        relevance_threshold=0.9
    )
    
    logger.info(f"更新后配置: {task.get_config().get_config_dict()}")
    
    # 执行任务
    result = await task.run()
    logger.info(f"任务结果: 找到 {result['total_papers']} 篇论文，其中 {result['relevant_papers']} 篇相关")


async def example_different_intervals():
    """不同执行间隔的示例"""
    logger.info("=== 不同执行间隔示例 ===")
    
    configs = [
        ("高频率配置 (10分钟)", PaperGatherTaskConfig(
            interval_seconds=600,  # 10分钟
            search_query="AI safety",
            max_papers_per_search=5
        )),
        ("中频率配置 (1小时)", PaperGatherTaskConfig(
            interval_seconds=3600,  # 1小时
            search_query="machine learning optimization",
            max_papers_per_search=15
        )),
        ("低频率配置 (4小时)", PaperGatherTaskConfig(
            interval_seconds=14400,  # 4小时
            search_query="artificial general intelligence",
            max_papers_per_search=30
        ))
    ]
    
    for name, config in configs:
        logger.info(f"{name}:")
        logger.info(f"  间隔: {config.interval_seconds}秒 ({config.interval_seconds/60}分钟)")
        logger.info(f"  查询: {config.search_query}")
        logger.info(f"  最大论文数: {config.max_papers_per_search}")
        logger.info("---")


async def main():
    """主函数"""
    logger.info("论文收集任务配置示例开始")
    
    try:
        # 运行各种示例
        await example_default_config()
        print("\n" + "="*50 + "\n")
        
        await example_custom_config()
        print("\n" + "="*50 + "\n")
        
        await example_config_update()
        print("\n" + "="*50 + "\n")
        
        await example_different_intervals()
        
    except Exception as e:
        logger.error(f"示例执行失败: {e}")
    
    logger.info("论文收集任务配置示例结束")


if __name__ == "__main__":
    asyncio.run(main())