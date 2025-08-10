"""
主路由 - 首页和基础页面
合并了PaperGather和ExplorePaperData的主要路由
"""
from flask import Blueprint, render_template, request, jsonify
try:
    from services.task_service import paper_gather_service
    from services.paper_gather_service import paper_data_service
    from services.paper_explore_service import PaperService
    from config import DEFAULT_TASK_CONFIG
except ImportError:
    # 如果直接导入失败，尝试相对导入
    from ..services.task_service import paper_gather_service
    from ..services.paper_gather_service import paper_data_service
    from ..services.paper_explore_service import PaperService
    from ..config import DEFAULT_TASK_CONFIG
import logging

logger = logging.getLogger(__name__)

main_bp = Blueprint('main', __name__)

# 初始化服务
paper_explore_service = PaperService()

@main_bp.route('/')
def index():
    """综合仪表板 - 合并两个应用的首页功能"""
    try:
        # 获取论文浏览统计信息 (使用正确的数据源)
        explore_stats = None
        try:
            explore_stats = paper_explore_service.get_overview_stats()
            if not explore_stats or not isinstance(explore_stats, dict):
                logger.warning("论文统计数据为空或格式不正确")
                explore_stats = None
        except Exception as stats_error:
            logger.error(f"获取论文统计失败: {stats_error}")
            explore_stats = None
        
        # 如果统计数据获取失败，提供默认数据结构
        if not explore_stats:
            explore_stats = {
                'basic': {
                    'total_papers': 0,
                    'analyzed_papers': 0,
                    'unanalyzed_papers': 0
                },
                'recent': []
            }
        
        # 获取最近的论文
        recent_papers = []
        try:
            recent_papers = paper_data_service.get_recent_papers(limit=10)
            if not recent_papers:
                recent_papers = []
        except Exception as papers_error:
            logger.error(f"获取最近论文失败: {papers_error}")
            recent_papers = []
        
        # 获取任务执行历史
        recent_tasks = []
        try:
            task_results = paper_gather_service.get_all_task_results()
            recent_tasks = sorted(task_results, key=lambda x: x['start_time'], reverse=True)[:10]
        except Exception as tasks_error:
            logger.error(f"获取任务历史失败: {tasks_error}")
            recent_tasks = []
        
        # 获取正在运行的定时任务
        scheduled_tasks = []
        try:
            scheduled_tasks = paper_gather_service.get_scheduled_tasks()
            if not scheduled_tasks:
                scheduled_tasks = []
        except Exception as scheduled_error:
            logger.error(f"获取定时任务失败: {scheduled_error}")
            scheduled_tasks = []
        
        # 获取运行中任务总数和详情
        running_tasks_count = 0
        running_tasks_detail = []
        try:
            running_tasks_count = paper_gather_service.get_running_tasks_count()
            running_tasks_detail = paper_gather_service.get_running_tasks_detail()
            if not running_tasks_detail:
                running_tasks_detail = []
        except Exception as running_error:
            logger.error(f"获取运行中任务失败: {running_error}")
            running_tasks_count = 0
            running_tasks_detail = []
        
        return render_template('index.html', 
                             explore_stats=explore_stats,
                             recent_papers=recent_papers,
                             recent_tasks=recent_tasks,
                             scheduled_tasks=scheduled_tasks,
                             running_tasks_count=running_tasks_count,
                             running_tasks_detail=running_tasks_detail)
    
    except Exception as e:
        logger.error(f"首页加载失败: {e}")
        return render_template('error.html', error="首页加载失败，请检查系统状态"), 500


@main_bp.route('/about')
def about():
    """关于页面"""
    return render_template('about.html')


@main_bp.route('/settings')
def settings():
    """系统设置页面"""
    try:
        # 获取可用模型列表
        available_models = []
        try:
            # 这里应该调用获取模型列表的服务
            # 暂时使用空列表，实际实现时需要从服务中获取
            from services.task_service import paper_gather_service
            available_models = paper_gather_service.get_available_models()
        except Exception as e:
            logger.warning(f"获取模型列表失败: {e}")
            available_models = []
        
        # 获取默认配置
        default_config = DEFAULT_TASK_CONFIG
        
        return render_template('settings.html',
                             available_models=available_models,
                             default_config=default_config)
    except Exception as e:
        logger.error(f"设置页面加载失败: {e}")
        return render_template('error.html', error="设置页面加载失败，请检查系统状态"), 500