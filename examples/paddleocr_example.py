#!/usr/bin/env python3
"""
PaddleOCR 3.0 集成示例
展示如何使用新的 PaddleOCR 功能进行结构化文档解析
"""

import sys
import os

# 添加项目根目录到路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from HomeSystem.utility.arxiv import ArxivTool

def main():
    print("=== PaddleOCR 3.0 集成示例 ===")
    
    # 初始化 ArXiv 工具
    arxiv_tool = ArxivTool()
    
    # 搜索一篇论文进行测试
    print("\n🔍 搜索测试论文...")
    results = arxiv_tool.arxivSearch(query="machine learning", num_results=3)
    
    if results.num_results > 0:
        # 选择第一篇论文
        paper = results.results[0]
        print(f"📄 选择论文: {paper.title[:80]}...")
        
        try:
            # 下载 PDF
            print("\n📥 下载 PDF...")
            paper.downloadPdf()
            print("✅ PDF 下载完成")
            
            # 方法1: 使用默认的 PyMuPDF (快速但简单)
            print("\n🔍 方法1: PyMuPDF 快速文本提取")
            text_result, text_status = paper.performOCR(use_paddleocr=False)
            
            if text_result:
                print(f"✅ PyMuPDF 完成: {len(text_result)} 字符")
                print(f"📊 状态: 处理 {text_status['processed_pages']}/{text_status['total_pages']} 页")
                print(f"📝 预览: {text_result[:200]}...")
            
            # 方法2: 使用 PaddleOCR 3.0 (结构化但较慢)
            print("\n🔍 方法2: PaddleOCR 3.0 结构化识别")
            markdown_result, paddle_status = paper.performOCR(use_paddleocr=True)
            
            if markdown_result:
                print(f"✅ PaddleOCR 完成: {len(markdown_result)} 字符")
                print(f"📊 状态: 处理 {paddle_status['processed_pages']}/{paddle_status['total_pages']} 页")
                if paddle_status.get('images_count', 0) > 0:
                    print(f"🖼️ 提取图片: {paddle_status['images_count']} 张")
                print(f"📝 Markdown 预览: {markdown_result[:300]}...")
                
                # 展示 PaddleOCR 特有功能
                print("\n🎯 PaddleOCR 特色功能:")
                
                # 获取结构化 Markdown
                paddle_markdown = paper.getPaddleOcrResult()
                if paddle_markdown:
                    print(f"   ✓ 结构化 Markdown: {len(paddle_markdown)} 字符")
                
                # 获取提取的图片
                paddle_images = paper.getPaddleOcrImages()
                if paddle_images:
                    print(f"   ✓ 图片提取: {len(paddle_images)} 张图片")
                    for img_path in list(paddle_images.keys())[:3]:  # 显示前3张图片路径
                        print(f"     - {img_path}")
                
                # 保存结果到文件
                output_path = "./paddleocr_output"
                if paper.savePaddleOcrToFile(output_path):
                    print(f"   ✓ 结果已保存到: {output_path}")
            
            else:
                print("❌ PaddleOCR 未提取到内容")
            
            # 清理内存
            print("\n🧹 清理内存...")
            paper.clearPaddleOcrResult()
            paper.clearPdf()
            print("✅ 清理完成")
            
        except Exception as e:
            print(f"❌ 处理失败: {str(e)}")
    
    else:
        print("❌ 未找到测试论文")
    
    print("\n=== 示例完成 ===")
    print("\n📖 使用说明:")
    print("1. 确保已安装 PaddlePaddle >= 3.0.0 和 PaddleOCR >= 3.0.0")
    print("2. PyMuPDF 方法适合快速文本提取")
    print("3. PaddleOCR 方法适合需要保留文档结构的场景")
    print("4. PaddleOCR 可以提取图片和生成 Markdown 格式")

if __name__ == "__main__":
    main()