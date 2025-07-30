"""
主要路由 - 首页和配置页面
"""
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from services.task_service import paper_gather_service
from services.paper_service import paper_data_service
from config import DEFAULT_TASK_CONFIG
import logging

logger = logging.getLogger(__name__)

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    """首页 - 仪表板"""
    try:
        # 获取论文统计信息
        stats = paper_data_service.get_paper_statistics()
        
        # 获取最近的论文
        recent_papers = paper_data_service.get_recent_papers(limit=5)
        
        # 获取任务执行历史
        task_results = paper_gather_service.get_all_task_results()
        recent_tasks = sorted(task_results, key=lambda x: x['start_time'], reverse=True)[:10]
        
        # 获取正在运行的定时任务
        scheduled_tasks = paper_gather_service.get_scheduled_tasks()
        
        # 获取运行中任务总数和详情
        running_tasks_count = paper_gather_service.get_running_tasks_count()
        running_tasks_detail = paper_gather_service.get_running_tasks_detail()
        
        return render_template('index.html', 
                             stats=stats,
                             recent_papers=recent_papers,
                             recent_tasks=recent_tasks,
                             scheduled_tasks=scheduled_tasks,
                             running_tasks_count=running_tasks_count,
                             running_tasks_detail=running_tasks_detail)
    
    except Exception as e:
        logger.error(f"首页加载失败: {e}")
        return render_template('error.html', error="首页加载失败，请检查系统状态"), 500


@main_bp.route('/config')
def config():
    """配置页面"""
    try:
        # 获取可用的LLM模型
        available_models = paper_gather_service.get_available_models()
        
        # 获取可用的搜索模式
        available_search_modes = paper_gather_service.get_available_search_modes()
        
        return render_template('config.html', 
                             default_config=DEFAULT_TASK_CONFIG,
                             available_models=available_models,
                             available_search_modes=available_search_modes)
    
    except Exception as e:
        logger.error(f"配置页面加载失败: {e}")
        return render_template('error.html', error="配置页面加载失败"), 500


@main_bp.route('/config/validate', methods=['POST'])
def validate_config():
    """验证配置参数"""
    try:
        config_data = request.get_json()
        
        is_valid, error_msg = paper_gather_service.validate_config(config_data)
        
        return jsonify({
            'success': is_valid,
            'error': error_msg
        })
    
    except Exception as e:
        logger.error(f"配置验证失败: {e}")
        return jsonify({
            'success': False,
            'error': f"配置验证失败: {str(e)}"
        }), 500


@main_bp.route('/help')
def help_page():
    """帮助页面"""
    return render_template('help.html')


@main_bp.route('/about')
def about():
    """关于页面"""
    return render_template('about.html')