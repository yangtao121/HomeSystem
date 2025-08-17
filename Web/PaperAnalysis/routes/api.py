"""
统一API路由 - 整合两个应用的API接口
提供RESTful API接口用于前端调用和第三方集成
"""
from flask import Blueprint, request, jsonify, send_file
from services.task_service import paper_gather_service
from services.paper_gather_service import paper_data_service
from services.paper_explore_service import PaperService
from services.dify_service import DifyService
from HomeSystem.integrations.paper_analysis.analysis_service import PaperAnalysisService
from HomeSystem.integrations.database import ArxivPaperModel
import logging
import os
import sys
import json
import tempfile
import zipfile
import re
from typing import Dict, Any, Optional
import asyncio
import httpx
import yaml
from pathlib import Path

logger = logging.getLogger(__name__)

# 定义项目根目录
PROJECT_ROOT = os.path.join(os.path.dirname(__file__), '..', '..', '..')
sys.path.append(PROJECT_ROOT)

api_bp = Blueprint('api', __name__, url_prefix='/api')

# 初始化服务
paper_explore_service = PaperService()
dify_service = DifyService()

# 初始化Redis连接
try:
    import redis
    from config import REDIS_CONFIG
    redis_client = redis.Redis(
        host=REDIS_CONFIG['host'],
        port=REDIS_CONFIG['port'],
        db=REDIS_CONFIG['db'],
        decode_responses=True
    )
    redis_client.ping()
except Exception as e:
    logger.warning(f"API模块Redis连接失败: {e}")
    redis_client = None


def apply_remote_ocr_config():
    """
    从Redis加载远程OCR配置并设置环境变量
    
    Returns:
        dict: 远程OCR配置信息
    """
    config = {
        'enable_remote_ocr': False,
        'remote_ocr_endpoint': 'http://localhost:5001',
        'remote_ocr_timeout': 300,
        'remote_ocr_max_pages': 25
    }
    
    if redis_client:
        try:
            # 从Redis加载系统设置
            system_settings_key = "system_settings:global"
            system_settings_data = redis_client.get(system_settings_key)
            
            if system_settings_data:
                system_settings = json.loads(system_settings_data)
                
                # 更新配置
                config['enable_remote_ocr'] = system_settings.get('enable_remote_ocr', False)
                config['remote_ocr_endpoint'] = system_settings.get('remote_ocr_endpoint', 'http://localhost:5001')
                config['remote_ocr_timeout'] = system_settings.get('remote_ocr_timeout', 300)
                config['remote_ocr_max_pages'] = system_settings.get('remote_ocr_max_pages', 25)
                
                # 如果启用了远程OCR，设置环境变量
                if config['enable_remote_ocr']:
                    import os
                    os.environ['REMOTE_OCR_ENDPOINT'] = config['remote_ocr_endpoint']
                    os.environ['REMOTE_OCR_TIMEOUT'] = str(config['remote_ocr_timeout'])
                    os.environ['REMOTE_OCR_MAX_PAGES'] = str(config['remote_ocr_max_pages'])
                    logger.info(f"🌐 API已设置远程OCR环境变量: {config['remote_ocr_endpoint']} (超时: {config['remote_ocr_timeout']}秒, 最大页数: {config['remote_ocr_max_pages']})")
                else:
                    logger.debug("🔍 API使用本地OCR (远程OCR未启用)")
            else:
                logger.debug("未找到系统设置，使用默认OCR配置")
                
        except Exception as e:
            logger.warning(f"加载远程OCR配置失败: {e}")
    else:
        logger.debug("Redis未连接，使用默认OCR配置")
    
    return config


# 初始化分析服务
paper_analysis_service = PaperAnalysisService()

# 分析服务适配器类 - 桥接PaperAnalysisService和Web API接口
class AnalysisServiceAdapter:
    """Web API分析服务适配器"""
    
    def __init__(self, paper_service: PaperService, redis_client=None):
        self.paper_service = paper_service
        self.redis_client = redis_client
        self.analysis_threads = {}  # 存储正在进行的分析线程
        
        # 默认配置
        self.default_config = {
            'analysis_model': 'deepseek.DeepSeek_V3',
            'vision_model': 'ollama.Qwen2_5_VL_7B', 
            'timeout': 1800  # 增加默认超时为30分钟
        }
        
        # Redis键前缀
        self.REDIS_PREFIX = "deep_analysis"
        self.STATUS_KEY_PREFIX = f"{self.REDIS_PREFIX}:status"
        self.PROCESS_KEY_PREFIX = f"{self.REDIS_PREFIX}:process"
    
    def load_config(self) -> Dict[str, Any]:
        """从Redis加载配置，优先使用新的系统设置，如果不存在则使用旧配置和默认配置"""
        config = self.default_config.copy()
        
        if self.redis_client:
            try:
                # 优先尝试加载新的系统设置
                system_config_key = "system_settings:global"
                saved_system_config = self.redis_client.get(system_config_key)
                if saved_system_config:
                    import json
                    system_data = json.loads(saved_system_config)
                    
                    # 从系统设置中提取深度分析相关配置
                    analysis_config = {}
                    
                    # 模型配置映射
                    if system_data.get('deep_analysis_model'):
                        analysis_config['analysis_model'] = system_data['deep_analysis_model']
                    elif system_data.get('llm_model_name'):
                        analysis_config['analysis_model'] = system_data['llm_model_name']
                    
                    if system_data.get('vision_model'):
                        analysis_config['vision_model'] = system_data['vision_model']
                    
                    if system_data.get('video_analysis_model'):
                        analysis_config['video_analysis_model'] = system_data['video_analysis_model']
                    
                    if system_data.get('analysis_timeout'):
                        analysis_config['timeout'] = system_data['analysis_timeout']
                    
                    # 深度分析相关配置
                    if 'enable_deep_analysis' in system_data:
                        analysis_config['enable_deep_analysis'] = system_data['enable_deep_analysis']
                    if 'enable_video_analysis' in system_data:
                        analysis_config['enable_video_analysis'] = system_data['enable_video_analysis']
                    if 'deep_analysis_threshold' in system_data:
                        analysis_config['deep_analysis_threshold'] = system_data['deep_analysis_threshold']
                    if 'ocr_char_limit_for_analysis' in system_data:
                        analysis_config['ocr_char_limit_for_analysis'] = system_data['ocr_char_limit_for_analysis']
                    if 'relevance_threshold' in system_data:
                        analysis_config['relevance_threshold'] = system_data['relevance_threshold']
                    
                    # 远程OCR配置
                    if 'enable_remote_ocr' in system_data:
                        analysis_config['enable_remote_ocr'] = system_data['enable_remote_ocr']
                    if 'remote_ocr_endpoint' in system_data:
                        analysis_config['remote_ocr_endpoint'] = system_data['remote_ocr_endpoint']
                    if 'remote_ocr_timeout' in system_data:
                        analysis_config['remote_ocr_timeout'] = system_data['remote_ocr_timeout']
                    
                    config.update(analysis_config)
                    logger.info(f"从系统设置加载深度分析配置: {analysis_config}")
                
                else:
                    # 如果系统设置不存在，尝试加载旧的分析配置（向后兼容）
                    old_config_key = "analysis_config:global"
                    saved_old_config = self.redis_client.get(old_config_key)
                    if saved_old_config:
                        import json
                        old_data = json.loads(saved_old_config)
                        config.update(old_data)
                        logger.info(f"从旧配置加载深度分析配置: {old_data}")
                
            except Exception as e:
                logger.warning(f"从Redis加载配置失败，使用默认配置: {e}")
        
        return config
    
    def start_analysis(self, arxiv_id: str, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """启动论文深度分析"""
        try:
            import threading
            from pathlib import Path
            
            logger.info(f"🚀 开始启动深度分析 - ArXiv ID: {arxiv_id}")
            
            # 检查论文是否存在
            paper = self.paper_service.get_paper_detail(arxiv_id)
            if not paper:
                logger.error(f"❌ 论文不存在: {arxiv_id}")
                return {
                    'success': False,
                    'error': f'论文 {arxiv_id} 不存在'
                }
            
            # 检查是否已在分析中（包括Redis中的活跃进程记录）
            if self._is_analysis_running(arxiv_id):
                logger.warning(f"⚠️ 论文已在分析中: {arxiv_id}")
                return {
                    'success': False,
                    'error': '该论文正在分析中，请稍后'
                }
            
            # 更新分析状态为处理中
            self.paper_service.update_analysis_status(arxiv_id, 'processing')
            
            # 加载当前配置
            current_config = self.load_config()
            analysis_config = {**current_config, **(config or {})}
            
            # 在Redis中记录分析进程信息
            self._record_analysis_start(arxiv_id, analysis_config)
            
            # 创建并启动分析线程
            thread = threading.Thread(
                target=self._run_analysis,
                args=(arxiv_id, paper, analysis_config),
                daemon=True
            )
            thread.start()
            self.analysis_threads[arxiv_id] = thread
            
            logger.info(f"Started deep analysis for paper {arxiv_id}")
            
            return {
                'success': True,
                'message': '深度分析已启动',
                'status': 'processing'
            }
            
        except Exception as e:
            logger.error(f"Failed to start analysis for {arxiv_id}: {e}")
            try:
                self.paper_service.update_analysis_status(arxiv_id, 'failed')
                self._cleanup_analysis_record(arxiv_id)
            except:
                pass
            
            return {
                'success': False,
                'error': f'启动分析失败: {str(e)}'
            }
    
    def _run_analysis(self, arxiv_id: str, paper: Dict[str, Any], config: Dict[str, Any]):
        """执行论文分析（在后台线程中运行）"""
        try:
            from pathlib import Path
            import re
            
            logger.info(f"🚀 开始执行深度分析 - ArXiv ID: {arxiv_id}")
            
            # 创建分析服务实例
            analysis_service = PaperAnalysisService(default_config=config)
            
            # 计算论文文件夹路径
            # For Docker: /app/routes/api.py -> /app (2 parents) -> /app/data
            # For local: routes/api.py -> project root (4 parents) -> project_root/data
            project_root = Path(__file__).parent.parent
            if not (project_root / "data").exists():
                project_root = Path(__file__).parent.parent.parent.parent
            paper_folder_path = str(project_root / "data" / "paper_analyze" / arxiv_id)
            
            # 准备论文数据（用于PDF下载）
            paper_data = {
                'title': paper.get('title', ''),
                'link': f"https://arxiv.org/abs/{arxiv_id}",
                'snippet': paper.get('abstract', ''),
                'categories': paper.get('categories', ''),
                'arxiv_id': arxiv_id
            }
            
            # 执行完整的深度分析流程
            result = analysis_service.perform_deep_analysis(
                arxiv_id=arxiv_id,
                paper_folder_path=paper_folder_path,
                config=config,
                paper_data=paper_data
            )
            
            if result['success']:
                # 使用Web应用特有的图片路径处理
                processed_content = self._process_image_paths(
                    result['analysis_result'], 
                    arxiv_id
                )
                
                # 保存分析结果到数据库
                self.paper_service.save_analysis_result(arxiv_id, processed_content)
                
                # 重新保存处理后的内容到文件
                with open(result['analysis_file_path'], 'w', encoding='utf-8') as f:
                    f.write(processed_content)
                
                logger.info(f"Analysis completed for {arxiv_id}, saved {len(processed_content)} characters")
                self.paper_service.update_analysis_status(arxiv_id, 'completed')
            else:
                logger.error(f"❌ 深度分析失败: {arxiv_id}: {result.get('error', '未知错误')}")
                self.paper_service.update_analysis_status(arxiv_id, 'failed')
            
        except Exception as e:
            logger.error(f"💥 分析过程失败 {arxiv_id}: {e}")
            try:
                self.paper_service.update_analysis_status(arxiv_id, 'failed')
            except:
                pass
        finally:
            # 清理分析记录（包括Redis记录和内存线程引用）
            self._cleanup_analysis_record(arxiv_id)
    
    def _process_image_paths(self, content: str, arxiv_id: str) -> str:
        """处理Markdown内容中的图片路径，将相对路径转换为可访问的URL路径"""
        try:
            logger.info(f"🖼️ Starting image path processing for {arxiv_id}")
            
            # 匹配 ![alt](imgs/filename) 格式
            img_pattern = r'!\[([^\]]*)\]\((imgs/[^)]+)\)'
            
            def replace_image_path(match):
                alt_text = match.group(1)
                relative_path = match.group(2)
                filename = relative_path.replace('imgs/', '')
                new_path = f"/paper/{arxiv_id}/imgs/{filename}"
                logger.debug(f"  📸 Converting: {relative_path} → {new_path}")
                return f"![{alt_text}]({new_path})"
            
            # 统计和替换
            original_matches = re.findall(img_pattern, content)
            logger.info(f"  📊 Found {len(original_matches)} image references for {arxiv_id}")
            
            processed_content = re.sub(img_pattern, replace_image_path, content)
            
            # 验证处理结果
            processed_matches = re.findall(r'!\[([^\]]*)\]\((/paper/[^)]+)\)', processed_content)
            logger.info(f"  ✅ Successfully processed {len(processed_matches)} image paths for {arxiv_id}")
            
            return processed_content
            
        except Exception as e:
            logger.error(f"❌ Failed to process image paths for {arxiv_id}: {e}")
            return content
    
    def get_analysis_status(self, arxiv_id: str) -> Dict[str, Any]:
        """获取分析状态"""
        try:
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
        """获取分析结果"""
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
    
    def _is_analysis_running(self, arxiv_id: str) -> bool:
        """检查分析是否正在运行（同时检查内存线程和Redis记录）"""
        # 检查内存中的线程
        if arxiv_id in self.analysis_threads:
            thread = self.analysis_threads[arxiv_id]
            if thread.is_alive():
                return True
            else:
                del self.analysis_threads[arxiv_id]
        
        # 检查Redis中的进程记录
        if self.redis_client:
            try:
                process_key = f"{self.PROCESS_KEY_PREFIX}:{arxiv_id}"
                process_info = self.redis_client.get(process_key)
                if process_info:
                    import json
                    import time
                    process_data = json.loads(process_info)
                    start_time = process_data.get('start_time', 0)
                    timeout = process_data.get('timeout', self.default_config['timeout'])
                    
                    # 检查是否超时
                    if time.time() - start_time > timeout:
                        logger.warning(f"分析进程超时: {arxiv_id}, 清理超时记录")
                        self._cleanup_analysis_record(arxiv_id)
                        self.paper_service.update_analysis_status(arxiv_id, 'failed')
                        return False
                    
                    return True
            except Exception as e:
                logger.warning(f"检查Redis进程记录失败: {e}")
        
        return False
    
    def _record_analysis_start(self, arxiv_id: str, config: Dict[str, Any]):
        """在Redis中记录分析开始信息"""
        if self.redis_client:
            try:
                import json
                import time
                import os
                
                process_key = f"{self.PROCESS_KEY_PREFIX}:{arxiv_id}"
                process_data = {
                    'start_time': time.time(),
                    'timeout': config.get('timeout', self.default_config['timeout']),
                    'config': config,
                    'pid': os.getpid(),
                    'status': 'processing'
                }
                
                # 设置过期时间为超时时间的2倍，确保记录不会永久存在
                expire_time = config.get('timeout', self.default_config['timeout']) * 2
                self.redis_client.setex(
                    process_key, 
                    expire_time, 
                    json.dumps(process_data)
                )
                
                logger.info(f"已在Redis中记录分析进程信息: {arxiv_id}")
            except Exception as e:
                logger.warning(f"记录分析开始信息失败: {e}")
    
    def _cleanup_analysis_record(self, arxiv_id: str):
        """清理Redis中的分析记录"""
        if self.redis_client:
            try:
                process_key = f"{self.PROCESS_KEY_PREFIX}:{arxiv_id}"
                self.redis_client.delete(process_key)
                logger.info(f"已清理分析进程记录: {arxiv_id}")
            except Exception as e:
                logger.warning(f"清理分析记录失败: {e}")
        
        # 同时清理内存中的线程引用
        if arxiv_id in self.analysis_threads:
            del self.analysis_threads[arxiv_id]
    
    def cancel_analysis(self, arxiv_id: str) -> Dict[str, Any]:
        """取消正在进行的分析"""
        try:
            # 检查是否有正在运行的分析
            if not self._is_analysis_running(arxiv_id):
                return {
                    'success': False,
                    'error': '没有正在进行的分析任务'
                }
            
            # 更新状态为已取消
            self.paper_service.update_analysis_status(arxiv_id, 'cancelled')
            
            # 清理Redis记录
            self._cleanup_analysis_record(arxiv_id)
            
            # 注意：我们不能强制终止线程，但可以通过状态标记让线程自行退出
            logger.info(f"已取消分析任务: {arxiv_id}")
            
            return {
                'success': True,
                'message': '分析任务已取消'
            }
            
        except Exception as e:
            logger.error(f"取消分析任务失败: {e}")
            return {
                'success': False,
                'error': f'取消失败: {str(e)}'
            }
    
    def reset_analysis_status(self, arxiv_id: str) -> Dict[str, Any]:
        """重置分析状态（管理功能）"""
        try:
            # 清理所有相关记录
            self._cleanup_analysis_record(arxiv_id)
            
            # 重置数据库状态
            self.paper_service.update_analysis_status(arxiv_id, 'pending')
            
            logger.info(f"已重置分析状态: {arxiv_id}")
            
            return {
                'success': True,
                'message': '分析状态已重置'
            }
            
        except Exception as e:
            logger.error(f"重置分析状态失败: {e}")
            return {
                'success': False,
                'error': f'重置失败: {str(e)}'
            }

# 创建适配器实例
analysis_service = AnalysisServiceAdapter(paper_explore_service, redis_client)


# === 论文收集相关API (来自PaperGather) ===

@api_bp.route('/collect/models')
def get_available_models():
    """获取可用的LLM模型"""
    try:
        models = paper_gather_service.get_available_models()
        return jsonify({
            'success': True,
            'models': models
        })
    except Exception as e:
        logger.error(f"获取模型列表失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route('/collect/search_modes')
def get_search_modes():
    """获取可用的搜索模式"""
    try:
        modes = paper_gather_service.get_available_search_modes()
        return jsonify({
            'success': True,
            'search_modes': modes
        })
    except Exception as e:
        logger.error(f"获取搜索模式失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route('/collect/task/<task_id>/status')
def get_task_status(task_id):
    """获取任务状态"""
    try:
        result = paper_gather_service.get_task_result(task_id)
        if not result:
            return jsonify({
                'success': False,
                'error': '任务不存在'
            }), 404
        
        return jsonify({
            'success': True,
            'task_result': result
        })
    except Exception as e:
        logger.error(f"获取任务状态失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route('/collect/task/<task_id>/stop', methods=['POST'])
def stop_task(task_id):
    """停止任务"""
    try:
        success = paper_gather_service.stop_task(task_id)
        return jsonify({
            'success': success,
            'message': '任务停止成功' if success else '任务停止失败'
        })
    except Exception as e:
        logger.error(f"停止任务失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# === 论文浏览相关API (来自ExplorePaperData) ===

@api_bp.route('/explore/search')
def api_search():
    """搜索论文"""
    try:
        query = request.args.get('q', '').strip()
        task_name = request.args.get('task_name', '').strip()
        task_id = request.args.get('task_id', '').strip()
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('per_page', 10)), 50)
        
        papers, total = paper_explore_service.search_papers(
            query=query,
            task_name=task_name,
            task_id=task_id,
            page=page, 
            per_page=per_page
        )
        
        return jsonify({
            'success': True,
            'data': papers,
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page
        })
    
    except Exception as e:
        logger.error(f"API搜索失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/explore/stats')
def api_stats():
    """获取统计数据"""
    try:
        stats = paper_explore_service.get_overview_stats()
        return jsonify({'success': True, 'data': stats})
    
    except Exception as e:
        logger.error(f"API统计数据获取失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/explore/tasks')
def api_tasks():
    """获取可用任务列表"""
    try:
        tasks_data = paper_explore_service.get_available_tasks()
        # 将复杂的数据结构转换为简单的任务数组，供JavaScript迭代使用
        all_tasks = []
        
        # 添加基于任务名称的任务
        for task in tasks_data.get('task_names', []):
            all_tasks.append({
                'task_name': task['task_name'],
                'task_id': '',  # task_names中没有task_id
                'paper_count': task['paper_count']
            })
        
        # 添加基于任务ID的任务（避免重复）
        task_name_set = {task['task_name'] for task in all_tasks}
        for task in tasks_data.get('task_ids', []):
            if task['task_name'] not in task_name_set:
                all_tasks.append({
                    'task_name': task['task_name'],
                    'task_id': task['task_id'],
                    'paper_count': task['paper_count'],
                    'first_created': task.get('first_created'),
                    'last_created': task.get('last_created')
                })
        
        return jsonify({'success': True, 'data': {'tasks': all_tasks}})
    
    except Exception as e:
        logger.error(f"获取任务列表失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/explore/update_task_name', methods=['POST'])
def api_update_task_name():
    """更新任务名称"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': '无效的请求数据'}), 400
        
        arxiv_id = data.get('arxiv_id')
        new_task_name = (data.get('new_task_name') or '').strip()
        
        if not arxiv_id:
            return jsonify({'success': False, 'error': '缺少论文ID'}), 400
            
        success = paper_explore_service.update_task_name(arxiv_id, new_task_name)
        
        if success:
            return jsonify({'success': True, 'message': '任务名称更新成功'})
        else:
            return jsonify({'success': False, 'error': '更新失败，论文不存在'}), 404
    
    except Exception as e:
        logger.error(f"更新任务名称失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/delete_paper', methods=['POST'])
def api_delete_paper_post():
    """删除单个论文 (POST请求，从JSON body获取arxiv_id)"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': '请求数据不能为空'}), 400
        
        arxiv_id = data.get('arxiv_id')
        if not arxiv_id:
            return jsonify({'success': False, 'error': '缺少论文ID'}), 400
        
        success = paper_explore_service.delete_paper(arxiv_id)
        
        if success:
            return jsonify({'success': True, 'message': '论文删除成功'})
        else:
            return jsonify({'success': False, 'error': '删除失败，论文不存在'}), 404
    
    except Exception as e:
        logger.error(f"删除论文失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/explore/delete_paper/<arxiv_id>', methods=['DELETE'])
def api_delete_paper(arxiv_id):
    """删除单个论文"""
    try:
        success = paper_explore_service.delete_paper(arxiv_id)
        
        if success:
            return jsonify({'success': True, 'message': '论文删除成功'})
        else:
            return jsonify({'success': False, 'error': '删除失败，论文不存在'}), 404
    
    except Exception as e:
        logger.error(f"删除论文失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# === 深度分析相关API ===

@api_bp.route('/analysis/paper/<arxiv_id>/analyze', methods=['POST'])
def api_start_analysis(arxiv_id):
    """启动深度论文分析"""
    try:
        logger.info(f"🎯 收到深度分析请求 - ArXiv ID: {arxiv_id}")
        
        # 获取配置参数
        data = request.get_json() if request.is_json else {}
        config = data.get('config', {})
        
        # 启动分析
        result = analysis_service.start_analysis(arxiv_id, config)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"启动深度分析失败 {arxiv_id}: {e}")
        return jsonify({
            'success': False,
            'error': f"启动分析失败: {str(e)}"
        }), 500


@api_bp.route('/analysis/paper/<arxiv_id>/status')
def api_analysis_status(arxiv_id):
    """查询分析状态"""
    try:
        result = analysis_service.get_analysis_status(arxiv_id)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 404
            
    except Exception as e:
        logger.error(f"获取分析状态失败 {arxiv_id}: {e}")
        return jsonify({
            'success': False,
            'error': f"获取状态失败: {str(e)}"
        }), 500


@api_bp.route('/analysis/paper/<arxiv_id>/result')
def api_analysis_result(arxiv_id):
    """获取分析结果"""
    try:
        result = analysis_service.get_analysis_result(arxiv_id)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 404
            
    except Exception as e:
        logger.error(f"获取分析结果失败 {arxiv_id}: {e}")
        return jsonify({
            'success': False,
            'error': f"获取结果失败: {str(e)}"
        }), 500


@api_bp.route('/analysis/config', methods=['GET'])
def get_analysis_config():
    """获取深度分析配置和可用模型"""
    try:
        # 导入LLMFactory
        from HomeSystem.graph.llm_factory import LLMFactory
        factory = LLMFactory()
        
        # 从Redis获取当前配置
        config_key = "analysis_config:global"
        current_config = {
            "analysis_model": "deepseek.DeepSeek_V3",
            "vision_model": "ollama.Qwen2_5_VL_7B",
            "timeout": 600
        }
        
        if redis_client:
            try:
                saved_config = redis_client.get(config_key)
                if saved_config:
                    current_config.update(json.loads(saved_config))
            except Exception as e:
                logger.warning(f"读取Redis配置失败: {e}")
        
        # 获取可用模型列表
        available_models = factory.get_available_llm_models()
        vision_models = factory.get_available_vision_models()
        
        return jsonify({
            'success': True,
            'data': {
                'current_config': current_config,
                'available_models': {
                    'analysis_models': available_models,
                    'vision_models': vision_models
                }
            }
        })
        
    except Exception as e:
        logger.error(f"获取分析配置失败: {e}")
        return jsonify({
            'success': False,
            'error': f"获取配置失败: {str(e)}"
        }), 500


@api_bp.route('/analysis/config', methods=['POST'])
def save_analysis_config():
    """保存深度分析配置"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': '请求数据不能为空'
            }), 400
        
        # 验证必要字段
        analysis_model = data.get('analysis_model')
        vision_model = data.get('vision_model')
        timeout = data.get('timeout', 600)
        
        if not analysis_model or not vision_model:
            return jsonify({
                'success': False,
                'error': '分析模型和视觉模型不能为空'
            }), 400
        
        # 构建配置
        config = {
            'analysis_model': analysis_model,
            'vision_model': vision_model,
            'timeout': timeout
        }
        
        # 保存到Redis
        config_key = "analysis_config:global"
        if redis_client:
            try:
                redis_client.set(config_key, json.dumps(config))
                logger.info(f"配置已保存到Redis: {config}")
            except Exception as e:
                logger.error(f"保存配置到Redis失败: {e}")
                return jsonify({
                    'success': False,
                    'error': f'保存配置失败: {str(e)}'
                }), 500
        
        return jsonify({
            'success': True,
            'message': '配置保存成功',
            'config': config
        })
        
    except Exception as e:
        logger.error(f"保存分析配置失败: {e}")
        return jsonify({
            'success': False,
            'error': f"保存配置失败: {str(e)}"
        }), 500


# === 深度分析管理API ===

@api_bp.route('/analysis/paper/<arxiv_id>/cancel', methods=['POST'])
def api_cancel_analysis(arxiv_id):
    """取消正在进行的深度分析"""
    try:
        result = analysis_service.cancel_analysis(arxiv_id)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"取消分析失败 {arxiv_id}: {e}")
        return jsonify({
            'success': False,
            'error': f"取消分析失败: {str(e)}"
        }), 500


@api_bp.route('/analysis/paper/<arxiv_id>/reset', methods=['POST'])
def api_reset_analysis_status(arxiv_id):
    """重置深度分析状态"""
    try:
        result = analysis_service.reset_analysis_status(arxiv_id)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"重置分析状态失败 {arxiv_id}: {e}")
        return jsonify({
            'success': False,
            'error': f"重置状态失败: {str(e)}"
        }), 500


@api_bp.route('/analysis/recover', methods=['POST'])
def api_recover_interrupted_analysis():
    """恢复被中断的深度分析任务"""
    try:
        result = paper_explore_service.recover_interrupted_analysis()
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"恢复中断分析失败: {e}")
        return jsonify({
            'success': False,
            'error': f"恢复失败: {str(e)}"
        }), 500


@api_bp.route('/analysis/reset_stuck', methods=['POST'])
def api_reset_stuck_analysis():
    """重置卡住的深度分析任务"""
    try:
        data = request.get_json() if request.is_json else {}
        max_hours = data.get('max_hours', 2)
        
        # 验证参数
        if max_hours <= 0 or max_hours > 24:
            return jsonify({
                'success': False,
                'error': '最大小时数必须在1-24之间'
            }), 400
        
        result = paper_explore_service.reset_stuck_analysis(max_hours)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"重置卡住分析失败: {e}")
        return jsonify({
            'success': False,
            'error': f"重置失败: {str(e)}"
        }), 500


@api_bp.route('/analysis/batch_reset', methods=['POST'])
def api_batch_reset_analysis_status():
    """批量重置深度分析状态"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': '请求数据不能为空'
            }), 400
        
        arxiv_ids = data.get('arxiv_ids', [])
        status = data.get('status', 'pending')
        
        if not arxiv_ids:
            return jsonify({
                'success': False,
                'error': '论文ID列表不能为空'
            }), 400
        
        result = paper_explore_service.batch_reset_analysis_status(arxiv_ids, status)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"批量重置分析状态失败: {e}")
        return jsonify({
            'success': False,
            'error': f"批量重置失败: {str(e)}"
        }), 500


@api_bp.route('/analysis/statistics')
def api_analysis_statistics():
    """获取深度分析统计信息"""
    try:
        result = paper_explore_service.get_analysis_statistics()
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 500
            
    except Exception as e:
        logger.error(f"获取分析统计失败: {e}")
        return jsonify({
            'success': False,
            'error': f"获取统计失败: {str(e)}"
        }), 500


@api_bp.route('/settings/save', methods=['POST'])
def save_settings():
    """保存系统设置（模型设置和深度分析设置）"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': '请求数据不能为空'
            }), 400
        
        # 验证必要字段
        llm_model_name = data.get('llm_model_name')
        if not llm_model_name:
            return jsonify({
                'success': False,
                'error': 'LLM模型名称不能为空'
            }), 400
        
        # 构建配置
        config = {
            # LLM配置
            'llm_model_name': llm_model_name,
            'relevance_threshold': data.get('relevance_threshold', 0.7),
            'abstract_analysis_model': data.get('abstract_analysis_model'),
            'full_paper_analysis_model': data.get('full_paper_analysis_model'),
            'deep_analysis_model': data.get('deep_analysis_model'),
            'vision_model': data.get('vision_model'),
            'video_analysis_model': data.get('video_analysis_model'),
            
            # 深度分析配置
            'enable_deep_analysis': data.get('enable_deep_analysis', True),
            'enable_video_analysis': data.get('enable_video_analysis', False),
            'deep_analysis_threshold': data.get('deep_analysis_threshold', 0.8),
            'ocr_char_limit_for_analysis': data.get('ocr_char_limit_for_analysis', 10000),
            'analysis_timeout': data.get('analysis_timeout', 600),
            
            # 远程OCR配置
            'enable_remote_ocr': data.get('enable_remote_ocr', False),
            'remote_ocr_endpoint': data.get('remote_ocr_endpoint', 'http://localhost:5001'),
            'remote_ocr_timeout': data.get('remote_ocr_timeout', 300),
            'remote_ocr_max_pages': data.get('remote_ocr_max_pages', 25)
        }
        
        # 保存到Redis
        config_key = "system_settings:global"
        if redis_client:
            try:
                redis_client.set(config_key, json.dumps(config))
                logger.info(f"系统设置已保存到Redis: {config}")
            except Exception as e:
                logger.error(f"保存系统设置到Redis失败: {e}")
                return jsonify({
                    'success': False,
                    'error': f'保存设置失败: {str(e)}'
                }), 500
        
        return jsonify({
            'success': True,
            'message': '设置保存成功',
            'config': config
        })
        
    except Exception as e:
        logger.error(f"保存系统设置失败: {e}")
        return jsonify({
            'success': False,
            'error': f"保存设置失败: {str(e)}"
        }), 500


@api_bp.route('/settings/load', methods=['GET'])
def load_settings():
    """加载系统设置"""
    try:
        config_key = "system_settings:global"
        config = {}
        
        if redis_client:
            try:
                config_data = redis_client.get(config_key)
                if config_data:
                    config = json.loads(config_data)
                    logger.info(f"从Redis加载系统设置: {config}")
            except Exception as e:
                logger.error(f"从Redis加载系统设置失败: {e}")
        
        return jsonify({
            'success': True,
            'config': config
        })
        
    except Exception as e:
        logger.error(f"加载系统设置失败: {e}")
        return jsonify({
            'success': False,
            'error': f"加载设置失败: {str(e)}"
        }), 500


# === 任务历史管理相关API ===

@api_bp.route('/task/details/<task_id>')
def get_task_details(task_id):
    """获取任务详细信息 - 用于前端模态框显示"""
    try:
        result = paper_gather_service.get_task_result(task_id)
        if not result:
            return jsonify({
                'success': False,
                'error': '任务不存在'
            }), 404
        
        return jsonify({
            'success': True,
            'data': result
        })
    except Exception as e:
        logger.error(f"获取任务详情失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500



@api_bp.route('/task/history')
def get_task_history():
    """获取任务历史列表"""
    try:
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('per_page', 50)), 100)
        
        # 获取任务历史
        tasks = paper_gather_service.get_task_history(limit=per_page * 5)  # 获取更多数据用于分页
        
        # 计算分页
        total = len(tasks)
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_tasks = tasks[start_idx:end_idx]
        
        return jsonify({
            'success': True,
            'data': {
                'tasks': paginated_tasks,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': total,
                    'total_pages': (total + per_page - 1) // per_page
                }
            }
        })
    
    except Exception as e:
        logger.error(f"获取任务历史失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route('/task/history/<task_id>', methods=['DELETE'])
def delete_task_history(task_id):
    """删除历史任务"""
    try:
        success, error_msg = paper_gather_service.delete_task_history(task_id)
        
        if success:
            return jsonify({
                'success': True,
                'message': '任务删除成功'
            })
        else:
            return jsonify({
                'success': False,
                'error': error_msg or '删除失败'
            }), 400
    
    except Exception as e:
        logger.error(f"删除任务历史失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route('/task/config/<task_id>')
def get_task_config(task_id):
    """获取特定任务的配置"""
    try:
        # 获取任务配置
        task_config = paper_gather_service.get_task_config_by_id(task_id)
        
        if not task_config:
            return jsonify({
                'success': False,
                'error': '任务不存在'
            }), 404
        
        return jsonify({
            'success': True,
            'data': {
                'task_id': task_id,
                'config': task_config
            }
        })
    
    except Exception as e:
        logger.error(f"获取任务配置失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route('/config/presets')
def get_config_presets():
    """获取配置预设列表"""
    try:
        # 返回空的预设列表（可以后续扩展）
        return jsonify({
            'success': True,
            'data': {
                'presets': []
            }
        })
    
    except Exception as e:
        logger.error(f"获取配置预设失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route('/config/presets', methods=['POST'])
def create_config_preset():
    """创建配置预设"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': '请求数据不能为空'
            }), 400
        
        # 目前返回成功但不实际保存（可以后续扩展）
        return jsonify({
            'success': True,
            'message': '预设创建成功（功能暂未完全实现）',
            'preset_id': 'temp_id'
        })
    
    except Exception as e:
        logger.error(f"创建配置预设失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route('/config/presets/<preset_id>', methods=['DELETE'])
def delete_config_preset(preset_id):
    """删除配置预设"""
    try:
        # 目前返回成功但不实际删除（可以后续扩展）
        return jsonify({
            'success': True,
            'message': '预设删除成功（功能暂未完全实现）'
        })
    
    except Exception as e:
        logger.error(f"删除配置预设失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route('/models')
def get_models():
    """获取可用的LLM模型列表"""
    try:
        models = paper_gather_service.get_available_models()
        return jsonify({
            'success': True,
            'data': models
        })
    except Exception as e:
        logger.error(f"获取模型列表失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# === 系统状态相关API ===

@api_bp.route('/running_tasks')
def get_running_tasks():
    """获取运行中任务状态 - 用于首页实时更新"""
    try:
        # 获取运行中任务数量和详情
        running_count = paper_gather_service.get_running_tasks_count()
        running_details = paper_gather_service.get_running_tasks_detail()
        
        return jsonify({
            'success': True,
            'data': {
                'count': running_count,
                'details': running_details
            }
        })
    except Exception as e:
        logger.error(f"获取运行中任务失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route('/system_stats')
def get_system_stats():
    """获取系统核心统计数据 - 用于首页展示卡片"""
    try:
        # 获取论文收集统计
        collect_stats = paper_data_service.get_paper_statistics()
        
        # 获取运行中任务数量
        running_tasks_count = paper_gather_service.get_running_tasks_count()
        
        # 获取定时任务数量
        scheduled_tasks = paper_gather_service.get_scheduled_tasks()
        scheduled_count = len(scheduled_tasks) if scheduled_tasks else 0
        
        # 构建核心统计数据
        core_stats = {
            'total_papers': collect_stats.get('total_papers', 0),
            'analyzed_papers': collect_stats.get('analyzed_papers', 0),
            'running_tasks': running_tasks_count,
            'scheduled_tasks': scheduled_count
        }
        
        return jsonify({
            'success': True,
            'data': core_stats
        })
    except Exception as e:
        logger.error(f"获取系统统计数据失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route('/tasks/status')
def get_tasks_status():
    """获取所有活动任务的状态 - 用于前端定时刷新"""
    try:
        # 获取运行中任务详情
        running_tasks = paper_gather_service.get_running_tasks_detail()
        
        # 格式化任务状态数据供前端使用
        status_data = []
        for task in running_tasks:
            status_data.append({
                'task_id': task.get('task_id', ''),
                'status': task.get('status', 'unknown'),
                'progress': task.get('progress', 0.0),
                'start_time': task.get('start_time'),
                'duration': task.get('duration')
            })
        
        return jsonify({
            'success': True,
            'data': status_data
        })
    except Exception as e:
        logger.error(f"获取任务状态失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ========== 关于页面系统状态相关API ==========

@api_bp.route('/about/system_status')
def get_about_system_status():
    """获取关于页面的系统状态信息"""
    try:
        import os
        import sys
        import redis
        import requests
        from datetime import datetime
        
        status_info = {
            'timestamp': datetime.now().isoformat(),
            'database': {'postgresql': False, 'redis': False},
            'llm_services': {'available_count': 0, 'total_providers': 0},
            'external_services': {
                'siyuan': False,
                'dify': False, 
                'ollama': False
            }
        }
        
        # 检测数据库连接状态
        try:
            import psycopg2
            postgres_config = {
                'host': os.getenv('DB_HOST', 'localhost'),
                'port': int(os.getenv('DB_PORT', 5432)),
                'database': os.getenv('DB_NAME', 'homesystem'),
                'user': os.getenv('DB_USER', 'homesystem'),
                'password': os.getenv('DB_PASSWORD', 'homesystem123'),
            }
            conn = psycopg2.connect(**postgres_config)
            conn.close()
            status_info['database']['postgresql'] = True
        except Exception as e:
            logger.debug(f"PostgreSQL连接检测失败: {e}")
        
        # 检测Redis连接状态
        try:
            redis_host = os.getenv('REDIS_HOST', 'localhost')
            redis_port = int(os.getenv('REDIS_PORT', 6379))
            r = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
            r.ping()
            status_info['database']['redis'] = True
        except Exception as e:
            logger.debug(f"Redis连接检测失败: {e}")
        
        # 检测LLM服务状态
        try:
            # 动态检测可用的API Key和准确的模型数量
            llm_providers = {
                'deepseek': (os.getenv('DEEPSEEK_API_KEY'), 2),  # DeepSeek V3 + R1
                'siliconflow': (os.getenv('SILICONFLOW_API_KEY'), 6),  # 6个聊天模型
                'volcano': (os.getenv('VOLCANO_API_KEY'), 3),  # 豆包3个版本
                'moonshot': (os.getenv('MOONSHOT_API_KEY'), 2),  # Kimi K2 + V1
                'dashscope': (os.getenv('DASHSCOPE_API_KEY'), 5),  # 阿里云5个模型
                'zhipuai': (os.getenv('ZHIPUAI_API_KEY'), 2),  # GLM-4.5 + Air
                'ollama': (os.getenv('OLLAMA_BASE_URL'), 4),  # 4个本地模型
                'openai': (os.getenv('OPENAI_API_KEY'), 0)  # 仅embedding
            }
            
            available_providers = []
            model_count = 0
            embedding_count = 0
            
            for provider, (key, models) in llm_providers.items():
                if key and not key.startswith('your_'):
                    available_providers.append(provider)
                    model_count += models
                    
                    # 计算embedding模型
                    if provider == 'siliconflow':
                        embedding_count += 1
                    elif provider == 'ollama':
                        embedding_count += 3
                    elif provider == 'openai':
                        embedding_count += 2
            
            status_info['llm_services']['available_count'] = model_count
            status_info['llm_services']['embedding_count'] = embedding_count
            status_info['llm_services']['total_providers'] = len(available_providers)
            status_info['llm_services']['providers'] = available_providers
        except Exception as e:
            logger.debug(f"LLM服务检测失败: {e}")
        
        # 检测外部服务状态
        # SiYuan
        try:
            siyuan_url = os.getenv('SIYUAN_API_URL', 'http://192.168.5.54:6806')
            response = requests.get(f"{siyuan_url}/api/system/getConf", timeout=3)
            if response.status_code == 200:
                status_info['external_services']['siyuan'] = True
        except Exception as e:
            logger.debug(f"SiYuan连接检测失败: {e}")
        
        # Dify - 修复检测逻辑
        try:
            dify_url = os.getenv('DIFY_BASE_URL', 'http://192.168.5.54:5001')
            # Dify可能没有标准的health-check端点，尝试访问根路径或API端点
            try:
                # 先尝试根路径
                response = requests.get(dify_url, timeout=3)
                if response.status_code in [200, 301, 302, 404]:  # 这些状态码表示服务在运行
                    status_info['external_services']['dify'] = True
                else:
                    raise Exception(f"根路径返回状态码: {response.status_code}")
            except Exception:
                # 如果根路径失败，尝试API端点
                response = requests.get(f"{dify_url}/v1/info", timeout=3)
                if response.status_code in [200, 401, 403]:  # 包括认证错误，说明服务在运行
                    status_info['external_services']['dify'] = True
        except Exception as e:
            logger.debug(f"Dify连接检测失败: {e}")
        
        # Ollama
        try:
            ollama_url = os.getenv('OLLAMA_BASE_URL', 'http://192.168.5.217:11434')
            response = requests.get(f"{ollama_url}/api/tags", timeout=3)
            if response.status_code == 200:
                status_info['external_services']['ollama'] = True
        except Exception as e:
            logger.debug(f"Ollama连接检测失败: {e}")
        
        return jsonify({
            'success': True,
            'data': status_info
        })
        
    except Exception as e:
        logger.error(f"获取系统状态失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

async def validate_api_token(provider_config: dict, timeout: int = 5) -> bool:
    """验证API token是否实际可用"""
    try:
        api_key_env = provider_config.get('api_key_env')
        if not api_key_env:
            # Ollama等本地服务不需要API key，检查URL连通性
            base_url = os.getenv(provider_config.get('base_url_env', ''), provider_config.get('base_url', ''))
            if base_url:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.get(f"{base_url}/api/tags" if 'ollama' in base_url else base_url)
                    return response.status_code < 500
            return False
        
        api_key = os.getenv(api_key_env)
        if not api_key or api_key.startswith('your_'):
            return False
        
        base_url = os.getenv(provider_config.get('base_url_env', ''), provider_config.get('base_url'))
        
        # 根据不同供应商进行实际API调用测试
        async with httpx.AsyncClient(timeout=timeout) as client:
            headers = {'Authorization': f'Bearer {api_key}'}
            
            if 'deepseek' in base_url.lower():
                response = await client.get(f"{base_url}/models", headers=headers)
            elif 'siliconflow' in base_url.lower():
                response = await client.get(f"{base_url}/models", headers=headers)
            elif 'moonshot' in base_url.lower():
                response = await client.get(f"{base_url}/models", headers=headers)
            elif 'bigmodel' in base_url.lower():
                # 智谱AI
                response = await client.post(f"{base_url}/chat/completions", 
                    headers=headers, 
                    json={"model": "glm-4.5", "messages": [{"role": "user", "content": "test"}], "max_tokens": 1})
            elif 'dashscope' in base_url.lower():
                # 阿里云
                response = await client.get(f"{base_url}/models", headers=headers)
            elif 'volces' in base_url.lower():
                # 火山引擎
                response = await client.post(f"{base_url}/chat/completions",
                    headers=headers,
                    json={"model": "doubao-seed-1.6", "messages": [{"role": "user", "content": "test"}], "max_tokens": 1})
            else:
                # 通用OpenAI兼容测试
                response = await client.get(f"{base_url}/models", headers=headers)
            
            return response.status_code < 400
            
    except Exception as e:
        logger.debug(f"API token validation failed for {provider_config.get('name', 'unknown')}: {e}")
        return False

def load_llm_config() -> dict:
    """加载LLM配置文件"""
    try:
        # Try Docker path first (2 parents: /app/routes/api.py -> /app/HomeSystem/...)
        config_path = Path(__file__).parent.parent / 'HomeSystem' / 'graph' / 'config' / 'llm_providers.yaml'
        
        # If Docker path doesn't exist, try local development path (4 parents)
        if not config_path.exists():
            config_path = Path(__file__).parent.parent.parent.parent / 'HomeSystem' / 'graph' / 'config' / 'llm_providers.yaml'
        
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"加载LLM配置失败: {e}")
        return {}


@api_bp.route('/about/llm_models')  
def get_about_llm_models():
    """获取所有可用的LLM模型详细信息，通过实际API调用验证可用性"""
    try:
        # 加载完整的LLM配置
        config = load_llm_config()
        if not config:
            return jsonify({
                'success': False,
                'error': '无法加载LLM配置文件'
            }), 500
        
        providers_data = {}
        total_chat_models = 0
        total_embedding_models = 0
        
        # 验证API token可用性的异步函数包装器
        async def validate_all_providers():
            validation_results = {}
            
            # 验证所有LLM提供商
            for provider_key, provider_config in config.get('providers', {}).items():
                is_available = await validate_api_token(provider_config)
                validation_results[provider_key] = is_available
            
            # 验证所有Embedding提供商
            for provider_key, provider_config in config.get('embedding_providers', {}).items():
                is_available = await validate_api_token(provider_config)
                validation_results[f"{provider_key}_embedding"] = is_available
            
            return validation_results
        
        # 运行验证
        validation_results = asyncio.run(validate_all_providers())
        
        # DeepSeek
        if os.getenv('DEEPSEEK_API_KEY') and not os.getenv('DEEPSEEK_API_KEY').startswith('your_'):
            providers_data['deepseek'] = {
                'name': 'DeepSeek',
                'chat_models': [
                    {
                        'key': 'deepseek.DeepSeek_V3',
                        'name': 'deepseek-chat',
                        'display_name': 'DeepSeek V3',
                        'description': 'MoE架构，14.8万亿token训练，671B总参数/37B激活',
                        'max_tokens': 131072,
                        'supports_functions': True,
                        'supports_vision': False,
                        'supports_thinking': False
                    },
                    {
                        'key': 'deepseek.DeepSeek_R1',
                        'name': 'deepseek-reasoner',
                        'display_name': 'DeepSeek R1',
                        'description': '最新推理模型，AIME 2025达87.5%准确率',
                        'max_tokens': 131072,
                        'supports_functions': True,
                        'supports_vision': False,
                        'supports_thinking': True
                    }
                ],
                'embedding_models': []
            }
            total_chat_models += 2

        # SiliconFlow
        if os.getenv('SILICONFLOW_API_KEY') and not os.getenv('SILICONFLOW_API_KEY').startswith('your_'):
            providers_data['siliconflow'] = {
                'name': 'SiliconFlow (硅基流动)',
                'chat_models': [
                    {
                        'key': 'siliconflow.DeepSeek_R1',
                        'name': 'deepseek-ai/DeepSeek-R1',
                        'display_name': 'DeepSeek R1',
                        'description': '通过硅基流动提供的DeepSeek R1推理优化版本',
                        'max_tokens': 131072,
                        'supports_functions': True,
                        'supports_vision': False,
                        'supports_thinking': True
                    },
                    {
                        'key': 'siliconflow.DeepSeek_V3',
                        'name': 'deepseek-ai/DeepSeek-V3',
                        'display_name': 'DeepSeek V3',
                        'description': '通过硅基流动提供的DeepSeek V3，671B总参数/37B激活',
                        'max_tokens': 131072,
                        'supports_functions': True,
                        'supports_vision': False,
                        'supports_thinking': False
                    },
                    {
                        'key': 'siliconflow.QwQ_32B',
                        'name': 'Qwen/QwQ-32B-Preview',
                        'display_name': '通义千问 QwQ-32B',
                        'description': '阿里通义千问推理增强版本，32B参数',
                        'max_tokens': 32768,
                        'supports_functions': True,
                        'supports_vision': False,
                        'supports_thinking': True
                    },
                    {
                        'key': 'siliconflow.Qwen2_5_72B',
                        'name': 'Qwen/Qwen2.5-72B-Instruct',
                        'display_name': '通义千问 2.5-72B',
                        'description': '通义千问2.5系列最强版本，72B参数',
                        'max_tokens': 131072,
                        'supports_functions': True,
                        'supports_vision': False,
                        'supports_thinking': False
                    },
                    {
                        'key': 'siliconflow.Qwen3_235B_A22B',
                        'name': 'Qwen/Qwen3-235B-A22B-Instruct-2507',
                        'display_name': '通义千问 3-235B-A22B',
                        'description': '通义千问3系列最强版本，235B参数，支持256K上下文',
                        'max_tokens': 10240,
                        'supports_functions': True,
                        'supports_vision': False,
                        'supports_thinking': False
                    },
                    {
                        'key': 'siliconflow.Qwen3_235B_A22B_Thinking',
                        'name': 'Qwen/Qwen3-235B-A22B-Thinking-2507',
                        'display_name': '通义千问 3-235B-A22B-思考版',
                        'description': '通义千问3系列最强思考版本，235B参数',
                        'max_tokens': 10240,
                        'supports_functions': True,
                        'supports_vision': False,
                        'supports_thinking': True
                    }
                ],
                'embedding_models': [
                    {
                        'key': 'siliconflow.BGE_Large_ZH_V1_5',
                        'name': 'BAAI/bge-large-zh-v1.5',
                        'display_name': 'BGE Large 中文 v1.5',
                        'description': '中文优化的embedding模型，326M参数',
                        'dimensions': 1024,
                        'max_input': 512
                    }
                ]
            }
            total_chat_models += 6
            total_embedding_models += 1

        # Volcano Engine (豆包)
        if os.getenv('VOLCANO_API_KEY') and not os.getenv('VOLCANO_API_KEY').startswith('your_'):
            providers_data['volcano'] = {
                'name': 'Volcano Engine (豆包)',
                'chat_models': [
                    {
                        'key': 'volcano.Doubao_1_6',
                        'name': 'doubao-seed-1.6',
                        'display_name': '豆包1.6 全能版',
                        'description': 'All-in-One综合模型，支持深度思考和多模态，256K上下文',
                        'max_tokens': 16384,
                        'supports_functions': True,
                        'supports_vision': False,
                        'supports_thinking': True
                    },
                    {
                        'key': 'volcano.Doubao_1_6_Thinking',
                        'name': 'doubao-seed-1.6-thinking',
                        'display_name': '豆包1.6 深度思考版',
                        'description': '深度思考强化版，数学推理能力突出，256K上下文',
                        'max_tokens': 16384,
                        'supports_functions': True,
                        'supports_vision': False,
                        'supports_thinking': True
                    },
                    {
                        'key': 'volcano.Doubao_1_6_Flash',
                        'name': 'doubao-seed-1.6-flash',
                        'display_name': '豆包1.6 极速版',
                        'description': '极低延迟版本，TOPT仅需10ms，支持256K上下文',
                        'max_tokens': 16384,
                        'supports_functions': True,
                        'supports_vision': False,
                        'supports_thinking': False
                    }
                ],
                'embedding_models': []
            }
            total_chat_models += 3

        # Moonshot (Kimi)
        if os.getenv('MOONSHOT_API_KEY') and not os.getenv('MOONSHOT_API_KEY').startswith('your_'):
            providers_data['moonshot'] = {
                'name': 'MoonShot (月之暗面)',
                'chat_models': [
                    {
                        'key': 'moonshot.Kimi_K2',
                        'name': 'kimi-k2-0711-preview',
                        'display_name': 'Kimi K2',
                        'description': '万亿参数MoE智能体模型，专注代码和推理，1T总参数/32B激活',
                        'max_tokens': 16384,
                        'supports_functions': True,
                        'supports_vision': False,
                        'supports_thinking': False
                    },
                    {
                        'key': 'moonshot.Kimi_V1_128K',
                        'name': 'moonshot-v1-128k',
                        'display_name': 'Kimi v1 128K',
                        'description': '长上下文处理专用版本，支持128K上下文',
                        'max_tokens': 16384,
                        'supports_functions': True,
                        'supports_vision': False,
                        'supports_thinking': False
                    }
                ],
                'embedding_models': []
            }
            total_chat_models += 2

        # ZhipuAI (智谱AI)
        if os.getenv('ZHIPUAI_API_KEY') and not os.getenv('ZHIPUAI_API_KEY').startswith('your_'):
            providers_data['zhipuai'] = {
                'name': 'ZhipuAI (智谱AI)',
                'chat_models': [
                    {
                        'key': 'zhipuai.GLM_4_5',
                        'name': 'glm-4.5',
                        'display_name': 'GLM-4.5',
                        'description': '智能体原生旗舰模型，MoE架构，全球排名第3，355B总参数/32B激活',
                        'max_tokens': 32768,
                        'supports_functions': True,
                        'supports_vision': False,
                        'supports_thinking': False
                    },
                    {
                        'key': 'zhipuai.GLM_4_5_Air',
                        'name': 'glm-4.5-air',
                        'display_name': 'GLM-4.5-Air',
                        'description': '轻量化版本，高效智能体模型，106B总参数/12B激活，性能评分59.8',
                        'max_tokens': 32768,
                        'supports_functions': True,
                        'supports_vision': False,
                        'supports_thinking': False
                    }
                ],
                'embedding_models': []
            }
            total_chat_models += 2

        # Alibaba (阿里云)
        if os.getenv('DASHSCOPE_API_KEY') and not os.getenv('DASHSCOPE_API_KEY').startswith('your_'):
            providers_data['alibaba'] = {
                'name': 'Alibaba Cloud (阿里云)',
                'chat_models': [
                    {
                        'key': 'alibaba.Qwen_Turbo_Latest',
                        'name': 'qwen-turbo-latest',
                        'display_name': '通义千问 Turbo 最新版',
                        'description': '最新版Turbo模型，支持思考模式，速度最快成本最低，适合简单任务',
                        'max_tokens': 8192,
                        'supports_functions': True,
                        'supports_vision': False,
                        'supports_thinking': True
                    },
                    {
                        'key': 'alibaba.Qwen_Turbo',
                        'name': 'qwen-turbo',
                        'display_name': '通义千问 Turbo',
                        'description': '高效轻量级模型，速度快成本低，适合日常对话和简单任务',
                        'max_tokens': 8192,
                        'supports_functions': True,
                        'supports_vision': False,
                        'supports_thinking': False
                    },
                    {
                        'key': 'alibaba.Qwen_Plus',
                        'name': 'qwen-plus',
                        'display_name': '通义千问 Plus',
                        'description': '平衡性能与成本的模型，支持思考模式，适合复杂推理任务',
                        'max_tokens': 32768,
                        'supports_functions': True,
                        'supports_vision': False,
                        'supports_thinking': True
                    },
                    {
                        'key': 'alibaba.Qwen3_235B_A22B',
                        'name': 'qwen3-235b-a22b-instruct-2507',
                        'display_name': '通义千问 3-235B-A22B',
                        'description': '通义千问3系列最强版本，MoE架构，支持256K上下文，235B参数',
                        'max_tokens': 32768,
                        'supports_functions': True,
                        'supports_vision': False,
                        'supports_thinking': False
                    },
                    {
                        'key': 'alibaba.Qwen3_235B_A22B_Thinking',
                        'name': 'qwen3-235b-a22b-thinking-2507',
                        'display_name': '通义千问 3-235B-A22B-思考版',
                        'description': '专门的思考模式模型，支持80K推理过程长度，在复杂推理任务上表现卓越',
                        'max_tokens': 32768,
                        'supports_functions': True,
                        'supports_vision': False,
                        'supports_thinking': True
                    }
                ],
                'embedding_models': []
            }
            total_chat_models += 5

        # Ollama (本地)
        if os.getenv('OLLAMA_BASE_URL'):
            providers_data['ollama'] = {
                'name': 'Ollama (本地部署)',
                'chat_models': [
                    {
                        'key': 'ollama.DeepSeek_R1_14B',
                        'name': 'deepseek-r1:14b',
                        'display_name': 'DeepSeek R1 14B',
                        'description': 'DeepSeek推理模型14B版本，支持128K上下文',
                        'max_tokens': 32768,
                        'supports_functions': False,
                        'supports_vision': False,
                        'supports_thinking': True
                    },
                    {
                        'key': 'ollama.Qwen2_5_VL_7B',
                        'name': 'qwen2.5vl:7b',
                        'display_name': '通义千问 2.5-VL-7B (视觉)',
                        'description': '通义千问2.5系列7B版本，支持视觉和图片分析',
                        'max_tokens': 32768,
                        'supports_functions': False,
                        'supports_vision': True,
                        'supports_thinking': False
                    },
                    {
                        'key': 'ollama.Qwen3_30B',
                        'name': 'qwen3:30b',
                        'display_name': '通义千问3 30B',
                        'description': 'MoE架构代码专用模型，多语言支持，支持128K上下文',
                        'max_tokens': 32768,
                        'supports_functions': False,
                        'supports_vision': False,
                        'supports_thinking': False
                    },
                    {
                        'key': 'ollama.gpt-oss',
                        'name': 'gpt-oss',
                        'display_name': 'Open AI GPT OSS',
                        'description': 'MoE架构代码专用模型，多语言支持，支持128K上下文，20B参数',
                        'max_tokens': 32768,
                        'supports_functions': False,
                        'supports_vision': False,
                        'supports_thinking': False
                    }
                ],
                'embedding_models': [
                    {
                        'key': 'ollama.BGE_M3',
                        'name': 'bge-m3:latest',
                        'display_name': 'BGE-M3',
                        'description': 'BAAI开源的多语言embedding模型，支持中英文，560M参数',
                        'dimensions': 1024,
                        'max_input': 8192
                    },
                    {
                        'key': 'ollama.Nomic_Embed_Text',
                        'name': 'nomic-embed-text:latest',
                        'display_name': 'Nomic Embed Text',
                        'description': '高效的英文文本embedding模型，137M参数',
                        'dimensions': 768,
                        'max_input': 2048
                    },
                    {
                        'key': 'ollama.MxBai_Embed_Large',
                        'name': 'mxbai-embed-large:latest',
                        'display_name': 'MxBai Embed Large',
                        'description': '高质量的通用embedding模型，335M参数',
                        'dimensions': 1024,
                        'max_input': 512
                    }
                ]
            }
            total_chat_models += 4
            total_embedding_models += 3

        # OpenAI (如果配置了的话)
        if os.getenv('OPENAI_API_KEY') and not os.getenv('OPENAI_API_KEY').startswith('your_'):
            providers_data['openai'] = {
                'name': 'OpenAI',
                'chat_models': [],
                'embedding_models': [
                    {
                        'key': 'openai.Text_Embedding_3_Large',
                        'name': 'text-embedding-3-large',
                        'display_name': 'Text Embedding 3 Large',
                        'description': 'OpenAI最新大型embedding模型',
                        'dimensions': 3072,
                        'max_input': 8191
                    },
                    {
                        'key': 'openai.Text_Embedding_3_Small',
                        'name': 'text-embedding-3-small',
                        'display_name': 'Text Embedding 3 Small',
                        'description': 'OpenAI紧凑型embedding模型',
                        'dimensions': 1536,
                        'max_input': 8191
                    }
                ]
            }
            total_embedding_models += 2
        
        return jsonify({
            'success': True,
            'data': {
                'providers': providers_data,
                'total_chat_models': total_chat_models,
                'total_embedding_models': total_embedding_models,
                'total_providers': len(providers_data)
            }
        })
        
    except Exception as e:
        logger.error(f"获取LLM模型列表失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ========== 迁移和任务管理相关API ==========

@api_bp.route('/tasks/available_for_migration')
def api_get_available_tasks_for_migration():
    """获取可用于迁移的任务列表"""
    try:
        tasks = paper_explore_service.get_available_tasks()
        return jsonify({'success': True, 'data': {'tasks': tasks}})
    
    except Exception as e:
        logger.error(f"获取迁移任务列表失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/get_tasks')
def api_get_tasks():
    """获取所有任务列表（用于批量操作）"""
    try:
        tasks_data = paper_explore_service.get_available_tasks()
        # 将复杂的数据结构转换为简单的任务数组，供批量操作使用
        all_tasks = []
        
        # 添加基于任务名称的任务
        for task in tasks_data.get('task_names', []):
            all_tasks.append({
                'task_name': task['task_name'],
                'task_id': '',  # task_names中没有task_id
                'paper_count': task['paper_count'],
                'created_at': None  # task_names中没有时间信息
            })
        
        # 添加基于任务ID的任务（避免重复）
        task_name_set = {task['task_name'] for task in all_tasks}
        for task in tasks_data.get('task_ids', []):
            if task['task_name'] not in task_name_set:
                all_tasks.append({
                    'task_name': task['task_name'],
                    'task_id': task['task_id'],
                    'paper_count': task['paper_count'],
                    'created_at': task.get('last_created')  # 使用last_created作为展示时间
                })
        
        return jsonify({'success': True, 'tasks': all_tasks})
    
    except Exception as e:
        logger.error(f"获取任务列表失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/migrate_paper_to_task', methods=['POST'])
def api_migrate_paper_to_task():
    """单个论文迁移到新任务"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': '无效的请求数据'}), 400
        
        arxiv_id = data.get('arxiv_id')
        target_task_name = data.get('target_task_name', '').strip()
        target_task_id = data.get('target_task_id', '').strip()
        
        if not arxiv_id or not target_task_name:
            return jsonify({'success': False, 'error': '缺少必要参数'}), 400
        
        success = paper_explore_service.migrate_paper_to_task(
            arxiv_id, target_task_name, target_task_id or None
        )
        
        if success:
            return jsonify({'success': True, 'message': '论文迁移成功'})
        else:
            return jsonify({'success': False, 'error': '迁移失败，论文不存在'}), 404
    
    except Exception as e:
        logger.error(f"论文迁移失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/batch_migrate_to_task', methods=['POST'])
def api_batch_migrate_to_task():
    """批量论文迁移到新任务"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': '无效的请求数据'}), 400
        
        arxiv_ids = data.get('arxiv_ids', [])
        target_task_name = data.get('target_task_name', '').strip()
        target_task_id = data.get('target_task_id', '').strip()
        
        if not arxiv_ids or not target_task_name:
            return jsonify({'success': False, 'error': '缺少必要参数'}), 400
        
        affected_rows = paper_explore_service.batch_migrate_papers_to_task(
            arxiv_ids, target_task_name, target_task_id or None
        )
        
        return jsonify({
            'success': True, 
            'affected_rows': affected_rows,
            'message': f'成功迁移 {affected_rows} 篇论文'
        })
    
    except Exception as e:
        logger.error(f"批量迁移失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/assign_task_to_paper', methods=['POST'])
def api_assign_task_to_paper():
    """为论文分配任务"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': '无效的请求数据'}), 400
        
        arxiv_id = data.get('arxiv_id')
        task_name = data.get('task_name', '').strip()
        task_id = data.get('task_id', '').strip()
        
        if not arxiv_id or not task_name:
            return jsonify({'success': False, 'error': '缺少必要参数'}), 400
        
        success = paper_explore_service.assign_task_to_paper(
            arxiv_id, task_name, task_id or None
        )
        
        if success:
            return jsonify({'success': True, 'message': '任务分配成功'})
        else:
            return jsonify({'success': False, 'error': '分配失败，论文不存在'}), 404
    
    except Exception as e:
        logger.error(f"任务分配失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/assign_task', methods=['POST'])
def api_assign_task():
    """为单个论文分配任务"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': '无效的请求数据'}), 400
        
        arxiv_id = data.get('arxiv_id', '').strip()
        task_name = data.get('task_name', '').strip()
        task_id = data.get('task_id', '').strip()
        
        if not arxiv_id or not task_name:
            return jsonify({'success': False, 'error': '缺少必要参数: arxiv_id 和 task_name'}), 400
        
        # 使用批量分配方法处理单个论文
        affected_rows = paper_explore_service.batch_assign_task_to_papers(
            [arxiv_id], task_name, task_id or None
        )
        
        if affected_rows > 0:
            return jsonify({
                'success': True, 
                'message': f'成功为论文 {arxiv_id} 分配任务 {task_name}'
            })
        else:
            return jsonify({
                'success': False, 
                'error': f'论文 {arxiv_id} 不存在或任务分配失败'
            }), 404
    
    except Exception as e:
        logger.error(f"分配任务失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/batch_assign_tasks', methods=['POST'])
def api_batch_assign_tasks():
    """批量分配任务 - 与前端期望的路径匹配"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': '无效的请求数据'}), 400
        
        arxiv_ids = data.get('arxiv_ids', [])
        task_name = data.get('task_name', '').strip()
        task_id = data.get('task_id', '').strip()
        
        if not arxiv_ids or not task_name:
            return jsonify({'success': False, 'error': '缺少必要参数'}), 400
        
        affected_rows = paper_explore_service.batch_assign_task_to_papers(
            arxiv_ids, task_name, task_id or None
        )
        
        return jsonify({
            'success': True, 
            'affected_rows': affected_rows,
            'message': f'成功为 {affected_rows} 篇论文分配任务'
        })
    
    except Exception as e:
        logger.error(f"批量分配任务失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/batch_assign_task', methods=['POST'])
def api_batch_assign_task():
    """批量分配任务"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': '无效的请求数据'}), 400
        
        arxiv_ids = data.get('arxiv_ids', [])
        task_name = data.get('task_name', '').strip()
        task_id = data.get('task_id', '').strip()
        
        if not arxiv_ids or not task_name:
            return jsonify({'success': False, 'error': '缺少必要参数'}), 400
        
        affected_rows = paper_explore_service.batch_assign_task_to_papers(
            arxiv_ids, task_name, task_id or None
        )
        
        return jsonify({
            'success': True, 
            'affected_rows': affected_rows,
            'message': f'成功为 {affected_rows} 篇论文分配任务'
        })
    
    except Exception as e:
        logger.error(f"批量分配任务失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# === 相关性评分API ===

@api_bp.route('/update_relevance_score', methods=['POST'])
def api_update_relevance_score():
    """更新单个论文的相关性评分"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': '无效的请求数据'}), 400
        
        arxiv_id = data.get('arxiv_id', '').strip()
        relevance_score = data.get('relevance_score')
        
        if not arxiv_id or relevance_score is None:
            return jsonify({'success': False, 'error': '缺少必要参数: arxiv_id 和 relevance_score'}), 400
        
        # 验证评分范围
        try:
            score = float(relevance_score)
            # 如果评分在0-10范围内，转换为0-1范围
            if 0 <= score <= 10:
                score_normalized = score / 10.0
            elif 0 <= score <= 1:
                score_normalized = score
            else:
                return jsonify({'success': False, 'error': '相关性评分必须在0-1或0-10之间'}), 400
        except (ValueError, TypeError):
            return jsonify({'success': False, 'error': '相关性评分必须是有效数字'}), 400
        
        # 更新相关性评分
        success = paper_explore_service.update_paper_relevance(arxiv_id, score_normalized)
        
        if success:
            return jsonify({
                'success': True, 
                'message': f'成功更新论文 {arxiv_id} 的相关性评分为 {score}'
            })
        else:
            return jsonify({
                'success': False, 
                'error': f'论文 {arxiv_id} 不存在或更新失败'
            }), 404
    
    except Exception as e:
        logger.error(f"更新相关性评分失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/update_relevance', methods=['POST'])
def api_update_relevance():
    """更新相关性（兼容旧版API）"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': '无效的请求数据'}), 400
        
        arxiv_id = data.get('arxiv_id', '').strip()
        relevance_score = data.get('relevance_score') or data.get('score')
        
        if not arxiv_id or relevance_score is None:
            return jsonify({'success': False, 'error': '缺少必要参数'}), 400
        
        # 验证评分范围
        try:
            score = float(relevance_score)
            # 如果评分在0-10范围内，转换为0-1范围
            if 0 <= score <= 10:
                score_normalized = score / 10.0
            elif 0 <= score <= 1:
                score_normalized = score
            else:
                return jsonify({'success': False, 'error': '相关性评分必须在0-1或0-10之间'}), 400
        except (ValueError, TypeError):
            return jsonify({'success': False, 'error': '相关性评分必须是有效数字'}), 400
        
        # 更新相关性评分
        success = paper_explore_service.update_paper_relevance(arxiv_id, score_normalized)
        
        if success:
            return jsonify({
                'success': True, 
                'message': f'成功更新论文 {arxiv_id} 的相关性评分为 {score}'
            })
        else:
            return jsonify({
                'success': False, 
                'error': f'论文 {arxiv_id} 不存在或更新失败'
            }), 404
    
    except Exception as e:
        logger.error(f"更新相关性失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# === 批量操作API ===

@api_bp.route('/batch_delete_papers', methods=['POST'])
def api_batch_delete_papers():
    """批量删除论文"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': '无效的请求数据'}), 400
        
        arxiv_ids = data.get('arxiv_ids', [])
        
        if not arxiv_ids:
            return jsonify({'success': False, 'error': '缺少必要参数: arxiv_ids'}), 400
        
        # 执行批量删除
        deleted_count = 0
        errors = []
        
        for arxiv_id in arxiv_ids:
            try:
                success = paper_explore_service.delete_paper(arxiv_id)
                if success:
                    deleted_count += 1
                else:
                    errors.append(f"论文 {arxiv_id} 删除失败")
            except Exception as e:
                errors.append(f"论文 {arxiv_id} 删除失败: {str(e)}")
        
        return jsonify({
            'success': True,
            'deleted_count': deleted_count,
            'total_requested': len(arxiv_ids),
            'errors': errors,
            'message': f'成功删除 {deleted_count}/{len(arxiv_ids)} 篇论文'
        })
    
    except Exception as e:
        logger.error(f"批量删除论文失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/batch_remove_from_dify', methods=['POST'])
def api_batch_remove_from_dify():
    """批量从Dify知识库移除论文"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': '无效的请求数据'}), 400
        
        arxiv_ids = data.get('arxiv_ids', [])
        
        if not arxiv_ids:
            return jsonify({'success': False, 'error': '缺少必要参数: arxiv_ids'}), 400
        
        # 执行批量移除
        removed_count = 0
        errors = []
        
        for arxiv_id in arxiv_ids:
            try:
                result = dify_service.remove_paper_from_dify(arxiv_id)
                if result.get('success'):
                    removed_count += 1
                else:
                    errors.append(f"论文 {arxiv_id} 移除失败: {result.get('error', '未知错误')}")
            except Exception as e:
                errors.append(f"论文 {arxiv_id} 移除失败: {str(e)}")
        
        return jsonify({
            'success': True,
            'removed_count': removed_count,
            'total_requested': len(arxiv_ids),
            'errors': errors,
            'message': f'成功从Dify移除 {removed_count}/{len(arxiv_ids)} 篇论文'
        })
    
    except Exception as e:
        logger.error(f"批量从Dify移除论文失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/refresh', methods=['POST'])
def api_refresh():
    """刷新数据"""
    try:
        # 这里可以实现数据刷新逻辑，比如清除缓存等
        # 目前简单返回成功响应
        return jsonify({
            'success': True,
            'message': '数据刷新成功'
        })
    
    except Exception as e:
        logger.error(f"数据刷新失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/migration_preview', methods=['POST'])
def api_migration_preview():
    """迁移预览"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': '无效的请求数据'}), 400
        
        source_task = data.get('source_task', '').strip()
        target_task = data.get('target_task', '').strip()
        
        if not source_task or not target_task:
            return jsonify({'success': False, 'error': '缺少必要参数: source_task 和 target_task'}), 400
        
        # 获取源任务的论文列表作为预览
        papers = paper_explore_service.get_papers_by_task_name(source_task, page=1, per_page=50)
        
        preview_info = {
            'source_task': source_task,
            'target_task': target_task,
            'papers_count': papers[1] if isinstance(papers, tuple) else 0,
            'preview_papers': []
        }
        
        if isinstance(papers, tuple) and papers[0]:
            preview_info['preview_papers'] = [
                {
                    'arxiv_id': paper.get('arxiv_id'),
                    'title': paper.get('title', '')[:100] + '...' if len(paper.get('title', '')) > 100 else paper.get('title', ''),
                    'authors': paper.get('authors', '')
                }
                for paper in papers[0][:10]  # 只显示前10篇作为预览
            ]
        
        return jsonify({
            'success': True,
            'data': preview_info
        })
    
    except Exception as e:
        logger.error(f"迁移预览失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/one_click_upload', methods=['POST'])
def api_one_click_upload():
    """一键上传（批量上传到Dify）"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': '无效的请求数据'}), 400
        
        # 获取所有符合条件的论文
        arxiv_ids = data.get('arxiv_ids', [])
        
        if not arxiv_ids:
            # 如果没有指定论文ID，则上传所有符合条件的论文
            eligible_papers = paper_explore_service.get_eligible_papers_for_upload()
            arxiv_ids = [paper.get('arxiv_id') for paper in eligible_papers if paper.get('arxiv_id')]
        
        if not arxiv_ids:
            return jsonify({'success': False, 'error': '没有找到符合条件的论文'}), 400
        
        # 执行批量上传
        uploaded_count = 0
        errors = []
        
        for arxiv_id in arxiv_ids:
            try:
                result = dify_service.upload_paper_to_dify(arxiv_id)
                if result.get('success'):
                    uploaded_count += 1
                else:
                    errors.append(f"论文 {arxiv_id} 上传失败: {result.get('error', '未知错误')}")
            except Exception as e:
                errors.append(f"论文 {arxiv_id} 上传失败: {str(e)}")
        
        return jsonify({
            'success': True,
            'uploaded_count': uploaded_count,
            'total_requested': len(arxiv_ids),
            'errors': errors,
            'message': f'成功上传 {uploaded_count}/{len(arxiv_ids)} 篇论文到Dify'
        })
    
    except Exception as e:
        logger.error(f"一键上传失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# === 下载分析相关API ===

@api_bp.route('/paper/<arxiv_id>/download_analysis')
def api_download_analysis(arxiv_id):
    """API接口 - 下载分析结果（Markdown + 图片打包为ZIP）"""
    try:
        # 获取分析结果
        result = analysis_service.get_analysis_result(arxiv_id)
        
        if not result['success']:
            return jsonify({
                'success': False,
                'error': '分析结果不存在'
            }), 404
        
        # 创建临时ZIP文件
        temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
        
        try:
            with zipfile.ZipFile(temp_zip.name, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                # 添加Markdown文件
                markdown_content = result['content']
                
                # 处理图片路径，转换为相对路径
                processed_markdown = _process_markdown_for_download(markdown_content, arxiv_id)
                
                zip_file.writestr(f"{arxiv_id}_analysis.md", processed_markdown)
                
                # 添加图片文件
                images_dir = os.path.join(PROJECT_ROOT, "data/paper_analyze", arxiv_id, "imgs")
                if os.path.exists(images_dir):
                    for filename in os.listdir(images_dir):
                        if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                            image_path = os.path.join(images_dir, filename)
                            if os.path.isfile(image_path):
                                zip_file.write(image_path, f"imgs/{filename}")
            
            # 返回ZIP文件
            return send_file(
                temp_zip.name,
                as_attachment=True,
                download_name=f"{arxiv_id}_deep_analysis.zip",
                mimetype='application/zip'
            )
            
        finally:
            # 清理临时文件（在发送后会被自动删除）
            pass
            
    except Exception as e:
        logger.error(f"下载分析结果失败 {arxiv_id}: {e}")
        return jsonify({
            'success': False,
            'error': f"下载失败: {str(e)}"
        }), 500


def _process_markdown_for_download(content: str, arxiv_id: str) -> str:
    """
    处理Markdown内容，将网页URL路径转换为本地相对路径
    
    Args:
        content: 原始Markdown内容
        arxiv_id: ArXiv论文ID
        
    Returns:
        str: 处理后的Markdown内容
    """
    try:
        # 将网页URL路径转换为相对路径
        pattern = rf'/paper/{re.escape(arxiv_id)}/imgs/([^)]+)'
        replacement = r'imgs/\1'
        
        processed_content = re.sub(pattern, replacement, content)
        
        return processed_content
        
    except Exception as e:
        logger.error(f"处理Markdown下载内容失败: {e}")
        return content


# === 中文搜索助手API ===

@api_bp.route('/search/translate', methods=['POST'])
def translate_chinese_search():
    """中文搜索需求转换为英文搜索关键词和需求描述"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': '请提供JSON数据'
            }), 400
        
        chinese_input = data.get('chinese_input', '').strip()
        model_name = data.get('model_name', 'ollama.Qwen3_30B')
        
        if not chinese_input:
            return jsonify({
                'success': False,
                'error': '请输入中文搜索需求'
            }), 400
        
        # 导入并创建中文搜索助手
        import sys
        import os
        sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        from HomeSystem.workflow.paper_gather_task.chinese_search_assistant import ChineseSearchAssistantLLM
        
        assistant = ChineseSearchAssistantLLM(model_name=model_name)
        result = assistant.convert_chinese_to_english_search(chinese_input)
        
        return jsonify({
            'success': True,
            'data': {
                'search_keywords': result.search_keywords,
                'user_requirements': result.user_requirements,
                'suggested_task_name': result.suggested_task_name,
                'confidence': result.confidence,
                'notes': result.notes,
                'model_used': model_name
            }
        })
    
    except Exception as e:
        logger.error(f"中文搜索转换失败: {e}")
        return jsonify({
            'success': False,
            'error': f"转换失败: {str(e)}"
        }), 500


# === Dify知识库相关API ===

@api_bp.route('/dify_upload_all_eligible', methods=['POST'])
def api_dify_upload_all_eligible():
    """一键上传全部符合条件的论文到Dify知识库"""
    try:
        data = request.get_json() if request.is_json else {}
        filters = data.get('filters', {})
        
        # 调用批量上传服务
        result = dify_service.upload_all_eligible_papers_with_summary(filters)
        
        if result.get('success'):
            return jsonify(result)
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"一键上传全部失败: {e}")
        return jsonify({
            'success': False,
            'error': f"上传失败: {str(e)}",
            'total_eligible': 0,
            'success_count': 0,
            'failed_count': 0,
            'progress': 0
        }), 500


@api_bp.route('/dify_batch_verify', methods=['POST'])
def api_dify_batch_verify():
    """一键验证知识库中所有文档的状态"""
    try:
        # 调用批量验证服务
        result = dify_service.batch_verify_all_documents()
        
        if result.get('success'):
            return jsonify(result)
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"一键验证知识库失败: {e}")
        return jsonify({
            'success': False,
            'error': f"验证失败: {str(e)}",
            'total': 0,
            'verified': 0,
            'failed': 0,
            'missing': 0,
            'progress': 0
        }), 500


@api_bp.route('/dify_upload/<arxiv_id>', methods=['POST'])
def api_dify_upload_single(arxiv_id):
    """上传单个论文到Dify知识库"""
    try:
        result = dify_service.upload_paper_to_dify(arxiv_id)
        
        if result.get('success'):
            return jsonify(result)
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"上传论文到Dify失败 {arxiv_id}: {e}")
        return jsonify({
            'success': False,
            'error': f"上传失败: {str(e)}"
        }), 500


@api_bp.route('/dify_remove/<arxiv_id>', methods=['POST', 'DELETE'])
def api_dify_remove_single(arxiv_id):
    """移除单个论文从Dify知识库（无/api/前缀版本）"""
    return api_dify_remove_single_paper(arxiv_id)


@api_bp.route('/dify_status/<arxiv_id>')
def api_dify_status(arxiv_id):
    """检查单个论文在Dify中的状态"""
    try:
        result = dify_service.verify_dify_document(arxiv_id)
        
        if result.get('success'):
            return jsonify(result)
        else:
            return jsonify(result), 404
    except Exception as e:
        logger.error(f"检查Dify状态失败 {arxiv_id}: {e}")
        return jsonify({
            'success': False,
            'error': f"状态检查失败: {str(e)}"
        }), 500

@api_bp.route('/api/upload_to_dify', methods=['POST'])
def api_upload_to_dify():
    """批量上传论文到Dify知识库 - 兼容前端调用"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': '无效的请求数据'}), 400
        
        arxiv_ids = data.get('arxiv_ids', [])
        if not arxiv_ids:
            return jsonify({'success': False, 'error': '未提供论文ID列表'}), 400
        
        # 如果只有一个ID，直接调用单篇上传
        if len(arxiv_ids) == 1:
            result = dify_service.upload_paper_to_dify(arxiv_ids[0])
            return jsonify(result)
        
        # 多个ID的情况，调用批量上传
        results = {
            'success_count': 0,
            'failed_count': 0,
            'results': []
        }
        
        for arxiv_id in arxiv_ids:
            try:
                result = dify_service.upload_paper_to_dify(arxiv_id)
                if result.get('success'):
                    results['success_count'] += 1
                    results['results'].append({
                        'arxiv_id': arxiv_id,
                        'status': 'success',
                        'message': '上传成功'
                    })
                else:
                    results['failed_count'] += 1
                    results['results'].append({
                        'arxiv_id': arxiv_id,
                        'status': 'failed',
                        'error': result.get('error', '未知错误')
                    })
            except Exception as e:
                results['failed_count'] += 1
                results['results'].append({
                    'arxiv_id': arxiv_id,
                    'status': 'failed',
                    'error': str(e)
                })
        
        # 如果全部成功
        if results['failed_count'] == 0:
            return jsonify({
                'success': True,
                'message': f'成功上传{results["success_count"]}篇论文',
                'data': results
            })
        else:
            return jsonify({
                'success': False,
                'error': f'上传失败{results["failed_count"]}篇，成功{results["success_count"]}篇',
                'data': results
            }), 400
            
    except Exception as e:
        logger.error(f"批量上传论文到Dify失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@api_bp.route('/api/remove_from_dify', methods=['POST'])
def api_remove_from_dify():
    """从Dify知识库移除论文 - 兼容前端调用"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': '无效的请求数据'}), 400
        
        arxiv_ids = data.get('arxiv_ids', [])
        if not arxiv_ids:
            return jsonify({'success': False, 'error': '未提供论文ID列表'}), 400
        
        # 检查是否有移除功能
        if not hasattr(dify_service, 'remove_paper_from_dify'):
            return jsonify({
                'success': False,
                'error': '暂不支持从Dify移除论文功能'
            }), 501
        
        # 如果只有一个ID
        if len(arxiv_ids) == 1:
            result = dify_service.remove_paper_from_dify(arxiv_ids[0])
            return jsonify(result)
        
        # 多个ID的情况
        results = {
            'success_count': 0,
            'failed_count': 0,
            'results': []
        }
        
        for arxiv_id in arxiv_ids:
            try:
                result = dify_service.remove_paper_from_dify(arxiv_id)
                if result.get('success'):
                    results['success_count'] += 1
                    results['results'].append({
                        'arxiv_id': arxiv_id,
                        'status': 'success',
                        'message': '移除成功'
                    })
                else:
                    results['failed_count'] += 1
                    results['results'].append({
                        'arxiv_id': arxiv_id,
                        'status': 'failed',
                        'error': result.get('error', '未知错误')
                    })
            except Exception as e:
                results['failed_count'] += 1
                results['results'].append({
                    'arxiv_id': arxiv_id,
                    'status': 'failed',
                    'error': str(e)
                })
        
        # 返回结果
        if results['failed_count'] == 0:
            return jsonify({
                'success': True,
                'message': f'成功移除{results["success_count"]}篇论文',
                'data': results
            })
        else:
            return jsonify({
                'success': False,
                'error': f'移除失败{results["failed_count"]}篇，成功{results["success_count"]}篇',
                'data': results
            }), 400
            
    except Exception as e:
        logger.error(f"从Dify移除论文失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route('/dify_statistics')
def api_dify_statistics():
    """获取Dify知识库统计信息"""
    try:
        # 获取基本统计
        eligible_papers = dify_service.get_eligible_papers_for_upload()
        
        # 计算已上传的论文数量
        all_papers = paper_explore_service.get_paper_statistics()
        uploaded_count = all_papers.get('dify_uploaded', 0) if all_papers else 0
        
        statistics = {
            'total_papers': all_papers.get('total_papers', 0) if all_papers else 0,
            'eligible_for_upload': len(eligible_papers),
            'already_uploaded': uploaded_count,
            'dify_service_available': dify_service.is_available()
        }
        
        return jsonify({
            'success': True,
            'data': statistics
        })
        
    except Exception as e:
        logger.error(f"获取Dify统计信息失败: {e}")
        return jsonify({
            'success': False,
            'error': f"获取统计失败: {str(e)}"
        }), 500


@api_bp.route('/dify_upload/<arxiv_id>', methods=['POST'])
def api_dify_upload_single_paper(arxiv_id):
    """单个论文上传到Dify知识库 - 兼容ExplorePaperData调用模式"""
    try:
        if not arxiv_id:
            return jsonify({'success': False, 'error': '缺少论文ID'}), 400
        
        # 调用shared service上传
        result = dify_service.upload_paper_to_dify(arxiv_id)
        
        if result.get('success'):
            return jsonify({
                'success': True,
                'message': '论文上传成功',
                'data': {
                    'arxiv_id': arxiv_id,
                    'dataset_id': result.get('dataset_id'),
                    'document_id': result.get('document_id'),
                    'document_name': result.get('document_name')
                }
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', '上传失败')
            }), 400
            
    except Exception as e:
        logger.error(f"上传单个论文到Dify失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route('/dify_remove/<arxiv_id>', methods=['POST', 'DELETE'])
def api_dify_remove_single_paper(arxiv_id):
    """从Dify知识库移除单个论文 - 兼容ExplorePaperData调用模式"""
    try:
        if not arxiv_id:
            return jsonify({'success': False, 'error': '缺少论文ID'}), 400
        
        # 调用shared service移除
        result = dify_service.remove_paper_from_dify(arxiv_id)
        
        if result.get('success'):
            return jsonify({
                'success': True,
                'message': '论文移除成功',
                'data': {
                    'arxiv_id': arxiv_id
                }
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', '移除失败')
            }), 400
            
    except Exception as e:
        logger.error(f"从Dify移除单个论文失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route('/dify_verify/<arxiv_id>', methods=['POST'])
def api_dify_verify_single_paper(arxiv_id):
    """验证论文是否存在于Dify服务器 - 兼容ExplorePaperData调用模式"""
    try:
        if not arxiv_id:
            return jsonify({'success': False, 'error': '缺少论文ID'}), 400
        
        # 调用shared service验证
        result = dify_service.verify_dify_document(arxiv_id)
        
        if result.get('success'):
            return jsonify({
                'success': True,
                'data': result
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', '验证失败')
            }), 404
            
    except Exception as e:
        logger.error(f"验证Dify文档失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route('/dify_clean/<arxiv_id>', methods=['POST'])
def api_dify_clean_single_paper(arxiv_id):
    """清理无效的Dify文档记录 - 兼容ExplorePaperData调用模式"""
    try:
        if not arxiv_id:
            return jsonify({'success': False, 'error': '缺少论文ID'}), 400
        
        # 获取论文数据并清理无效记录
        paper_dict = dify_service._get_paper_data(arxiv_id)
        if not paper_dict:
            return jsonify({'success': False, 'error': '论文不存在'}), 400
        
        # 清理数据库中的Dify信息
        if dify_service.db_ops:
            paper = dify_service.db_ops.get_by_field(ArxivPaperModel, 'arxiv_id', arxiv_id)
            if paper:
                arxiv_paper = paper if isinstance(paper, ArxivPaperModel) else ArxivPaperModel.from_dict(paper.to_dict())
                arxiv_paper.clear_dify_info()
                
                clear_data = {
                    'dify_dataset_id': arxiv_paper.dify_dataset_id,
                    'dify_document_id': arxiv_paper.dify_document_id,
                    'dify_document_name': arxiv_paper.dify_document_name,
                    'dify_character_count': arxiv_paper.dify_character_count,
                    'dify_segment_count': arxiv_paper.dify_segment_count,
                    'dify_upload_time': arxiv_paper.dify_upload_time,
                    'dify_metadata': json.dumps(arxiv_paper.dify_metadata) if arxiv_paper.dify_metadata else '{}'
                }
                
                success = dify_service.db_ops.update(arxiv_paper, clear_data)
                if success:
                    return jsonify({
                        'success': True,
                        'message': '无效记录已清理',
                        'data': {'arxiv_id': arxiv_id}
                    })
                else:
                    return jsonify({'success': False, 'error': '清理失败'}), 500
            else:
                return jsonify({'success': False, 'error': '论文不存在'}), 400
        else:
            return jsonify({'success': False, 'error': '数据库服务不可用'}), 500
            
    except Exception as e:
        logger.error(f"清理Dify记录失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route('/dify_validate_upload/<arxiv_id>')
def api_dify_validate_upload_single_paper(arxiv_id):
    """验证论文上传前置条件 - 兼容ExplorePaperData调用模式"""
    try:
        if not arxiv_id:
            return jsonify({'success': False, 'error': '缺少论文ID'}), 400
        
        # 调用shared service验证上传前置条件
        result = dify_service.validate_upload_preconditions(arxiv_id)
        
        return jsonify(result)
            
    except Exception as e:
        logger.error(f"验证上传前置条件失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ========== 论文创建相关API ==========

@api_bp.route('/create_paper_from_pdf', methods=['POST'])
def api_create_paper_from_pdf():
    """从PDF文件创建论文"""
    try:
        # 检查是否有上传的文件
        if 'pdf_file' not in request.files:
            return jsonify({'success': False, 'error': '未上传PDF文件'}), 400
            
        pdf_file = request.files['pdf_file']
        if pdf_file.filename == '':
            return jsonify({'success': False, 'error': 'PDF文件名为空'}), 400
        
        # 检查文件类型
        if not pdf_file.filename.lower().endswith('.pdf'):
            return jsonify({'success': False, 'error': '仅支持PDF文件'}), 400
        
        # 获取可选参数
        task_name = request.form.get('task_name', '').strip() or None
        task_id = request.form.get('task_id', '').strip() or None
        
        # 导入必要的模块
        from HomeSystem.utility.arxiv.arxiv import ArxivData
        from HomeSystem.integrations.database import DatabaseOperations, ArxivPaperModel
        import tempfile
        import os
        import uuid
        from datetime import datetime
        
        # 保存上传的PDF到临时文件
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_pdf:
            pdf_file.save(temp_pdf.name)
            temp_pdf_path = temp_pdf.name
        
        try:
            # 应用远程OCR配置（在OCR处理之前）
            ocr_config = apply_remote_ocr_config()
            
            # 先生成唯一的arxiv_id（使用简化格式加上timestamp）
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            generated_id = f"manual_{timestamp}_{str(uuid.uuid4())[:8]}"
            
            # 创建ArxivData对象并设置arxiv_id
            arxiv_data = ArxivData()
            arxiv_data.arxiv_id = generated_id
            
            # 获取标准目录路径并创建目录
            pdf_dir = arxiv_data.get_paper_directory()
            pdf_dir.mkdir(parents=True, exist_ok=True)
            
            # 设置PDF路径，启用元数据提取
            arxiv_data.set_pdf_path(temp_pdf_path, extract_metadata=True)
            
            # 手动执行OCR并保存到正确位置
            logger.info(f"执行OCR处理，保存到: {pdf_dir}")
            
            # 根据OCR类型决定处理页数
            if ocr_config.get('enable_remote_ocr', False):
                ocr_max_pages = ocr_config.get('remote_ocr_max_pages', 25)
                logger.info(f"使用远程OCR处理 {ocr_max_pages} 页")
            else:
                ocr_max_pages = 25  # 本地OCR也使用25页，因为这是完整处理
                logger.info(f"使用本地OCR处理 {ocr_max_pages} 页")
            
            ocr_result, ocr_status = arxiv_data.performOCR(
                max_pages=ocr_max_pages,
                use_paddleocr=True,
                use_remote_ocr=ocr_config.get('enable_remote_ocr', False),
                auto_save=True,
                save_path=str(pdf_dir)
            )
            
            if ocr_result:
                logger.info(f"OCR处理成功，提取 {len(ocr_result)} 字符")
            else:
                logger.warning("OCR处理失败或未提取到内容")
            
            # 设置基本属性
            if not arxiv_data.title:
                arxiv_data.title = f"Manual Upload - {pdf_file.filename}"
            
            # 创建数据库模型
            paper_model = ArxivPaperModel()
            paper_model.arxiv_id = generated_id
            paper_model.title = arxiv_data.title or f"Manual Upload - {pdf_file.filename}"
            paper_model.authors = arxiv_data.authors or ""
            paper_model.abstract = arxiv_data.snippet or ""
            paper_model.categories = "manual_upload"
            paper_model.published_date = datetime.now().strftime('%Y-%m-%d')
            paper_model.pdf_url = ""  # 没有ArXiv URL
            paper_model.processing_status = "completed"
            paper_model.task_name = task_name
            paper_model.task_id = task_id
            
            # 添加元数据标记这是手动上传
            paper_model.add_metadata('source', 'manual_upload')
            paper_model.add_metadata('original_filename', pdf_file.filename)
            paper_model.add_metadata('upload_timestamp', datetime.now().isoformat())
            
            # 保存到数据库
            from HomeSystem.integrations.database import DatabaseOperations
            db_ops = DatabaseOperations()
            success = db_ops.create(paper_model)
            
            if success:
                # 复制临时PDF到标准目录（PDF目录已在前面创建）
                try:
                    pdf_file_path = pdf_dir / f"{generated_id}.pdf"
                    import shutil
                    shutil.copy2(temp_pdf_path, pdf_file_path)
                    logger.info(f"PDF已保存到标准目录: {pdf_file_path}")
                    
                except Exception as e:
                    logger.warning(f"保存PDF到标准目录失败: {e}")
                    # 不影响主流程，只记录警告
                
                return jsonify({
                    'success': True,
                    'arxiv_id': generated_id,
                    'title': paper_model.title,
                    'authors': paper_model.authors,
                    'abstract': paper_model.abstract,
                    'message': '论文创建成功',
                    'redirect_url': f'/explore/paper/{generated_id}'
                })
            else:
                return jsonify({'success': False, 'error': '数据库保存失败'}), 500
                
        finally:
            # 清理临时文件
            if os.path.exists(temp_pdf_path):
                os.unlink(temp_pdf_path)
            
    except Exception as e:
        logger.error(f"从PDF创建论文失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/create_paper_from_arxiv', methods=['POST'])
def api_create_paper_from_arxiv():
    """从ArXiv URL创建论文"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': '无效的请求数据'}), 400
        
        arxiv_input = data.get('arxiv_input', '').strip()
        if not arxiv_input:
            return jsonify({'success': False, 'error': '请输入ArXiv链接或ID'}), 400
        
        task_name = data.get('task_name', '').strip() or None
        task_id = data.get('task_id', '').strip() or None
        
        # 导入必要的模块
        from HomeSystem.utility.arxiv.arxiv import ArxivData
        from HomeSystem.integrations.database import DatabaseOperations, ArxivPaperModel
        from datetime import datetime
        
        # 规范化ArXiv输入为完整URL
        if not arxiv_input.startswith('http'):
            # 如果只是ID，转换为完整URL
            arxiv_input = f"https://arxiv.org/abs/{arxiv_input}"
        
        # 创建ArxivData对象
        arxiv_data = ArxivData()
        
        # 从ArXiv链接获取元数据
        success = arxiv_data.populate_from_arxiv_link(arxiv_input)
        if not success:
            return jsonify({'success': False, 'error': '无法从ArXiv获取论文信息，请检查链接或ID是否正确'}), 400
        
        # 检查论文是否已存在
        db_ops = DatabaseOperations()
        if arxiv_data.arxiv_id:
            existing_paper = db_ops.get_by_field(ArxivPaperModel, 'arxiv_id', arxiv_data.arxiv_id)
        else:
            existing_paper = None
        if existing_paper:
            return jsonify({
                'success': False, 
                'error': f'论文已存在: {arxiv_data.arxiv_id}',
                'existing_paper': {
                    'arxiv_id': existing_paper.arxiv_id,
                    'title': existing_paper.title,
                    'redirect_url': f'/explore/paper/{existing_paper.arxiv_id}'
                }
            }), 409
        
        # 应用远程OCR配置（在PDF下载和潜在OCR处理之前）
        ocr_config = apply_remote_ocr_config()
        
        # 下载PDF到标准目录
        try:
            if arxiv_data.pdf_link:
                arxiv_data.downloadPdf(use_standard_path=True, check_existing=True)
                logger.info(f"PDF下载成功: {arxiv_data.arxiv_id}")
        except Exception as e:
            logger.warning(f"PDF下载失败: {e}")
            # 不影响主流程，继续创建论文记录
        
        # 创建数据库模型
        paper_model = ArxivPaperModel()
        paper_model.arxiv_id = arxiv_data.arxiv_id or ""
        paper_model.title = arxiv_data.title or "Untitled"
        paper_model.authors = arxiv_data.authors or ""
        paper_model.abstract = arxiv_data.snippet or ""
        paper_model.categories = arxiv_data.categories or "Unknown"
        paper_model.published_date = arxiv_data.published_date or ""
        paper_model.pdf_url = arxiv_data.pdf_link or ""
        paper_model.processing_status = "completed"
        paper_model.task_name = task_name
        paper_model.task_id = task_id
        
        # 添加元数据标记这是从ArXiv创建
        paper_model.add_metadata('source', 'arxiv_manual_add')
        paper_model.add_metadata('creation_timestamp', datetime.now().isoformat())
        
        # 保存到数据库
        success = db_ops.create(paper_model)
        
        if success:
            return jsonify({
                'success': True,
                'arxiv_id': paper_model.arxiv_id,
                'title': paper_model.title,
                'authors': paper_model.authors,
                'abstract': paper_model.abstract,
                'message': '论文创建成功',
                'redirect_url': f'/explore/paper/{paper_model.arxiv_id}'
            })
        else:
            return jsonify({'success': False, 'error': '数据库保存失败'}), 500
            
    except Exception as e:
        logger.error(f"从ArXiv创建论文失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500