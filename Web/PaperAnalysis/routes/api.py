"""
统一API路由 - 整合两个应用的API接口
提供RESTful API接口用于前端调用和第三方集成
"""
from flask import Blueprint, request, jsonify
from services.task_service import paper_gather_service
from services.paper_gather_service import paper_data_service
from services.paper_explore_service import PaperService, DifyService
from services.analysis_service import DeepAnalysisService
import logging
import os
import sys
import json

logger = logging.getLogger(__name__)

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
analysis_service = DeepAnalysisService(paper_explore_service, redis_client)


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
        tasks = paper_explore_service.get_available_tasks()
        return jsonify({'success': True, 'data': tasks})
    
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