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
            'timeout': 600
        }
    
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
                    
                    if system_data.get('analysis_timeout'):
                        analysis_config['timeout'] = system_data['analysis_timeout']
                    
                    # 深度分析相关配置
                    if 'enable_deep_analysis' in system_data:
                        analysis_config['enable_deep_analysis'] = system_data['enable_deep_analysis']
                    if 'deep_analysis_threshold' in system_data:
                        analysis_config['deep_analysis_threshold'] = system_data['deep_analysis_threshold']
                    if 'ocr_char_limit_for_analysis' in system_data:
                        analysis_config['ocr_char_limit_for_analysis'] = system_data['ocr_char_limit_for_analysis']
                    if 'relevance_threshold' in system_data:
                        analysis_config['relevance_threshold'] = system_data['relevance_threshold']
                    
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
                    del self.analysis_threads[arxiv_id]
            
            # 更新分析状态为处理中
            self.paper_service.update_analysis_status(arxiv_id, 'processing')
            
            # 加载当前配置
            current_config = self.load_config()
            analysis_config = {**current_config, **(config or {})}
            
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
            if arxiv_id in self.analysis_threads:
                del self.analysis_threads[arxiv_id]
    
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
                new_path = f"/paper/{arxiv_id}/analysis_images/{filename}"
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
            
            # 深度分析配置
            'enable_deep_analysis': data.get('enable_deep_analysis', True),
            'deep_analysis_threshold': data.get('deep_analysis_threshold', 0.8),
            'ocr_char_limit_for_analysis': data.get('ocr_char_limit_for_analysis', 10000),
            'analysis_timeout': data.get('analysis_timeout', 600)
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
        pattern = rf'/paper/{re.escape(arxiv_id)}/analysis_images/([^)]+)'
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