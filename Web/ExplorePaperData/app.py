"""
ArXiv论文数据可视化Web应用
提供直观的论文数据探索界面
"""
from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_moment import Moment
from database import PaperService
from config import Config
from utils.markdown_utils import markdown_filter, markdown_safe_filter
import logging
import math

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config.from_object(Config)

# 初始化Flask-Moment
moment = Moment(app)

# 初始化服务
paper_service = PaperService()

# 添加模板上下文处理器
@app.context_processor
def inject_now():
    """注入当前时间和无任务论文数量到模板上下文"""
    from datetime import datetime
    try:
        # 获取无任务论文数量
        _, unassigned_count = paper_service.get_papers_without_tasks(page=1, per_page=1)
        return {
            'now': datetime.now(),
            'unassigned_papers_count': unassigned_count
        }
    except Exception as e:
        logger.warning(f"获取无任务论文数量失败: {e}")
        return {
            'now': datetime.now(),
            'unassigned_papers_count': 0
        }

@app.route('/')
def index():
    """首页 - 仪表板概览"""
    try:
        stats = paper_service.get_overview_stats()
        return render_template('index.html', stats=stats)
    except Exception as e:
        logger.error(f"首页加载失败: {e}")
        return render_template('error.html', error="数据库连接失败，请检查数据库服务状态"), 500

@app.route('/papers')
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
        per_page = app.config['PAPERS_PER_PAGE']
        
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
        
        return render_template('papers.html', 
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

@app.route('/paper/<arxiv_id>')
def paper_detail(arxiv_id):
    """论文详情页面"""
    try:
        paper = paper_service.get_paper_detail(arxiv_id)
        if not paper:
            return render_template('error.html', error="论文不存在"), 404
        
        # 获取导航信息
        navigation = paper_service.get_paper_navigation(arxiv_id)
        
        return render_template('paper_detail.html', paper=paper, navigation=navigation)
    
    except Exception as e:
        logger.error(f"论文详情加载失败: {e}")
        return render_template('error.html', error="加载论文详情失败"), 500

@app.route('/stats')
def statistics():
    """统计分析页面"""
    try:
        stats = paper_service.get_statistics()
        return render_template('stats.html', stats=stats)
    
    except Exception as e:
        logger.error(f"统计数据加载失败: {e}")
        return render_template('error.html', error="加载统计数据失败"), 500

@app.route('/insights')
def insights():
    """研究洞察页面"""
    try:
        insights = paper_service.get_research_insights()
        return render_template('insights.html', insights=insights)
    
    except Exception as e:
        logger.error(f"研究洞察加载失败: {e}")
        return render_template('error.html', error="加载研究洞察失败"), 500

@app.route('/api/search')
def api_search():
    """API接口 - 搜索论文"""
    try:
        query = request.args.get('q', '').strip()
        task_name = request.args.get('task_name', '').strip()
        task_id = request.args.get('task_id', '').strip()
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('per_page', 10)), 50)  # 限制每页最多50条
        
        papers, total = paper_service.search_papers(
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
            'total_pages': math.ceil(total / per_page)
        })
    
    except Exception as e:
        logger.error(f"API搜索失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/stats')
def api_stats():
    """API接口 - 获取统计数据"""
    try:
        stats = paper_service.get_overview_stats()
        return jsonify({'success': True, 'data': stats})
    
    except Exception as e:
        logger.error(f"API统计数据获取失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/tasks')
def api_tasks():
    """API接口 - 获取可用任务列表"""
    try:
        tasks = paper_service.get_available_tasks()
        return jsonify({'success': True, 'data': tasks})
    
    except Exception as e:
        logger.error(f"获取任务列表失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/update_task_name', methods=['POST'])
def api_update_task_name():
    """API接口 - 更新任务名称"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': '无效的请求数据'}), 400
        
        arxiv_id = data.get('arxiv_id')
        new_task_name = (data.get('new_task_name') or '').strip()
        
        if not arxiv_id:
            return jsonify({'success': False, 'error': '缺少论文ID'}), 400
            
        success = paper_service.update_task_name(arxiv_id, new_task_name)
        
        if success:
            return jsonify({'success': True, 'message': '任务名称更新成功'})
        else:
            return jsonify({'success': False, 'error': '更新失败，论文不存在'}), 404
    
    except Exception as e:
        logger.error(f"更新任务名称失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/batch_update_task_name', methods=['POST'])
def api_batch_update_task_name():
    """API接口 - 批量更新任务名称"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': '无效的请求数据'}), 400
        
        old_task_name = (data.get('old_task_name') or '').strip()
        new_task_name = (data.get('new_task_name') or '').strip()
        
        if not old_task_name or not new_task_name:
            return jsonify({'success': False, 'error': '缺少必要参数'}), 400
            
        affected_rows = paper_service.batch_update_task_name(old_task_name, new_task_name)
        
        return jsonify({
            'success': True, 
            'message': f'成功更新 {affected_rows} 篇论文的任务名称',
            'affected_rows': affected_rows
        })
    
    except Exception as e:
        logger.error(f"批量更新任务名称失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/delete_paper/<arxiv_id>', methods=['DELETE'])
def api_delete_paper(arxiv_id):
    """API接口 - 删除单个论文"""
    try:
        success = paper_service.delete_paper(arxiv_id)
        
        if success:
            return jsonify({'success': True, 'message': '论文删除成功'})
        else:
            return jsonify({'success': False, 'error': '删除失败，论文不存在'}), 404
    
    except Exception as e:
        logger.error(f"删除论文失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/delete_task', methods=['DELETE'])
def api_delete_task():
    """API接口 - 按任务删除论文"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': '无效的请求数据'}), 400
        
        task_name = (data.get('task_name') or '').strip()
        task_id = (data.get('task_id') or '').strip()
        
        if not task_name and not task_id:
            return jsonify({'success': False, 'error': '必须提供任务名称或任务ID'}), 400
            
        affected_rows = paper_service.delete_papers_by_task(task_name=task_name, task_id=task_id)
        
        return jsonify({
            'success': True, 
            'message': f'成功删除 {affected_rows} 篇论文',
            'affected_rows': affected_rows
        })
    
    except Exception as e:
        logger.error(f"按任务删除论文失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/papers_without_tasks')
def api_papers_without_tasks():
    """API接口 - 获取没有分配任务的论文"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        papers, total = paper_service.get_papers_without_tasks(page=page, per_page=per_page)
        
        return jsonify({
            'success': True,
            'papers': papers,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'pages': (total + per_page - 1) // per_page
            }
        })
    
    except Exception as e:
        logger.error(f"获取无任务论文失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/assign_task_to_paper', methods=['POST'])
def api_assign_task_to_paper():
    """API接口 - 为单个论文分配任务"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': '无效的请求数据'}), 400
        
        arxiv_id = (data.get('arxiv_id') or '').strip()
        task_name = (data.get('task_name') or '').strip()
        task_id = (data.get('task_id') or '').strip() or None
        
        if not arxiv_id or not task_name:
            return jsonify({'success': False, 'error': '缺少必要参数'}), 400
            
        success = paper_service.assign_task_to_paper(arxiv_id, task_name, task_id)
        
        if success:
            return jsonify({'success': True, 'message': '任务分配成功'})
        else:
            return jsonify({'success': False, 'error': '分配失败，论文不存在'}), 404
    
    except Exception as e:
        logger.error(f"分配任务失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/batch_assign_task', methods=['POST'])
def api_batch_assign_task():
    """API接口 - 批量为论文分配任务"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': '无效的请求数据'}), 400
        
        arxiv_ids = data.get('arxiv_ids', [])
        task_name = (data.get('task_name') or '').strip()
        task_id = (data.get('task_id') or '').strip() or None
        
        if not arxiv_ids or not task_name:
            return jsonify({'success': False, 'error': '缺少必要参数'}), 400
            
        if not isinstance(arxiv_ids, list):
            return jsonify({'success': False, 'error': 'arxiv_ids必须是数组'}), 400
            
        affected_rows = paper_service.batch_assign_task_to_papers(arxiv_ids, task_name, task_id)
        
        return jsonify({
            'success': True, 
            'message': f'成功为 {affected_rows} 篇论文分配任务',
            'affected_rows': affected_rows
        })
    
    except Exception as e:
        logger.error(f"批量分配任务失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/unassigned_stats')
def api_unassigned_stats():
    """API接口 - 获取无任务论文统计信息"""
    try:
        stats = paper_service.get_unassigned_papers_stats()
        return jsonify({'success': True, 'stats': stats})
    
    except Exception as e:
        logger.error(f"获取无任务论文统计失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/update_relevance', methods=['POST'])
def api_update_relevance():
    """API接口 - 更新论文相关度评分和理由"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': '无效的请求数据'}), 400
        
        arxiv_id = (data.get('arxiv_id') or '').strip()
        relevance_score = data.get('relevance_score')
        relevance_justification = data.get('relevance_justification')
        
        if not arxiv_id:
            return jsonify({'success': False, 'error': '缺少论文ID'}), 400
        
        # 验证和转换评分
        if relevance_score is not None:
            try:
                relevance_score = float(relevance_score)
                if not (0 <= relevance_score <= 1):
                    return jsonify({'success': False, 'error': '评分必须在0-1之间'}), 400
            except (ValueError, TypeError):
                return jsonify({'success': False, 'error': '评分必须是有效的数字'}), 400
        
        # 验证理由长度
        if relevance_justification is not None:
            relevance_justification = str(relevance_justification).strip()
            if len(relevance_justification) > 5000:
                return jsonify({'success': False, 'error': '理由长度不能超过5000字符'}), 400
        
        # 检查是否至少提供了一个字段
        if relevance_score is None and not relevance_justification:
            return jsonify({'success': False, 'error': '必须提供评分或理由'}), 400
        
        # 更新相关度
        success = paper_service.update_paper_relevance(
            arxiv_id=arxiv_id,
            relevance_score=relevance_score,
            relevance_justification=relevance_justification
        )
        
        if success:
            return jsonify({
                'success': True, 
                'message': '相关度更新成功',
                'data': {
                    'arxiv_id': arxiv_id,
                    'relevance_score': relevance_score,
                    'relevance_justification': relevance_justification
                }
            })
        else:
            return jsonify({'success': False, 'error': '更新失败，论文不存在'}), 404
    
    except Exception as e:
        logger.error(f"更新相关度失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/tasks')
def tasks():
    """任务管理页面"""
    try:
        tasks = paper_service.get_available_tasks()
        task_stats = paper_service.get_task_statistics()
        return render_template('tasks.html', tasks=tasks, stats=task_stats)
    
    except Exception as e:
        logger.error(f"任务页面加载失败: {e}")
        return render_template('error.html', error="加载任务页面失败"), 500

@app.route('/unassigned')
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
        
        return render_template('unassigned.html', 
                             papers=papers, 
                             pagination=pagination,
                             stats=stats)
    
    except Exception as e:
        logger.error(f"无任务论文页面加载失败: {e}")
        return render_template('error.html', error="加载无任务论文页面失败"), 500

@app.errorhandler(404)
def not_found(error):
    """404错误处理"""
    return render_template('error.html', error="页面不存在"), 404

@app.errorhandler(500)
def internal_error(error):
    """500错误处理"""
    logger.error(f"内部错误: {error}")
    return render_template('error.html', error="服务器内部错误"), 500

@app.template_filter('truncate_text')
def truncate_text(text, length=100):
    """截断文本过滤器"""
    if not text:
        return ""
    if len(text) <= length:
        return text
    return text[:length] + "..."

@app.template_filter('format_date')
def format_date(date_obj):
    """日期格式化过滤器"""
    if not date_obj:
        return ""
    
    # 如果是字符串，尝试解析为datetime对象
    if isinstance(date_obj, str):
        try:
            from datetime import datetime
            # 尝试解析ISO格式的日期字符串
            if 'T' in date_obj:
                date_obj = datetime.fromisoformat(date_obj.replace('Z', '+00:00'))
            else:
                # 尝试解析其他常见格式
                date_obj = datetime.strptime(date_obj, '%Y-%m-%d %H:%M:%S')
        except (ValueError, AttributeError):
            # 如果解析失败，直接返回原字符串
            return str(date_obj)
    
    # 如果是datetime对象，格式化输出
    try:
        return date_obj.strftime('%Y-%m-%d %H:%M')
    except AttributeError:
        # 如果对象没有strftime方法，返回字符串表示
        return str(date_obj)

@app.template_filter('safe_strip')
def safe_strip(text):
    """安全strip过滤器"""
    if not text:
        return ""
    return str(text).strip()

@app.template_filter('status_badge')
def status_badge(status):
    """状态徽章过滤器"""
    status_map = {
        'pending': 'warning',
        'completed': 'success',
        'failed': 'danger'
    }
    return status_map.get(status, 'secondary')

@app.template_filter('relevance_score_display')
def relevance_score_display(score):
    """相关度评分显示过滤器"""
    if score is None:
        return "未评分"
    try:
        score_float = float(score)
        return f"{score_float:.2f}"
    except (ValueError, TypeError):
        return "未评分"

@app.template_filter('relevance_score_stars')
def relevance_score_stars(score):
    """相关度评分星级显示过滤器"""
    if score is None:
        return '<span class="text-muted">☆☆☆☆☆</span>'
    
    try:
        score_float = float(score)
        # 将0-1的评分转换为5星显示
        stars_count = round(score_float * 5)
        filled_stars = '★' * stars_count
        empty_stars = '☆' * (5 - stars_count)
        
        # 根据评分设置颜色
        if score_float >= 0.8:
            color_class = 'text-success'
        elif score_float >= 0.5:
            color_class = 'text-warning'
        else:
            color_class = 'text-danger'
        
        return f'<span class="{color_class}">{filled_stars}{empty_stars}</span>'
    except (ValueError, TypeError):
        return '<span class="text-muted">☆☆☆☆☆</span>'

@app.template_filter('relevance_justification_display')
def relevance_justification_display(justification):
    """相关度理由显示过滤器"""
    if not justification or str(justification).strip() == '':
        return "暂无评分理由"
    return str(justification).strip()

@app.template_filter('relevance_justification_preview')
def relevance_justification_preview(justification, length=100):
    """相关度理由预览过滤器（截断显示）"""
    if not justification or str(justification).strip() == '':
        return "暂无理由"
    
    text = str(justification).strip()
    if len(text) <= length:
        return text
    return text[:length] + "..."

@app.template_filter('has_relevance_data')
def has_relevance_data(paper):
    """检查论文是否有相关度数据"""
    if not isinstance(paper, dict):
        return False
    
    has_score = paper.get('full_paper_relevance_score') is not None
    has_justification = bool(str(paper.get('full_paper_relevance_justification', '')).strip())
    
    return has_score or has_justification

@app.template_filter('relevance_status_badge')
def relevance_status_badge(paper):
    """相关度状态徽章过滤器"""
    if not isinstance(paper, dict):
        return '<span class="badge bg-secondary">未知</span>'
    
    has_score = paper.get('full_paper_relevance_score') is not None
    has_justification = bool(str(paper.get('full_paper_relevance_justification', '')).strip())
    
    if has_score and has_justification:
        return '<span class="badge bg-success"><i class="bi bi-check-circle"></i> 已完整评分</span>'
    elif has_score:
        return '<span class="badge bg-info"><i class="bi bi-star"></i> 仅有评分</span>'
    elif has_justification:
        return '<span class="badge bg-warning"><i class="bi bi-chat-text"></i> 仅有理由</span>'
    else:
        return '<span class="badge bg-secondary"><i class="bi bi-question-circle"></i> 未评分</span>'

@app.template_filter('markdown')
def markdown_template_filter(text):
    """Markdown模板过滤器"""
    return markdown_filter(text)

@app.template_filter('markdown_safe')
def markdown_safe_template_filter(text):
    """安全Markdown模板过滤器"""
    return markdown_safe_filter(text)

if __name__ == '__main__':
    try:
        # 测试数据库连接
        test_stats = paper_service.get_overview_stats()
        logger.info("数据库连接测试成功")
        logger.info(f"发现 {test_stats['basic']['total_papers']} 篇论文")
        
        # 启动应用
        app.run(
            host=app.config['HOST'], 
            port=app.config['PORT'], 
            debug=app.config['DEBUG']
        )
    except Exception as e:
        logger.error(f"应用启动失败: {e}")
        print("❌ 应用启动失败，请检查:")
        print("1. 数据库服务是否正常运行 (docker compose up -d)")
        print("2. 环境变量配置是否正确")
        print("3. 依赖包是否完整安装")