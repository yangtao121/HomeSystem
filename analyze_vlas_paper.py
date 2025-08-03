#!/usr/bin/env python3
"""
VLAS论文深度分析脚本

专门用于分析 /mnt/nfs_share/code/homesystem/data/paper_analyze/2502.13508 论文
生成完整的中文深度分析报告并保存到该文件夹中。
"""

import asyncio
import os
import sys
from pathlib import Path
from loguru import logger

# 添加项目路径
sys.path.append('/mnt/nfs_share/code/homesystem')

from HomeSystem.graph.deep_paper_analysis_agent import DeepPaperAnalysisAgent


def analyze_vlas_paper():
    """分析VLAS论文并生成报告"""
    
    # 论文文件夹路径
    paper_folder = "/mnt/nfs_share/code/homesystem/data/paper_analyze/2502.13508"
    
    # 检查文件夹是否存在
    if not os.path.exists(paper_folder):
        logger.error(f"论文文件夹不存在: {paper_folder}")
        return
    
    logger.info("="*60)
    logger.info("🔬 开始VLAS论文深度分析")
    logger.info(f"📁 分析文件夹: {paper_folder}")
    logger.info("="*60)
    
    try:
        # 创建配置
        from HomeSystem.graph.deep_paper_analysis_agent import DeepPaperAnalysisConfig
        
        config = DeepPaperAnalysisConfig(
            analysis_model="deepseek.DeepSeek_V3",    # 使用云端强大模型进行分析
            vision_model="ollama.Qwen2_5_VL_7B",      # 本地视觉模型
            translation_model="deepseek.DeepSeek_V3", # 使用相同模型进行翻译
            max_analysis_iterations=5,                # 增加分析轮次
            enable_translation=True,
            target_language="zh"
        )
        
        # 创建深度分析Agent
        agent = DeepPaperAnalysisAgent(config=config)
        
        logger.info("✅ 深度分析Agent初始化完成")
        logger.info("🤖 分析模型: DeepSeek V3 (云端)")
        logger.info("👁️ 视觉模型: Qwen2.5-VL-7B (本地)")
        logger.info("🌐 翻译模型: DeepSeek V3 (云端)")
        
        # 开始分析
        logger.info("📊 开始深度分析流程...")
        analysis_result = agent.analyze_paper_folder(paper_folder)
        
        # 生成并保存报告
        output_path = os.path.join(paper_folder, "VLAS_深度分析报告.md")
        logger.info(f"📝 生成中文分析报告...")
        
        report_path = agent.generate_markdown_report(
            analysis_result=analysis_result,
            output_path=output_path
        )
        
        logger.info("="*60)
        logger.info("✅ 分析完成！")
        logger.info(f"📋 分析轮次: {analysis_result.get('analysis_iterations', 0)}")
        logger.info(f"🔄 任务完成数: {analysis_result.get('completed_tasks_count', 0)}")
        logger.info(f"🖼️ 图片分析数: {len(analysis_result.get('analyzed_images', []))}")
        logger.info(f"📄 报告路径: {report_path}")
        logger.info("="*60)
        
        # 显示报告概要
        if os.path.exists(report_path):
            with open(report_path, 'r', encoding='utf-8') as f:
                report_content = f.read()
                
            logger.info(f"📊 报告总长度: {len(report_content)} 字符")
            
            # 显示报告开头
            preview_lines = report_content.split('\n')[:10]
            logger.info("📝 报告预览:")
            for line in preview_lines:
                if line.strip():
                    logger.info(f"   {line}")
        
        # 检查分析结果的完整性
        logger.info("\n🔍 分析完整性检查:")
        
        required_fields = [
            'research_background', 'research_objectives', 'methodology',
            'key_findings', 'conclusions', 'limitations', 'future_work', 'keywords'
        ]
        
        completed_analysis = analysis_result.get('analysis_completed', False)
        translation_completed = analysis_result.get('translation_completed', False)
        
        logger.info(f"   英文分析完成: {'✅' if completed_analysis else '❌'}")
        logger.info(f"   中文翻译完成: {'✅' if translation_completed else '❌'}")
        
        # 检查各个分析字段
        for field in required_fields:
            field_content = analysis_result.get(field)
            has_content = field_content and len(str(field_content).strip()) > 10
            logger.info(f"   {field}: {'✅' if has_content else '❌'}")
        
        if completed_analysis and translation_completed:
            logger.info("🎉 深度分析完全成功！所有字段都已完成分析和翻译。")
        else:
            logger.warning("⚠️ 分析可能不完整，建议重新运行或检查模型配置。")
            
    except Exception as e:
        logger.error(f"❌ 分析过程中发生错误: {str(e)}")
        logger.exception("详细错误信息:")


def main():
    """主函数"""
    logger.info("🚀 启动VLAS论文深度分析脚本")
    
    # 运行分析
    analyze_vlas_paper()


if __name__ == "__main__":
    main()