"""
论文浏览路由 - 来自ExplorePaperData的功能
包括论文搜索、详情、统计、洞察等功能
"""
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, send_file
from services.paper_explore_service import PaperService, DifyService
from services.analysis_service import DeepAnalysisService
import logging
import math
import os
import sys

logger = logging.getLogger(__name__)

explore_bp = Blueprint('explore', __name__, url_prefix='/explore')

# 初始化服务
paper_service = PaperService()
dify_service = DifyService()

# 添加HomeSystem模块路径以导入LLMFactory
PROJECT_ROOT = os.path.join(os.path.dirname(__file__), '..', '..', '..')
sys.path.append(PROJECT_ROOT)

# 初始化Redis连接用于配置存储
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
    logger.info("Redis连接成功")
except Exception as e:
    logger.warning(f"Redis连接失败，将使用内存存储: {e}")
    redis_client = None

# 初始化分析服务
analysis_service = DeepAnalysisService(paper_service, redis_client)


@explore_bp.route('/')
def index():
    """浏览功能首页"""
    try:
        stats = paper_service.get_overview_stats()
        return render_template('explore/index.html', stats=stats)
    except Exception as e:
        logger.error(f"浏览首页加载失败: {e}")
        return render_template('error.html', error="数据库连接失败，请检查数据库服务状态"), 500


@explore_bp.route('/papers')
def papers():
    """论文浏览页面"""
    try:
        # 获取查询参数
        query = request.args.get('q', '').strip()
        category = request.args.get('category', '').strip()
        status = request.args.get('status', '').strip()
        task_name = request.args.get('task_name', '').strip()
        task_id = request.args.get('task_id', '').strip()
        page = int(request.args.get('page', 1))
        per_page = 20
        
        # 搜索论文
        papers, total = paper_service.search_papers(
            query=query, 
            category=category, 
            status=status,
            task_name=task_name,
            task_id=task_id,
            page=page, 
            per_page=per_page
        )
        
        # 计算分页信息
        total_pages = math.ceil(total / per_page)
        has_prev = page > 1
        has_next = page < total_pages
        
        pagination = {
            'page': page,
            'per_page': per_page,
            'total': total,
            'total_pages': total_pages,
            'has_prev': has_prev,
            'has_next': has_next,
            'prev_num': page - 1 if has_prev else None,
            'next_num': page + 1 if has_next else None
        }
        
        return render_template('explore/papers.html', 
                             papers=papers, 
                             pagination=pagination,
                             query=query,
                             category=category,
                             status=status,
                             task_name=task_name,
                             task_id=task_id)
    
    except Exception as e:
        logger.error(f"论文搜索失败: {e}")
        return render_template('error.html', error="搜索失败，请稍后重试"), 500


@explore_bp.route('/paper/<arxiv_id>')
def paper_detail(arxiv_id):
    """论文详情页面"""
    try:
        paper = paper_service.get_paper_detail(arxiv_id)
        if not paper:
            return render_template('error.html', error="论文不存在"), 404
        
        # 获取导航信息
        navigation = paper_service.get_paper_navigation(arxiv_id)
        
        return render_template('explore/paper_detail.html', paper=paper, navigation=navigation)
    
    except Exception as e:
        logger.error(f"论文详情加载失败: {e}")
        return render_template('error.html', error="加载论文详情失败"), 500


@explore_bp.route('/stats')
def statistics():
    """统计分析页面"""
    try:
        stats = paper_service.get_statistics()
        return render_template('explore/stats.html', stats=stats)
    
    except Exception as e:
        logger.error(f"统计数据加载失败: {e}")
        return render_template('error.html', error="加载统计数据失败"), 500


@explore_bp.route('/insights')
def insights():
    """研究洞察页面"""
    try:
        insights = paper_service.get_research_insights()
        return render_template('explore/insights.html', insights=insights)
    
    except Exception as e:
        logger.error(f"研究洞察加载失败: {e}")
        return render_template('error.html', error="加载研究洞察失败"), 500


@explore_bp.route('/tasks')
def tasks():
    """任务管理页面"""
    try:
        tasks = paper_service.get_available_tasks()
        task_stats = paper_service.get_task_statistics()
        return render_template('explore/tasks.html', tasks=tasks, stats=task_stats)
    
    except Exception as e:
        logger.error(f"任务页面加载失败: {e}")
        return render_template('error.html', error="加载任务页面失败"), 500


@explore_bp.route('/unassigned')
def unassigned_papers():
    """无任务论文管理页面"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 20
        
        papers, total = paper_service.get_papers_without_tasks(page=page, per_page=per_page)
        stats = paper_service.get_unassigned_papers_stats()
        
        pagination = {
            'page': page,
            'per_page': per_page,
            'total': total,
            'pages': (total + per_page - 1) // per_page
        }
        
        return render_template('explore/unassigned.html', 
                             papers=papers, 
                             pagination=pagination,
                             stats=stats)
    
    except Exception as e:
        logger.error(f"无任务论文页面加载失败: {e}")
        return render_template('error.html', error="加载无任务论文页面失败"), 500


@explore_bp.route('/paper/<arxiv_id>/analysis')
def paper_analysis_view(arxiv_id):
    """论文深度分析显示页面"""
    try:
        # 获取分析结果
        result = analysis_service.get_analysis_result(arxiv_id)
        
        if not result['success']:
            return render_template('error.html', 
                                   error="分析结果不存在，请先进行深度分析"), 404
        
        # 获取论文基本信息
        paper = paper_service.get_paper_detail(arxiv_id)
        if not paper:
            return render_template('error.html', error="论文不存在"), 404
        
        return render_template('explore/paper_analysis.html', 
                             paper=paper, 
                             analysis=result)
    
    except Exception as e:
        logger.error(f"显示分析结果失败 {arxiv_id}: {e}")
        return render_template('error.html', error="加载分析结果失败"), 500