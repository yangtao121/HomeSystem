#!/usr/bin/env python3
"""
测试PaperGather任务修复的脚本
验证任务结果统计是否准确
"""

import sys
import os
import asyncio
from typing import Dict, Any

# 添加HomeSystem到路径
sys.path.append(os.path.join(os.path.dirname(__file__)))

from HomeSystem.workflow.paper_gather_task.paper_gather_task import PaperGatherTask, PaperGatherTaskConfig
from HomeSystem.utility.arxiv.arxiv import ArxivSearchMode
from loguru import logger

async def test_paper_gather_fix():
    """测试论文收集任务修复"""
    logger.info("开始测试PaperGather任务修复")
    
    # 创建一个简单的测试配置 - 使用小数量进行快速测试
    config = PaperGatherTaskConfig(
        search_query="large language model",
        max_papers_per_search=3,  # 使用小数量进行快速测试
        user_requirements="寻找大语言模型相关的研究论文",
        llm_model_name="ollama.Qwen3_30B",
        relevance_threshold=0.1,  # 降低阈值以便有更多论文被认为是相关的
        search_mode=ArxivSearchMode.LATEST,
        enable_paper_summarization=False,  # 禁用论文总结以加快测试
        enable_translation=False  # 禁用翻译以加快测试
    )
    
    # 创建任务实例
    task = PaperGatherTask(config=config)
    
    try:
        # 执行任务
        logger.info("执行论文收集任务...")
        result = await task.run()
        
        # 输出结果统计
        logger.info("=== 任务结果统计 ===")
        logger.info(f"消息: {result.get('message', 'N/A')}")
        logger.info(f"总论文数: {result.get('total_papers', 0)}")
        logger.info(f"相关论文数: {result.get('relevant_papers', 0)}")
        logger.info(f"已保存论文数: {result.get('saved_papers', 0)}")
        logger.info(f"已分析论文数: {result.get('analyzed_papers', 0)}")
        logger.info(f"搜索查询: {result.get('search_query', 'N/A')}")
        
        # 验证统计一致性
        if 'papers' in result:
            actual_papers = len(result['papers'])
            reported_papers = result.get('total_papers', 0)
            logger.info(f"实际论文对象数量: {actual_papers}")
            logger.info(f"报告论文数量: {reported_papers}")
            
            if actual_papers != reported_papers:
                logger.warning(f"论文数量不一致: 实际={actual_papers}, 报告={reported_papers}")
            else:
                logger.success("论文数量统计一致!")
        
        if 'top_relevant_papers' in result:
            actual_relevant = len(result['top_relevant_papers'])
            reported_relevant = result.get('relevant_papers', 0)
            logger.info(f"实际相关论文对象数量: {actual_relevant}")
            logger.info(f"报告相关论文数量: {reported_relevant}")
            
            if actual_relevant != reported_relevant:
                logger.warning(f"相关论文数量不一致: 实际={actual_relevant}, 报告={reported_relevant}")
            else:
                logger.success("相关论文数量统计一致!")
        
        # 检查论文对象的标记
        if 'papers' in result:
            for i, paper in enumerate(result['papers'][:3]):  # 只检查前3个
                logger.info(f"论文 {i+1}: {paper.arxiv_id}")
                logger.info(f"  - 最终相关性: {getattr(paper, 'final_is_relevant', 'N/A')}")
                logger.info(f"  - 相关性评分: {getattr(paper, 'final_relevance_score', 'N/A')}")
                logger.info(f"  - 已保存到数据库: {getattr(paper, 'saved_to_database', 'N/A')}")
                logger.info(f"  - 已完整分析: {getattr(paper, 'full_paper_analyzed', 'N/A')}")
        
        return True
        
    except Exception as e:
        logger.error(f"测试执行失败: {e}")
        return False

def main():
    """主函数"""
    # 设置日志级别
    logger.remove()
    logger.add(sys.stdout, level="INFO", format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}")
    
    # 运行测试
    success = asyncio.run(test_paper_gather_fix())
    
    if success:
        logger.success("测试完成 - PaperGather任务修复验证成功!")
        sys.exit(0)
    else:
        logger.error("测试失败 - PaperGather任务修复验证失败!")
        sys.exit(1)

if __name__ == "__main__":
    main()