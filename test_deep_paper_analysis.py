#!/usr/bin/env python3
"""
深度论文分析Agent测试脚本

测试完整的论文分析流程，包括：
1. 文件夹解析
2. 图片分析
3. 深度文本分析  
4. 翻译
5. 报告生成
"""

import sys
import os
import asyncio
from pathlib import Path

# 添加项目路径
sys.path.append('/mnt/nfs_share/code/homesystem')

from HomeSystem.graph.deep_paper_analysis_agent import create_deep_paper_analysis_agent
from HomeSystem.graph.parser.paper_folder_parser import create_paper_folder_parser
from loguru import logger


def test_folder_parser():
    """测试文件夹解析器"""
    logger.info("=== 测试文件夹解析器 ===")
    
    test_folder = "/mnt/nfs_share/code/homesystem/data/paper_analyze/2502.13508"
    
    try:
        parser = create_paper_folder_parser(test_folder)
        
        # 验证文件夹
        validation = parser.validate_folder_integrity()
        logger.info(f"文件夹验证: {'通过' if validation['is_valid'] else '失败'}")
        
        if validation["issues"]:
            logger.warning(f"发现问题: {validation['issues']}")
        
        # 解析文件夹
        result = parser.parse_folder()
        logger.info(f"解析结果:")
        logger.info(f"  文本长度: {len(result['paper_text'])} 字符")
        logger.info(f"  图片数量: {len(result['available_images'])}")
        logger.info(f"  公式数量: {result['latex_formulas']['total_count']}")
        logger.info(f"  章节数量: {len(result['content_sections'])}")
        
        # 图片分类
        categorized = parser.categorize_images_by_type()
        for category, images in categorized.items():
            if images:
                logger.info(f"  {category}: {len(images)} 张")
        
        return True
        
    except Exception as e:
        logger.error(f"文件夹解析测试失败: {e}")
        return False


def test_image_analysis_tool():
    """测试图片分析工具"""
    logger.info("=== 测试图片分析工具 ===")
    
    test_folder = "/mnt/nfs_share/code/homesystem/data/paper_analyze/2502.13508"
    
    try:
        from HomeSystem.graph.tool.image_analysis_tool import create_image_analysis_tool
        
        # 创建工具
        tool = create_image_analysis_tool(test_folder, "ollama.Qwen2_5_VL_7B")
        
        # 测试图片验证
        test_image = "imgs/img_in_image_box_253_178_967_593.jpg"
        validation = tool.validate_image(test_image)
        
        logger.info(f"图片验证: {'有效' if validation['is_valid'] else '无效'}")
        
        if validation["is_valid"]:
            # 测试图片分析
            logger.info("开始图片分析测试...")
            result = tool._run(
                analysis_query="Analyze this architecture diagram and describe the main components",
                image_path=test_image
            )
            
            logger.info(f"分析结果长度: {len(result)} 字符")
            logger.info(f"前200字符: {result[:200]}...")
            
            return True
        else:
            logger.error(f"图片验证失败: {validation['error_message']}")
            return False
            
    except Exception as e:
        logger.error(f"图片分析工具测试失败: {e}")
        return False


def test_translation_tool():
    """测试翻译工具"""
    logger.info("=== 测试翻译工具 ===")
    
    try:
        from HomeSystem.graph.tool.paper_translation_tool import create_translation_tool
        
        # 创建翻译工具
        tool = create_translation_tool("ollama.Qwen3_30B", "zh")
        
        # 测试结构化内容翻译
        test_contributions = {
            "contributions": [
                {
                    "id": 1,
                    "title": "End-to-end speech integration",
                    "description": "VLAS integrates speech recognition directly into the robot policy model without external ASR systems."
                }
            ],
            "contribution_count": 1,
            "innovation_level": "high"
        }
        
        logger.info("开始翻译测试...")
        translated = tool.translate_contributions(test_contributions)
        
        logger.info("翻译结果:")
        logger.info(f"  结构键: {list(translated.keys())}")
        
        if "contributions" in translated:
            first_contrib = translated["contributions"][0]
            logger.info(f"  第一个贡献标题: {first_contrib.get('title', 'N/A')}")
        
        return True
        
    except Exception as e:
        logger.error(f"翻译工具测试失败: {e}")
        return False


def test_deep_analysis_agent():
    """测试深度分析Agent"""
    logger.info("=== 测试深度分析Agent ===")
    
    test_folder = "/mnt/nfs_share/code/homesystem/data/paper_analyze/2502.13508"
    
    try:
        # 创建agent（使用较快的配置进行测试）
        agent = create_deep_paper_analysis_agent(
            analysis_model="deepseek.DeepSeek_V3",  # 使用本地模型测试更快
            vision_model="ollama.Qwen2_5_VL_7B",
            translation_model="deepseek.DeepSeek_V3",
            max_analysis_iterations=3,  # 限制迭代次数
            enable_translation=True
        )
        
        logger.info(f"Agent配置: {agent.get_config().__dict__}")
        
        # 执行分析（限制时间）
        logger.info("开始执行分析（这可能需要几分钟）...")
        
        analysis_result = agent.analyze_paper_folder(test_folder, thread_id="test_1")
        
        # 检查结果
        logger.info("分析完成，检查结果:")
        logger.info(f"  分析轮次: {analysis_result.get('analysis_iteration', 0)}")
        logger.info(f"  分析完成: {analysis_result.get('is_analysis_complete', False)}")
        logger.info(f"  翻译完成: {analysis_result.get('is_translation_complete', False)}")
        logger.info(f"  已完成任务: {len(analysis_result.get('completed_tasks', []))}")
        
        if analysis_result.get("analysis_errors"):
            logger.warning(f"分析错误: {analysis_result['analysis_errors']}")
        
        # 检查具体分析结果
        if analysis_result.get("main_contributions"):
            logger.info("✅ 主要贡献分析完成")
        
        if analysis_result.get("methodology_analysis"):
            logger.info("✅ 方法论分析完成")
        
        if analysis_result.get("experimental_results"):
            logger.info("✅ 实验结果分析完成")
        
        if analysis_result.get("translated_contributions"):
            logger.info("✅ 翻译完成")
        
        return analysis_result
        
    except Exception as e:
        logger.error(f"深度分析Agent测试失败: {e}")
        return None


def test_markdown_generation(analysis_result):
    """测试markdown报告生成"""
    logger.info("=== 测试Markdown报告生成 ===")
    
    if not analysis_result:
        logger.error("没有分析结果，跳过markdown测试")
        return False
    
    try:
        # 创建agent
        agent = create_deep_paper_analysis_agent()
        
        # 生成报告
        output_path = "/tmp/test_paper_analysis_report.md"
        report_content = agent.generate_markdown_report(analysis_result, output_path)
        
        logger.info(f"报告生成完成:")
        logger.info(f"  报告长度: {len(report_content)} 字符")
        logger.info(f"  保存路径: {output_path}")
        
        # 显示报告开头
        logger.info("报告开头:")
        lines = report_content.split('\n')
        for i, line in enumerate(lines[:20]):  # 显示前20行
            print(f"{i+1:2d}: {line}")
        
        return True
        
    except Exception as e:
        logger.error(f"Markdown报告生成测试失败: {e}")
        return False


def main():
    """主测试函数"""
    logger.info("开始深度论文分析Agent完整测试")
    
    # 检查测试文件夹是否存在
    test_folder = "/mnt/nfs_share/code/homesystem/data/paper_analyze/2502.13508"
    if not os.path.exists(test_folder):
        logger.error(f"测试文件夹不存在: {test_folder}")
        return
    
    test_results = []
    
    # 1. 测试文件夹解析器
    result1 = test_folder_parser()
    test_results.append(("文件夹解析器", result1))
    
    # 2. 测试图片分析工具
    result2 = test_image_analysis_tool()
    test_results.append(("图片分析工具", result2))
    
    # 3. 测试翻译工具
    result3 = test_translation_tool()
    test_results.append(("翻译工具", result3))
    
    # 4. 测试深度分析Agent（主要测试）
    analysis_result = test_deep_analysis_agent()
    test_results.append(("深度分析Agent", analysis_result is not None))
    
    # 5. 测试markdown报告生成
    result5 = test_markdown_generation(analysis_result)
    test_results.append(("Markdown报告生成", result5))
    
    # 汇总测试结果
    logger.info("\n" + "="*50)
    logger.info("测试结果汇总:")
    
    passed = 0
    total = len(test_results)
    
    for test_name, success in test_results:
        status = "✅ 通过" if success else "❌ 失败"
        logger.info(f"  {test_name}: {status}")
        if success:
            passed += 1
    
    logger.info(f"\n总体结果: {passed}/{total} 个测试通过")
    
    if passed == total:
        logger.info("🎉 所有测试通过！深度论文分析Agent可以正常使用。")
    else:
        logger.warning(f"⚠️  有 {total - passed} 个测试失败，请检查相关组件。")


if __name__ == "__main__":
    main()