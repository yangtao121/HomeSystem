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
    """获取任务历史"""
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        
        all_results = paper_gather_service.get_all_task_results()
        sorted_results = sorted(all_results, key=lambda x: x['start_time'], reverse=True)
        
        # 分页
        total = len(sorted_results)
        start = (page - 1) * per_page
        end = start + per_page
        results = sorted_results[start:end]
        
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