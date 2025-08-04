"""
公式纠错Agent使用示例

演示如何使用公式纠错智能体修复论文分析文档中的公式错误。
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from HomeSystem.graph.formula_correction_agent import create_formula_correction_agent
from loguru import logger


def test_formula_correction():
    """测试公式纠错功能"""
    
    # 示例文件路径
    analysis_file = "/mnt/nfs_share/code/homesystem/data/paper_analyze/2412.03572/2412.03572_analysis.md"
    ocr_file = "/mnt/nfs_share/code/homesystem/data/paper_analyze/2412.03572/2412.03572_paddleocr.md"
    output_file = "/mnt/nfs_share/code/homesystem/data/paper_analyze/2412.03572/2412.03572_corrected.md"
    
    # 检查文件是否存在
    if not os.path.exists(analysis_file):
        logger.error(f"分析文档不存在: {analysis_file}")
        return False
    
    if not os.path.exists(ocr_file):
        logger.error(f"OCR文档不存在: {ocr_file}")
        return False
    
    try:
        # 1. 创建公式纠错agent
        logger.info("创建公式纠错Agent...")
        agent = create_formula_correction_agent(
            correction_model="deepseek.DeepSeek_V3"
        )
        
        # 2. 执行公式纠错
        logger.info("开始执行公式纠错...")
        result = agent.correct_formulas(
            analysis_file_path=analysis_file,
            ocr_file_path=ocr_file,
            thread_id="test_correction_001"
        )
        
        # 3. 检查结果
        if "error" in result:
            logger.error(f"纠错失败: {result['error']}")
            return False
        
        # 4. 显示纠错统计
        logger.info("=== 纠错结果统计 ===")
        logger.info(f"是否完成: {result.get('is_complete', False)}")
        logger.info(f"当前步骤: {result.get('current_step', 'unknown')}")
        
        extracted_formulas = result.get('extracted_formulas', [])
        logger.info(f"提取公式数量: {len(extracted_formulas)}")
        
        corrections_applied = result.get('corrections_applied', [])
        logger.info(f"应用纠错数量: {len(corrections_applied)}")
        
        if corrections_applied:
            logger.info("应用的纠错操作:")
            for i, correction in enumerate(corrections_applied, 1):
                logger.info(f"  {i}. {correction.get('operation', 'unknown')}: {correction.get('message', 'no message')}")
        
        # 5. 保存纠错后的文档
        if result.get('corrected_content'):
            success = agent.save_corrected_document(result, output_file)
            if success:
                logger.info(f"✅ 纠错文档已保存: {output_file}")
            else:
                logger.error("❌ 纠错文档保存失败")
        else:
            logger.warning("⚠️ 没有生成纠错内容")
        
        return True
        
    except Exception as e:
        logger.error(f"测试过程中发生错误: {e}")
        import traceback
        logger.error(f"错误堆栈: {traceback.format_exc()}")
        return False


def test_individual_tools():
    """测试各个工具的功能"""
    
    logger.info("=== 测试各个工具功能 ===")
    
    # 测试文件路径
    analysis_file = "/mnt/nfs_share/code/homesystem/data/paper_analyze/2412.03572/2412.03572_analysis.md"
    ocr_file = "/mnt/nfs_share/code/homesystem/data/paper_analyze/2412.03572/2412.03572_paddleocr.md"
    
    try:
        # 1. 测试公式提取工具
        logger.info("1. 测试公式提取工具...")
        from HomeSystem.graph.tool.math_formula_extractor import create_math_formula_extractor_tool
        
        formula_tool = create_math_formula_extractor_tool()
        formula_result = formula_tool._run(file_path=analysis_file)
        
        import json
        formula_data = json.loads(formula_result)
        logger.info(f"   提取到 {formula_data.get('total_count', 0)} 个公式")
        
        # 2. 测试OCR文档加载工具
        logger.info("2. 测试OCR文档加载工具...")
        from HomeSystem.graph.tool.ocr_document_loader import create_ocr_document_loader_tool
        
        ocr_tool = create_ocr_document_loader_tool()
        ocr_result = ocr_tool._run(ocr_file_path=ocr_file)
        
        ocr_data = json.loads(ocr_result)
        logger.info(f"   OCR文档加载成功，分块数: {ocr_data.get('total_chunks', 0)}")
        
        # 测试查询功能
        query_result = ocr_tool._run(ocr_file_path=ocr_file, query="Navigation World Model")
        query_data = json.loads(query_result)
        search_results = query_data.get('search_results', [])
        logger.info(f"   查询结果数: {len(search_results)}")
        
        # 3. 测试文本编辑工具
        logger.info("3. 测试文本编辑工具...")
        from HomeSystem.graph.tool.text_editor import create_text_editor_tool
        
        text_editor = create_text_editor_tool()
        
        # 读取一小段测试内容
        with open(analysis_file, 'r', encoding='utf-8') as f:
            content_lines = f.readlines()
            test_content = ''.join(content_lines[:20])  # 只取前20行测试
        
        # 测试获取预览
        from HomeSystem.graph.tool.text_editor import TextEditor
        editor = TextEditor()
        load_result = editor.load_text(test_content)
        logger.info(f"   文本编辑器加载: {load_result.get('message', 'unknown')}")
        
        preview_result = editor.get_preview(1, 5)
        if preview_result.get('success'):
            logger.info("   预览功能正常")
        
        logger.info("✅ 所有工具测试完成")
        return True
        
    except Exception as e:
        logger.error(f"工具测试失败: {e}")
        import traceback
        logger.error(f"错误堆栈: {traceback.format_exc()}")
        return False


def main():
    """主函数"""
    logger.info("🚀 开始公式纠错Agent示例")
    
    # 检查必要文件
    required_files = [
        "/mnt/nfs_share/code/homesystem/data/paper_analyze/2412.03572/2412.03572_analysis.md",
        "/mnt/nfs_share/code/homesystem/data/paper_analyze/2412.03572/2412.03572_paddleocr.md"
    ]
    
    missing_files = [f for f in required_files if not os.path.exists(f)]
    if missing_files:
        logger.error("❌ 缺少必要文件:")
        for file in missing_files:
            logger.error(f"   - {file}")
        return
    
    # 选择测试模式
    import argparse
    parser = argparse.ArgumentParser(description="公式纠错Agent示例")
    parser.add_argument("--mode", choices=["tools", "full"], default="full",
                       help="测试模式: tools=仅测试工具, full=完整纠错流程")
    
    args = parser.parse_args()
    
    if args.mode == "tools":
        logger.info("📋 运行工具测试模式")
        success = test_individual_tools()
    else:
        logger.info("🔧 运行完整纠错流程")
        success = test_formula_correction()
    
    if success:
        logger.info("✅ 测试成功完成")
    else:
        logger.error("❌ 测试失败")


if __name__ == "__main__":
    main()