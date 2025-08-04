"""
深度论文分析服务
处理论文深度分析的业务逻辑
"""
import os
import sys
import threading
import time
import logging
import re
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

# 添加 HomeSystem 模块路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from database import PaperService

logger = logging.getLogger(__name__)


class DeepAnalysisService:
    """深度论文分析服务类"""
    
    def __init__(self, paper_service: PaperService):
        self.paper_service = paper_service
        self.analysis_threads = {}  # 存储正在进行的分析线程
        
        # 默认配置
        self.default_config = {
            'analysis_model': 'deepseek.DeepSeek_V3',
            'vision_model': 'ollama.Qwen2_5_VL_7B',
            'timeout': 600  # 10分钟超时
        }
    
    def start_analysis(self, arxiv_id: str, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        启动论文深度分析
        
        Args:
            arxiv_id: ArXiv论文ID
            config: 分析配置（可选）
            
        Returns:
            Dict: 操作结果
        """
        try:
            logger.info(f"🚀 开始启动深度分析 - ArXiv ID: {arxiv_id}")
            
            # 检查论文是否存在
            paper = self.paper_service.get_paper_detail(arxiv_id)
            if not paper:
                logger.error(f"❌ 论文不存在: {arxiv_id}")
                return {
                    'success': False,
                    'error': f'论文 {arxiv_id} 不存在'
                }
            
            logger.info(f"✅ 论文存在检查通过: {arxiv_id}")
            
            # 检查是否已在分析中
            if arxiv_id in self.analysis_threads:
                thread = self.analysis_threads[arxiv_id]
                if thread.is_alive():
                    logger.warning(f"⚠️ 论文已在分析中: {arxiv_id}")
                    return {
                        'success': False,
                        'error': '该论文正在分析中，请稍后'
                    }
                else:
                    # 清理已完成的线程
                    del self.analysis_threads[arxiv_id]
                    logger.info(f"🧹 清理了已完成的线程: {arxiv_id}")
            
            # 检查论文文件夹是否存在
            paper_folder = f"/mnt/nfs_share/code/homesystem/data/paper_analyze/{arxiv_id}"
            logger.info(f"📁 检查论文文件夹: {paper_folder}")
            
            if not os.path.exists(paper_folder):
                logger.error(f"❌ 论文文件夹不存在: {paper_folder}")
                return {
                    'success': False,
                    'error': f'论文数据文件夹不存在: {paper_folder}'
                }
            
            logger.info(f"✅ 论文文件夹存在检查通过: {paper_folder}")
            
            # 更新分析状态为处理中
            self.paper_service.update_analysis_status(arxiv_id, 'processing')
            
            # 合并配置
            analysis_config = {**self.default_config, **(config or {})}
            
            # 创建并启动分析线程
            thread = threading.Thread(
                target=self._run_analysis,
                args=(arxiv_id, paper_folder, analysis_config),
                daemon=True
            )
            thread.start()
            
            # 保存线程引用
            self.analysis_threads[arxiv_id] = thread
            
            logger.info(f"Started deep analysis for paper {arxiv_id}")
            
            return {
                'success': True,
                'message': '深度分析已启动',
                'status': 'processing'
            }
            
        except Exception as e:
            logger.error(f"Failed to start analysis for {arxiv_id}: {e}")
            # 更新状态为失败
            try:
                self.paper_service.update_analysis_status(arxiv_id, 'failed')
            except:
                pass
            
            return {
                'success': False,
                'error': f'启动分析失败: {str(e)}'
            }
    
    def _run_analysis(self, arxiv_id: str, paper_folder: str, config: Dict[str, Any]):
        """
        执行论文分析（在后台线程中运行）
        
        Args:
            arxiv_id: ArXiv论文ID
            paper_folder: 论文文件夹路径
            config: 分析配置
        """
        try:
            logger.info(f"Starting analysis for {arxiv_id} with config: {config}")
            
            # 动态导入深度分析智能体（延迟导入避免启动时的兼容性问题）
            try:
                from HomeSystem.graph.deep_paper_analysis_agent import create_deep_paper_analysis_agent
                logger.info("✅ Successfully imported deep paper analysis agent")
            except Exception as import_error:
                logger.error(f"❌ Failed to import deep paper analysis agent: {import_error}")
                self.paper_service.update_analysis_status(arxiv_id, 'failed')
                return
            
            # 创建深度分析智能体
            logger.info("🤖 Creating deep paper analysis agent...")
            agent = create_deep_paper_analysis_agent(
                analysis_model=config['analysis_model'],
                vision_model=config['vision_model']
            )
            logger.info("✅ Deep paper analysis agent created successfully")
            
            # 执行分析
            analysis_result, report_content = agent.analyze_and_generate_report(
                folder_path=paper_folder,
                thread_id=f"web_analysis_{arxiv_id}_{int(time.time())}"
            )
            
            # 检查分析是否成功
            if 'error' in analysis_result:
                logger.error(f"Analysis failed for {arxiv_id}: {analysis_result['error']}")
                self.paper_service.update_analysis_status(arxiv_id, 'failed')
                return
            
            # 处理分析结果
            if analysis_result.get('analysis_result') or report_content:
                # 使用分析结果或报告内容
                final_content = analysis_result.get('analysis_result') or report_content
                
                # 处理图片路径
                processed_content = self._process_image_paths(final_content, arxiv_id)
                
                # 保存分析结果
                self.paper_service.save_analysis_result(arxiv_id, processed_content)
                
                # 保存到文件
                analysis_file = os.path.join(paper_folder, f"{arxiv_id}_analysis.md")
                with open(analysis_file, 'w', encoding='utf-8') as f:
                    f.write(processed_content)
                
                logger.info(f"Analysis completed for {arxiv_id}, saved {len(processed_content)} characters")
                
                # 更新状态为完成
                self.paper_service.update_analysis_status(arxiv_id, 'completed')
            else:
                logger.warning(f"No analysis result generated for {arxiv_id}")
                self.paper_service.update_analysis_status(arxiv_id, 'failed')
                
        except Exception as e:
            logger.error(f"Analysis failed for {arxiv_id}: {e}")
            # 更新状态为失败
            try:
                self.paper_service.update_analysis_status(arxiv_id, 'failed')
            except:
                pass
        finally:
            # 清理线程引用
            if arxiv_id in self.analysis_threads:
                del self.analysis_threads[arxiv_id]
    
    def _process_image_paths(self, content: str, arxiv_id: str) -> str:
        """
        处理Markdown内容中的图片路径，将相对路径转换为可访问的URL路径
        
        Args:
            content: 原始Markdown内容
            arxiv_id: ArXiv论文ID
            
        Returns:
            str: 处理后的Markdown内容
        """
        try:
            # 使用正则表达式匹配Markdown图片语法
            img_pattern = r'!\[(.*?)\]\((imgs/[^)]+)\)'
            
            def replace_image_path(match):
                alt_text = match.group(1)
                relative_path = match.group(2)
                # 转换为Flask可访问的URL路径
                new_path = f"/paper/{arxiv_id}/analysis_images/{relative_path.replace('imgs/', '')}"
                return f"![{alt_text}]({new_path})"
            
            # 替换所有图片路径
            processed_content = re.sub(img_pattern, replace_image_path, content)
            
            logger.info(f"Processed {len(re.findall(img_pattern, content))} image paths for {arxiv_id}")
            
            return processed_content
            
        except Exception as e:
            logger.error(f"Failed to process image paths for {arxiv_id}: {e}")
            return content
    
    def get_analysis_status(self, arxiv_id: str) -> Dict[str, Any]:
        """
        获取分析状态
        
        Args:
            arxiv_id: ArXiv论文ID
            
        Returns:
            Dict: 状态信息
        """
        try:
            # 从数据库获取状态
            status_info = self.paper_service.get_analysis_status(arxiv_id)
            
            if not status_info:
                return {
                    'success': True,
                    'status': 'not_started',
                    'message': '尚未开始分析'
                }
            
            # 检查是否有正在运行的线程
            if arxiv_id in self.analysis_threads:
                thread = self.analysis_threads[arxiv_id]
                if thread.is_alive():
                    status_info['is_running'] = True
                else:
                    # 清理已完成的线程
                    del self.analysis_threads[arxiv_id]
                    status_info['is_running'] = False
            else:
                status_info['is_running'] = False
            
            return {
                'success': True,
                **status_info
            }
            
        except Exception as e:
            logger.error(f"Failed to get analysis status for {arxiv_id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_analysis_result(self, arxiv_id: str) -> Dict[str, Any]:
        """
        获取分析结果
        
        Args:
            arxiv_id: ArXiv论文ID
            
        Returns:
            Dict: 分析结果
        """
        try:
            result = self.paper_service.get_analysis_result(arxiv_id)
            
            if not result:
                return {
                    'success': False,
                    'error': '分析结果不存在'
                }
            
            return {
                'success': True,
                **result
            }
            
        except Exception as e:
            logger.error(f"Failed to get analysis result for {arxiv_id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def cancel_analysis(self, arxiv_id: str) -> Dict[str, Any]:
        """
        取消正在进行的分析
        
        Args:
            arxiv_id: ArXiv论文ID
            
        Returns:
            Dict: 操作结果
        """
        try:
            if arxiv_id not in self.analysis_threads:
                return {
                    'success': False,
                    'error': '没有正在进行的分析'
                }
            
            thread = self.analysis_threads[arxiv_id]
            if not thread.is_alive():
                del self.analysis_threads[arxiv_id]
                return {
                    'success': False,
                    'error': '分析已完成或已停止'
                }
            
            # 注意：Python线程无法强制停止，这里只能标记状态
            # 实际的线程仍会继续运行直到自然结束
            del self.analysis_threads[arxiv_id]
            
            # 更新数据库状态
            self.paper_service.update_analysis_status(arxiv_id, 'cancelled')
            
            logger.info(f"Analysis cancelled for {arxiv_id}")
            
            return {
                'success': True,
                'message': '分析已取消'
            }
            
        except Exception as e:
            logger.error(f"Failed to cancel analysis for {arxiv_id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def cleanup_completed_threads(self):
        """清理已完成的分析线程"""
        completed_threads = []
        
        for arxiv_id, thread in self.analysis_threads.items():
            if not thread.is_alive():
                completed_threads.append(arxiv_id)
        
        for arxiv_id in completed_threads:
            del self.analysis_threads[arxiv_id]
        
        if completed_threads:
            logger.info(f"Cleaned up {len(completed_threads)} completed analysis threads")
    
    def get_active_analyses(self) -> Dict[str, Any]:
        """
        获取所有活跃的分析任务
        
        Returns:
            Dict: 活跃任务信息
        """
        try:
            self.cleanup_completed_threads()
            
            active_analyses = []
            for arxiv_id, thread in self.analysis_threads.items():
                if thread.is_alive():
                    status_info = self.paper_service.get_analysis_status(arxiv_id)
                    if status_info:
                        active_analyses.append({
                            'arxiv_id': arxiv_id,
                            **status_info
                        })
            
            return {
                'success': True,
                'active_count': len(active_analyses),
                'analyses': active_analyses
            }
            
        except Exception as e:
            logger.error(f"Failed to get active analyses: {e}")
            return {
                'success': False,
                'error': str(e)
            }