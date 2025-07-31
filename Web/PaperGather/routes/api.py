"""
API路由 - 提供JSON API接口
"""
from flask import Blueprint, request, jsonify
from services.task_service import paper_gather_service
from services.paper_service import paper_data_service
import logging

logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__, url_prefix='/api')


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


@api_bp.route('/task/status/<task_id>')
def get_task_status(task_id):
    """获取任务状态 - 用于实时更新"""
    try:
        task_result = paper_gather_service.get_task_result(task_id)
        
        if not task_result:
            return jsonify({
                'success': False,
                'error': '任务不存在'
            }), 404
        
        return jsonify({
            'success': True,
            'data': task_result
        })
    
    except Exception as e:
        logger.error(f"获取任务状态失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route('/task/history')
def get_task_history():
    """获取任务历史（包含持久化数据）"""
    try:
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('per_page', 20)), 100)
        status_filter = request.args.get('status', '').strip()
        
        # 使用新的历史记录获取方法
        limit = per_page * page  # 获取足够的数据进行分页
        all_results = paper_gather_service.get_task_history(
            limit=limit * 2,  # 获取更多数据以确保分页准确
            status_filter=status_filter if status_filter else None
        )
        
        # 分页
        total = len(all_results)
        start = (page - 1) * per_page
        end = start + per_page
        results = all_results[start:end]
        
        return jsonify({
            'success': True,
            'data': results,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'total_pages': (total + per_page - 1) // per_page
            }
        })
    
    except Exception as e:
        logger.error(f"获取任务历史失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route('/task/config/<task_id>')
def get_task_config(task_id):
    """获取指定任务的配置（支持版本兼容性）"""
    try:
        config = paper_gather_service.get_task_config_by_id(task_id)
        
        if not config:
            return jsonify({
                'success': False,
                'error': '任务不存在或配置获取失败'
            }), 404
        
        return jsonify({
            'success': True,
            'data': config
        })
    
    except Exception as e:
        logger.error(f"获取任务配置失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route('/task/start_from_config', methods=['POST'])
def start_task_from_config():
    """基于配置启动新任务"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': '请提供JSON数据'
            }), 400
        
        config_dict = data.get('config', {})
        task_mode = data.get('mode', 'immediate')  # immediate 或 scheduled
        
        if not config_dict:
            return jsonify({
                'success': False,
                'error': '缺少配置参数'
            }), 400
        
        # 导入TaskMode枚举
        from services.task_service import TaskMode
        mode = TaskMode.IMMEDIATE if task_mode == 'immediate' else TaskMode.SCHEDULED
        
        success, task_id, error_msg = paper_gather_service.start_task_from_config(config_dict, mode)
        
        if success:
            return jsonify({
                'success': True,
                'data': {
                    'task_id': task_id,
                    'mode': task_mode
                }
            })
        else:
            return jsonify({
                'success': False,
                'error': error_msg
            }), 400
    
    except Exception as e:
        logger.error(f"基于配置启动任务失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route('/config/presets')
def get_config_presets():
    """获取所有配置预设"""
    try:
        presets = paper_gather_service.load_config_presets()
        
        return jsonify({
            'success': True,
            'data': presets
        })
    
    except Exception as e:
        logger.error(f"获取配置预设失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route('/config/presets', methods=['POST'])
def save_config_preset():
    """保存配置预设"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': '请提供JSON数据'
            }), 400
        
        name = data.get('name', '').strip()
        config_dict = data.get('config', {})
        description = data.get('description', '').strip()
        
        if not name:
            return jsonify({
                'success': False,
                'error': '预设名称不能为空'
            }), 400
        
        if not config_dict:
            return jsonify({
                'success': False,
                'error': '配置不能为空'
            }), 400
        
        success, error_msg = paper_gather_service.save_config_preset(name, config_dict, description)
        
        if success:
            return jsonify({
                'success': True,
                'message': '配置预设保存成功'
            })
        else:
            return jsonify({
                'success': False,
                'error': error_msg
            }), 400
    
    except Exception as e:
        logger.error(f"保存配置预设失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route('/config/presets/<preset_id>', methods=['DELETE'])
def delete_config_preset(preset_id):
    """删除配置预设"""
    try:
        success, error_msg = paper_gather_service.delete_config_preset(preset_id)
        
        if success:
            return jsonify({
                'success': True,
                'message': '配置预设删除成功'
            })
        else:
            return jsonify({
                'success': False,
                'error': error_msg
            }), 400
    
    except Exception as e:
        logger.error(f"删除配置预设失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route('/task/history/<task_id>', methods=['PUT'])
def update_task_history(task_id):
    """更新历史任务记录"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': '请提供更新数据'
            }), 400
        
        success, error_msg = paper_gather_service.update_task_history(task_id, data)
        
        if success:
            return jsonify({
                'success': True,
                'message': '历史任务更新成功'
            })
        else:
            return jsonify({
                'success': False,
                'error': error_msg or '更新历史任务失败'
            }), 400
    
    except Exception as e:
        logger.error(f"更新历史任务失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route('/task/history/<task_id>', methods=['DELETE'])
def delete_task_history(task_id):
    """删除历史任务记录"""
    try:
        success, error_msg = paper_gather_service.delete_task_history(task_id)
        
        if success:
            return jsonify({
                'success': True,
                'message': '历史任务删除成功'
            })
        else:
            # 如果是"未找到"错误，返回404状态码
            if error_msg and ('未找到' in error_msg or '不存在' in error_msg):
                return jsonify({
                    'success': False,
                    'error': '任务不存在或已被删除',
                    'code': 'TASK_NOT_FOUND'
                }), 404
            else:
                return jsonify({
                    'success': False,
                    'error': error_msg or '删除历史任务失败'
                }), 400
    
    except Exception as e:
        logger.error(f"删除历史任务失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route('/data/statistics')
def get_data_statistics():
    """获取数据统计信息"""
    try:
        stats = paper_gather_service.get_data_statistics()
        
        return jsonify({
            'success': True,
            'data': stats
        })
    
    except Exception as e:
        logger.error(f"获取数据统计失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route('/papers/search')
def search_papers():
    """搜索论文"""
    try:
        query = request.args.get('q', '').strip()
        category = request.args.get('category', '').strip()
        status = request.args.get('status', '').strip()
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('per_page', 20)), 100)
        
        papers, total = paper_data_service.search_papers(
            query=query,
            category=category,
            status=status,
            page=page,
            per_page=per_page
        )
        
        return jsonify({
            'success': True,
            'data': papers,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'total_pages': (total + per_page - 1) // per_page
            }
        })
    
    except Exception as e:
        logger.error(f"搜索论文失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route('/papers/<arxiv_id>')
def get_paper_detail(arxiv_id):
    """获取论文详情"""
    try:
        paper = paper_data_service.get_paper_detail(arxiv_id)
        
        if not paper:
            return jsonify({
                'success': False,
                'error': '论文不存在'
            }), 404
        
        return jsonify({
            'success': True,
            'data': paper
        })
    
    except Exception as e:
        logger.error(f"获取论文详情失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route('/papers/statistics')
def get_paper_statistics():
    """获取论文统计信息"""
    try:
        stats = paper_data_service.get_paper_statistics()
        
        return jsonify({
            'success': True,
            'data': stats
        })
    
    except Exception as e:
        logger.error(f"获取论文统计失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route('/papers/recent')
def get_recent_papers():
    """获取最近的论文"""
    try:
        limit = min(int(request.args.get('limit', 10)), 50)
        papers = paper_data_service.get_recent_papers(limit=limit)
        
        return jsonify({
            'success': True,
            'data': papers
        })
    
    except Exception as e:
        logger.error(f"获取最近论文失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route('/scheduled_tasks')
def get_scheduled_tasks():
    """获取定时任务列表"""
    try:
        tasks = paper_gather_service.get_scheduled_tasks()
        
        return jsonify({
            'success': True,
            'data': tasks
        })
    
    except Exception as e:
        logger.error(f"获取定时任务失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route('/running_tasks')
def get_running_tasks():
    """获取运行中任务列表"""
    try:
        running_tasks = paper_gather_service.get_running_tasks_detail()
        running_count = paper_gather_service.get_running_tasks_count()
        
        return jsonify({
            'success': True,
            'data': {
                'tasks': running_tasks,
                'count': running_count
            }
        })
    
    except Exception as e:
        logger.error(f"获取运行中任务失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


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


@api_bp.route('/config/status')
def get_config_status():
    """获取配置模块状态"""
    try:
        status = {
            'success': True,
            'modules': {
                'llm_factory': {'status': 'unknown', 'message': '', 'details': {}},
                'search_modes': {'status': 'unknown', 'message': '', 'details': {}},
                'task_history': {'status': 'unknown', 'message': '', 'details': {}},
                'database': {'status': 'unknown', 'message': '', 'details': {}}
            },
            'overall_status': 'unknown'
        }
        
        # 检查LLM配置
        try:
            models = paper_gather_service.get_available_models()
            status['modules']['llm_factory'] = {
                'status': 'healthy',
                'message': f'成功加载 {len(models)} 个LLM模型',
                'details': {'model_count': len(models), 'models': models[:3]}
            }
        except Exception as e:
            status['modules']['llm_factory'] = {
                'status': 'error',
                'message': f'LLM模型加载失败: {str(e)}',
                'details': {'error': str(e)}
            }
        
        # 检查搜索模式
        try:
            search_modes = paper_gather_service.get_available_search_modes()
            status['modules']['search_modes'] = {
                'status': 'healthy',
                'message': f'成功加载 {len(search_modes)} 个搜索模式',
                'details': {'mode_count': len(search_modes)}
            }
        except Exception as e:
            status['modules']['search_modes'] = {
                'status': 'error',
                'message': f'搜索模式加载失败: {str(e)}',
                'details': {'error': str(e)}
            }
        
        # 检查任务历史
        try:
            task_count = len(paper_gather_service.get_all_task_results())
            status['modules']['task_history'] = {
                'status': 'healthy',
                'message': f'成功加载 {task_count} 个历史任务',
                'details': {'task_count': task_count}
            }
        except Exception as e:
            status['modules']['task_history'] = {
                'status': 'warning',
                'message': f'历史任务加载部分失败: {str(e)}',
                'details': {'error': str(e)}
            }
        
        # 检查数据库连接
        try:
            stats = paper_data_service.get_paper_statistics()
            status['modules']['database'] = {
                'status': 'healthy',
                'message': '数据库连接正常',
                'details': {'total_papers': stats.get('total_papers', 0)}
            }
        except Exception as e:
            status['modules']['database'] = {
                'status': 'error',
                'message': f'数据库连接失败: {str(e)}',
                'details': {'error': str(e)}
            }
        
        # 计算整体状态
        module_statuses = [module['status'] for module in status['modules'].values()]
        if 'error' in module_statuses:
            status['overall_status'] = 'error'
        elif 'warning' in module_statuses:
            status['overall_status'] = 'warning'
        else:
            status['overall_status'] = 'healthy'
        
        return jsonify(status)
    
    except Exception as e:
        logger.error(f"获取配置状态失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'overall_status': 'error'
        }), 500


@api_bp.route('/health')
def health_check():
    """健康检查"""
    try:
        # 检查数据库连接
        stats = paper_data_service.get_paper_statistics()
        
        # 检查任务服务
        models = paper_gather_service.get_available_models()
        
        return jsonify({
            'success': True,
            'status': 'healthy',
            'data': {
                'database': 'connected',
                'available_models': len(models),
                'total_papers': stats.get('total_papers', 0)
            }
        })
    
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return jsonify({
            'success': False,
            'status': 'unhealthy',
            'error': str(e)
        }), 500