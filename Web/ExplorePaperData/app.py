"""
ArXiv论文数据可视化Web应用
提供直观的论文数据探索界面
"""
from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_moment import Moment
from database import PaperService
from config import Config
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
    """注入当前时间到模板上下文"""
    from datetime import datetime
    return {'now': datetime.now()}

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
        page = int(request.args.get('page', 1))
        per_page = app.config['PAPERS_PER_PAGE']
        
        # 搜索论文
        papers, total = paper_service.search_papers(
            query=query, 
            category=category, 
            status=status, 
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
                             status=status)
    
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
        
        return render_template('paper_detail.html', paper=paper)
    
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
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('per_page', 10)), 50)  # 限制每页最多50条
        
        papers, total = paper_service.search_papers(
            query=query, 
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

@app.template_filter('status_badge')
def status_badge(status):
    """状态徽章过滤器"""
    status_map = {
        'pending': 'warning',
        'completed': 'success',
        'failed': 'danger'
    }
    return status_map.get(status, 'secondary')

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