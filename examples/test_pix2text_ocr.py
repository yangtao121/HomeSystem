#!/usr/bin/env python3
"""
测试pix2text OCR功能

使用arxiv论文测试新的OCR引擎
"""

import sys
import os
import asyncio

# 添加项目根目录到路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from HomeSystem.utility.arxiv.arxiv import ArxivTool
from loguru import logger


async def test_pix2text_ocr():
    """测试pix2text OCR功能"""
    logger.info("=== 测试pix2text OCR功能 ===")
    
    try:
        # 创建ArXiv工具
        arxiv_tool = ArxivTool()
        
        # 搜索一篇论文
        logger.info("搜索论文...")
        results = arxiv_tool.getLatestPapers(query="machine learning", num_results=1)
        
        if results.num_results == 0:
            logger.error("未找到论文，无法测试OCR")
            return
        
        paper = results.results[0]
        logger.info(f"找到论文: {paper.title}")
        logger.info(f"PDF链接: {paper.pdf_link}")
        
        # 下载PDF
        logger.info("下载PDF...")
        pdf_content = paper.downloadPdf()
        if pdf_content is None:
            logger.error("PDF下载失败")
            return
        
        logger.info(f"PDF下载完成，大小: {len(pdf_content)} 字节")
        
        # 执行OCR - 限制字符数以便快速测试
        logger.info("开始OCR识别...")
        ocr_result = paper.performOCR(max_chars=2000, max_pages=2)
        
        if ocr_result:
            logger.info(f"OCR识别成功！提取文本长度: {len(ocr_result)} 字符")
            
            # 显示前500字符的内容
            preview = ocr_result[:500] + "..." if len(ocr_result) > 500 else ocr_result
            logger.info("OCR识别内容预览:")
            print("=" * 50)
            print(preview)
            print("=" * 50)
            
            # 检查文本质量
            words = ocr_result.split()
            logger.info(f"识别到的单词数: {len(words)}")
            
            # 检查是否包含常见的学术论文关键词
            academic_keywords = ['abstract', 'introduction', 'method', 'result', 'conclusion', 
                               'figure', 'table', 'reference', 'algorithm', 'experiment']
            found_keywords = [kw for kw in academic_keywords if kw.lower() in ocr_result.lower()]
            logger.info(f"发现的学术关键词: {found_keywords}")
            
            return True
        else:
            logger.error("OCR识别失败或未提取到内容")
            return False
            
    except Exception as e:
        logger.error(f"测试失败: {e}")
        return False


async def test_ocr_performance():
    """测试OCR性能"""
    logger.info("=== 测试OCR性能 ===")
    
    try:
        import time
        
        # 创建ArXiv工具
        arxiv_tool = ArxivTool()
        
        # 搜索论文
        results = arxiv_tool.getLatestPapers(query="computer vision", num_results=1)
        
        if results.num_results == 0:
            logger.warning("未找到论文，跳过性能测试")
            return
        
        paper = results.results[0]
        
        # 下载PDF
        pdf_content = paper.downloadPdf()
        if pdf_content is None:
            logger.warning("PDF下载失败，跳过性能测试")
            return
        
        # 测试不同字符限制的OCR性能
        test_configs = [
            {"max_chars": 1000, "max_pages": 1, "desc": "小规模测试"},
            {"max_chars": 5000, "max_pages": 3, "desc": "中等规模测试"},
            {"max_chars": 10000, "max_pages": 5, "desc": "大规模测试"}
        ]
        
        for config in test_configs:
            logger.info(f"开始{config['desc']}: max_chars={config['max_chars']}, max_pages={config['max_pages']}")
            
            start_time = time.time()
            ocr_result = paper.performOCR(max_chars=config['max_chars'], max_pages=config['max_pages'])
            end_time = time.time()
            
            duration = end_time - start_time
            
            if ocr_result:
                char_count = len(ocr_result)
                words_count = len(ocr_result.split())
                logger.info(f"{config['desc']}完成:")
                logger.info(f"  - 耗时: {duration:.2f}秒")
                logger.info(f"  - 提取字符数: {char_count}")
                logger.info(f"  - 提取单词数: {words_count}")
                logger.info(f"  - 处理速度: {char_count/duration:.1f} 字符/秒")
            else:
                logger.warning(f"{config['desc']}失败")
            
            print("-" * 40)
            
    except Exception as e:
        logger.error(f"性能测试失败: {e}")


async def main():
    """主函数"""
    logger.info("开始测试pix2text OCR功能")
    
    try:
        # 基本功能测试
        basic_success = await test_pix2text_ocr()
        
        if basic_success:
            logger.info("基本功能测试通过")
            
            # 性能测试
            await test_ocr_performance()
        else:
            logger.error("基本功能测试失败")
            
    except Exception as e:
        logger.error(f"测试过程中发生错误: {e}")
    
    logger.info("测试完成")


if __name__ == "__main__":
    asyncio.run(main())