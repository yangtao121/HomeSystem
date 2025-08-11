"""
论文浏览路由 - 来自ExplorePaperData的功能
包括论文搜索、详情、统计、洞察等功能
"""
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, send_file
from services.paper_explore_service import PaperService, DifyService
from HomeSystem.integrations.paper_analysis.analysis_service import PaperAnalysisService
from HomeSystem.integrations.database import DatabaseOperations, ArxivPaperModel
import logging
import math
import os
import sys
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

explore_bp = Blueprint('explore', __name__, url_prefix='/explore')

# 初始化服务
paper_service = PaperService()
dify_service = DifyService()
db_ops = DatabaseOperations()

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
analysis_service = AnalysisServiceAdapter(paper_service, redis_client)


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
        # 支持多个任务名称
        task_names = request.args.getlist('task_name')
        task_names = [name.strip() for name in task_names if name.strip()]
        task_id = request.args.get('task_id', '').strip()
        page = int(request.args.get('page', 1))
        per_page = 20
        
        # 获取所有任务名称列表（用于下拉框选项）
        all_task_names = paper_service.get_all_task_names()
        
        # 如果没有指定任务筛选，默认选择所有任务（显示全部论文）
        if not task_names:
            task_names = all_task_names + ['未分配任务']
        
        # 搜索论文
        papers, total = paper_service.search_papers(
            query=query, 
            category=category, 
            status=status,
            task_name=task_names,
            task_id=task_id,
            page=page, 
            per_page=per_page
        )
        
        # 计算分页信息
        total_pages = math.ceil(total / per_page)
        has_prev = page > 1
        has_next = page < total_pages
        
        class Pagination:
            def __init__(self, page, per_page, total):
                self.page = page
                self.per_page = per_page
                self.total = total
                self.total_pages = math.ceil(total / per_page)
                self.has_prev = page > 1
                self.has_next = page < self.total_pages
                self.prev_num = page - 1 if self.has_prev else None
                self.next_num = page + 1 if self.has_next else None
            
            def iter_pages(self, left_edge=2, right_edge=2, left_current=2, right_current=3):
                """生成分页页码"""
                last = self.total_pages
                for num in range(1, last + 1):
                    if (num <= left_edge or 
                        (self.page - left_current - 1 < num < self.page + right_current) or
                        num > last - right_edge):
                        yield num
        
        pagination = Pagination(page, per_page, total)
        
        return render_template('explore/papers.html', 
                             papers=papers, 
                             pagination=pagination,
                             query=query,
                             category=category,
                             status=status,
                             task_names=task_names,
                             all_task_names=all_task_names,
                             task_id=task_id)
    
    except Exception as e:
        logger.error(f"论文搜索失败: {e}")
        return render_template('error.html', error="搜索失败，请稍后重试"), 500


@explore_bp.route('/paper/<arxiv_id>')
def paper_detail(arxiv_id):
    """论文详情页面"""
    try:
        # 使用DatabaseOperations查询，确保与上传流程使用相同数据源
        paper_model = db_ops.get_by_field(ArxivPaperModel, 'arxiv_id', arxiv_id)
        if not paper_model:
            return render_template('error.html', error="论文不存在"), 404
        
        # 转换为字典格式，保持模板兼容性
        paper = paper_model.to_dict()
        
        # 获取导航信息（仍使用原服务，因为需要复杂查询）
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
        paper_model = db_ops.get_by_field(ArxivPaperModel, 'arxiv_id', arxiv_id)
        if not paper_model:
            return render_template('error.html', error="论文不存在"), 404
        
        paper = paper_model.to_dict()
        
        return render_template('explore/paper_analysis.html', 
                             paper=paper, 
                             analysis=result)
    
    except Exception as e:
        logger.error(f"显示分析结果失败 {arxiv_id}: {e}")
        return render_template('error.html', error="加载分析结果失败"), 500


@explore_bp.route('/paper/<arxiv_id>/videos/<filename>')
def serve_analysis_video_explore(arxiv_id, filename):
    """为探索页面提供视频服务路由"""
    try:
        # 重用 images_bp 中的视频服务逻辑
        from routes.analysis import serve_analysis_video
        return serve_analysis_video(arxiv_id, filename)
        
    except Exception as e:
        logger.error(f"Explore视频服务失败 {arxiv_id}/{filename}: {e}")
        return "Server error", 500


@explore_bp.route('/batch_operations', methods=['GET', 'POST'])
def batch_operations():
    """批量操作页面"""
    try:
        selected_papers = []
        
        if request.method == 'POST':
            # 从POST数据中获取选中的论文
            selected_papers_data = request.form.get('selected_papers')
            if selected_papers_data:
                import json
                selected_paper_ids = [p['arxiv_id'] for p in json.loads(selected_papers_data)]
                # 获取完整的论文信息
                for arxiv_id in selected_paper_ids:
                    paper_model = db_ops.get_by_field(ArxivPaperModel, 'arxiv_id', arxiv_id)
                    if paper_model:
                        paper = paper_model.to_dict()
                        selected_papers.append(paper)
        
        # 计算统计信息
        with_task_count = len([p for p in selected_papers if p.get('task_name')])
        without_task_count = len(selected_papers) - with_task_count
        uploaded_to_dify_count = len([p for p in selected_papers if p.get('dify_document_id')])
        
        return render_template('explore/batch_operations.html',
                             selected_papers=selected_papers,
                             with_task_count=with_task_count,
                             without_task_count=without_task_count,
                             uploaded_to_dify_count=uploaded_to_dify_count)
    
    except Exception as e:
        logger.error(f"批量操作页面加载失败: {e}")
        return render_template('error.html', error="加载批量操作页面失败"), 500