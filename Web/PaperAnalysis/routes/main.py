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
        explore_stats = paper_explore_service.get_overview_stats()
        
        # 获取最近的论文
        recent_papers = paper_data_service.get_recent_papers(limit=10)
        
        # 获取任务执行历史
        task_results = paper_gather_service.get_all_task_results()
        recent_tasks = sorted(task_results, key=lambda x: x['start_time'], reverse=True)[:10]
        
        # 获取正在运行的定时任务
        scheduled_tasks = paper_gather_service.get_scheduled_tasks()
        
        # 获取运行中任务总数和详情
        running_tasks_count = paper_gather_service.get_running_tasks_count()
        running_tasks_detail = paper_gather_service.get_running_tasks_detail()
        
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