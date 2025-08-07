"""
统一的论文深度分析服务

提供统一的论文深度分析接口，替代各个模块中的重复实现
包含完整的分析流程：文件准备、PDF下载、OCR处理、深度分析
"""

import os
import re
import time
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

from loguru import logger

from HomeSystem.utility.arxiv.arxiv import ArxivData


class PaperAnalysisService:
    """统一的论文深度分析服务
    
    功能：
    1. 论文文件夹准备
    2. PDF下载和验证
    3. OCR文本提取
    4. 深度分析执行
    5. 结果处理和保存
    """
    
    def __init__(self, default_config: Optional[Dict[str, Any]] = None):
        """
        初始化分析服务
        
        Args:
            default_config: 默认配置参数
        """
        self.default_config = default_config or {
            'analysis_model': 'deepseek.DeepSeek_V3',
            'vision_model': 'ollama.Qwen2_5_VL_7B',
            'timeout': 600
        }
    
    def perform_deep_analysis(
        self,
        arxiv_id: str,
        paper_folder_path: str,
        config: Optional[Dict[str, Any]] = None,
        paper_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        执行完整的深度论文分析流程
        
        Args:
            arxiv_id: ArXiv论文ID
            paper_folder_path: 论文文件夹路径
            config: 分析配置（可选）
            paper_data: 论文基础数据（可选，用于PDF下载）
            
        Returns:
            Dict: 分析结果
                - success: bool, 是否成功
                - analysis_result: str, 分析内容（成功时）
                - analysis_file_path: str, 分析文件路径（成功时）
                - error: str, 错误信息（失败时）
        """
        try:
            logger.info(f"🚀 开始论文深度分析流程: {arxiv_id}")
            
            # 合并配置
            analysis_config = {**self.default_config, **(config or {})}
            
            # 第一步：准备论文文件夹
            folder_result = self._prepare_paper_folder(paper_folder_path)
            if not folder_result['success']:
                return folder_result
            
            logger.info(f"✅ 论文文件夹准备完成: {paper_folder_path}")
            
            # 第二步：下载论文PDF（如果尚未存在）
            pdf_result = self._ensure_paper_pdf(
                arxiv_id, 
                paper_folder_path, 
                paper_data
            )
            if not pdf_result['success']:
                return pdf_result
            
            logger.info(f"✅ 论文PDF准备完成: {arxiv_id}")
            
            # 第三步：执行OCR处理（如果尚未存在）
            ocr_result = self._ensure_paper_ocr(arxiv_id, paper_folder_path)
            if not ocr_result['success']:
                return ocr_result
            
            logger.info(f"✅ 论文OCR处理完成: {arxiv_id}")
            
            # 第四步：执行深度分析
            analysis_result = self._execute_deep_analysis(
                arxiv_id, 
                paper_folder_path, 
                analysis_config
            )
            
            if analysis_result['success']:
                logger.info(f"✅ 深度分析完成: {arxiv_id}")
            else:
                logger.error(f"❌ 深度分析失败: {arxiv_id}")
            
            return analysis_result
            
        except Exception as e:
            logger.error(f"💥 深度分析流程异常 {arxiv_id}: {e}")
            return {
                'success': False,
                'error': f'深度分析流程异常: {str(e)}'
            }
    
    def _prepare_paper_folder(self, paper_folder_path: str) -> Dict[str, Any]:
        """
        准备论文分析文件夹
        
        Args:
            paper_folder_path: 论文文件夹路径
            
        Returns:
            Dict: 操作结果
        """
        try:
            folder_path = Path(paper_folder_path)
            folder_path.mkdir(parents=True, exist_ok=True)
            
            logger.info(f"📁 论文文件夹已准备: {folder_path}")
            return {
                'success': True,
                'folder_path': str(folder_path)
            }
            
        except Exception as e:
            logger.error(f"❌ 准备论文文件夹失败: {e}")
            return {
                'success': False,
                'error': f'准备论文文件夹失败: {str(e)}'
            }
    
    def _ensure_paper_pdf(
        self,
        arxiv_id: str,
        paper_folder_path: str,
        paper_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        确保论文PDF文件存在
        
        Args:
            arxiv_id: ArXiv论文ID
            paper_folder_path: 论文文件夹路径
            paper_data: 论文基础数据
            
        Returns:
            Dict: 操作结果
        """
        try:
            # 检查PDF是否已存在
            pdf_path = os.path.join(paper_folder_path, f"{arxiv_id}.pdf")
            if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
                logger.info(f"📄 PDF文件已存在，跳过下载: {pdf_path}")
                return {
                    'success': True,
                    'pdf_path': pdf_path,
                    'skipped': True
                }
            
            # 下载PDF
            logger.info(f"📥 开始下载PDF: {arxiv_id}")
            
            # 构造ArxivData对象
            if paper_data:
                arxiv_data = ArxivData(paper_data)
            else:
                # 使用最小必要信息
                arxiv_data = ArxivData({
                    'title': '',
                    'link': f"https://arxiv.org/abs/{arxiv_id}",
                    'snippet': '',
                    'categories': '',
                    'arxiv_id': arxiv_id
                })
            
            # 下载PDF到指定路径
            arxiv_data.downloadPdf(save_path=paper_folder_path)
            
            # 检查下载结果并重命名为标准格式
            pdf_files = [f for f in os.listdir(paper_folder_path) if f.endswith('.pdf')]
            if pdf_files:
                # 重命名为标准格式
                actual_pdf_path = os.path.join(paper_folder_path, pdf_files[0])
                if actual_pdf_path != pdf_path and os.path.exists(actual_pdf_path):
                    os.rename(actual_pdf_path, pdf_path)
                    logger.info(f"📁 PDF重命名为标准格式: {pdf_path}")
            
            # 验证下载结果
            if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
                logger.info(f"✅ PDF下载成功: {pdf_path}")
                return {
                    'success': True,
                    'pdf_path': pdf_path,
                    'downloaded': True
                }
            else:
                logger.error(f"❌ PDF下载失败，文件不存在或为空: {pdf_path}")
                return {
                    'success': False,
                    'error': 'PDF下载失败，文件不存在或为空'
                }
                
        except Exception as e:
            logger.error(f"❌ 下载PDF失败 {arxiv_id}: {e}")
            return {
                'success': False,
                'error': f'下载PDF失败: {str(e)}'
            }
    
    def _ensure_paper_ocr(self, arxiv_id: str, paper_folder_path: str) -> Dict[str, Any]:
        """
        确保论文OCR处理完成
        
        Args:
            arxiv_id: ArXiv论文ID
            paper_folder_path: 论文文件夹路径
            
        Returns:
            Dict: 操作结果
        """
        try:
            # 检查OCR结果是否已存在
            ocr_file = os.path.join(paper_folder_path, f"{arxiv_id}_paddleocr.md")
            if os.path.exists(ocr_file) and os.path.getsize(ocr_file) > 0:
                logger.info(f"📝 OCR文件已存在，跳过处理: {ocr_file}")
                return {
                    'success': True,
                    'ocr_file_path': ocr_file,
                    'skipped': True
                }
            
            # 检查PDF文件
            pdf_path = os.path.join(paper_folder_path, f"{arxiv_id}.pdf")
            if not os.path.exists(pdf_path):
                logger.error(f"❌ PDF文件不存在: {pdf_path}")
                return {
                    'success': False,
                    'error': 'PDF文件不存在，无法进行OCR'
                }
            
            logger.info(f"🔍 开始OCR处理: {pdf_path}")
            
            # 创建ArxivData实例并执行OCR
            arxiv_data = ArxivData({
                'title': '',
                'link': f"https://arxiv.org/abs/{arxiv_id}",
                'snippet': '',
                'categories': '',
                'arxiv_id': arxiv_id
            })
            
            # 从文件加载PDF
            with open(pdf_path, 'rb') as f:
                arxiv_data.pdf = f.read()
            
            # 执行PaddleOCR处理
            ocr_result, status_info = arxiv_data.performOCR(
                use_paddleocr=True,
                auto_save=True,
                save_path=paper_folder_path
            )
            
            if ocr_result and len(ocr_result.strip()) > 0:
                logger.info(f"✅ OCR处理成功，生成 {len(ocr_result)} 字符: {arxiv_id}")
                return {
                    'success': True,
                    'ocr_file_path': ocr_file,
                    'ocr_content': ocr_result,
                    'processed': True
                }
            else:
                logger.error(f"❌ OCR处理失败，未生成有效内容: {arxiv_id}")
                return {
                    'success': False,
                    'error': 'OCR处理失败，未生成有效内容'
                }
                
        except Exception as e:
            logger.error(f"❌ OCR处理失败 {arxiv_id}: {e}")
            return {
                'success': False,
                'error': f'OCR处理失败: {str(e)}'
            }
    
    def _execute_deep_analysis(
        self,
        arxiv_id: str,
        paper_folder_path: str,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        执行深度分析
        
        Args:
            arxiv_id: ArXiv论文ID
            paper_folder_path: 论文文件夹路径
            config: 分析配置
            
        Returns:
            Dict: 分析结果
        """
        try:
            logger.info(f"🤖 开始深度分析: {arxiv_id}")
            
            # 动态导入深度分析智能体
            try:
                from HomeSystem.graph.deep_paper_analysis_agent import create_deep_paper_analysis_agent
                logger.info("✅ 成功导入深度论文分析智能体")
            except Exception as import_error:
                logger.error(f"❌ 导入深度论文分析智能体失败: {import_error}")
                return {
                    'success': False,
                    'error': f'导入深度论文分析智能体失败: {str(import_error)}'
                }
            
            # 创建深度分析智能体
            logger.info("🤖 创建深度分析智能体...")
            agent = create_deep_paper_analysis_agent(
                analysis_model=config['analysis_model'],
                vision_model=config['vision_model']
            )
            logger.info("✅ 深度分析智能体创建成功")
            
            # 执行分析
            analysis_result, report_content = agent.analyze_and_generate_report(
                folder_path=paper_folder_path,
                thread_id=f"unified_analysis_{arxiv_id}_{int(time.time())}"
            )
            
            # 检查分析是否成功
            if 'error' in analysis_result:
                logger.error(f"分析执行失败 {arxiv_id}: {analysis_result['error']}")
                return {
                    'success': False,
                    'error': f"分析执行失败: {analysis_result['error']}"
                }
            
            # 处理分析结果
            if analysis_result.get('analysis_result') or report_content:
                # 使用分析结果或报告内容
                final_content = analysis_result.get('analysis_result') or report_content
                
                # 处理图片路径（如果需要）
                processed_content = self._process_image_paths(final_content, arxiv_id)
                
                # 保存分析结果
                analysis_file_path = os.path.join(paper_folder_path, f"{arxiv_id}_analysis.md")
                with open(analysis_file_path, 'w', encoding='utf-8') as f:
                    f.write(processed_content)
                
                logger.info(f"深度分析完成: {arxiv_id}, 保存了 {len(processed_content)} 字符")
                logger.info(f"分析结果已保存到: {analysis_file_path}")
                
                return {
                    'success': True,
                    'analysis_result': processed_content,
                    'analysis_file_path': analysis_file_path,
                    'content_length': len(processed_content)
                }
            else:
                logger.warning(f"深度分析未生成有效结果: {arxiv_id}")
                return {
                    'success': False,
                    'error': '深度分析未生成有效结果'
                }
                
        except Exception as e:
            logger.error(f"❌ 执行深度分析失败 {arxiv_id}: {e}")
            return {
                'success': False,
                'error': f'执行深度分析失败: {str(e)}'
            }
    
    def _process_image_paths(self, content: str, arxiv_id: str) -> str:
        """
        处理Markdown内容中的图片路径
        
        Args:
            content: 原始Markdown内容
            arxiv_id: ArXiv论文ID
            
        Returns:
            str: 处理后的Markdown内容
        """
        try:
            logger.info(f"🖼️ 开始处理图片路径: {arxiv_id}")
            
            # 使用正则表达式匹配图片路径
            img_pattern = r'!\[([^\]]*)\]\((imgs/[^)]+)\)'
            
            def replace_image_path(match):
                alt_text = match.group(1)
                relative_path = match.group(2)
                filename = relative_path.replace('imgs/', '')
                # 生成Web可访问路径（根据具体Web应用需求调整）
                new_path = f"/paper/{arxiv_id}/analysis_images/{filename}"
                logger.debug(f"  📸 转换图片路径: {relative_path} → {new_path}")
                return f"![{alt_text}]({new_path})"
            
            # 统计原始图片引用数量
            original_matches = re.findall(img_pattern, content)
            logger.info(f"  📊 发现 {len(original_matches)} 个图片引用: {arxiv_id}")
            
            # 替换所有图片路径
            processed_content = re.sub(img_pattern, replace_image_path, content)
            
            # 验证处理结果
            processed_matches = re.findall(r'!\[([^\]]*)\]\((/paper/[^)]+)\)', processed_content)
            logger.info(f"  ✅ 成功处理 {len(processed_matches)} 个图片路径: {arxiv_id}")
            
            return processed_content
            
        except Exception as e:
            logger.error(f"❌ 处理图片路径失败 {arxiv_id}: {e}")
            return content
    
    def add_analysis_footer(
        self, 
        content: str, 
        publication_date: Optional[str] = None,
        additional_info: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        添加分析结果的页脚信息
        
        Args:
            content: 分析内容
            publication_date: 论文发表时间
            additional_info: 额外信息
            
        Returns:
            str: 添加页脚后的内容
        """
        try:
            footer_parts = ["---"]
            
            if publication_date:
                footer_parts.append(f"**论文发表时间**: {publication_date}")
                footer_parts.append("")
            
            if additional_info:
                for key, value in additional_info.items():
                    footer_parts.append(f"**{key}**: {value}")
                footer_parts.append("")
            
            footer_parts.extend([
                "---",
                "*此分析由 HomeSystem 生成*"
            ])
            
            footer_content = "\n\n" + "\n".join(footer_parts)
            return content + footer_content
            
        except Exception as e:
            logger.error(f"❌ 添加页脚失败: {e}")
            return content


# 便捷函数
def create_paper_analysis_service(config: Optional[Dict[str, Any]] = None) -> PaperAnalysisService:
    """
    创建论文分析服务的便捷函数
    
    Args:
        config: 配置参数
        
    Returns:
        PaperAnalysisService: 分析服务实例
    """
    return PaperAnalysisService(default_config=config)