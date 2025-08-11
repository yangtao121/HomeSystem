"""
PaperAnalysis - 统一的论文收集与分析系统
整合了PaperGather和ExplorePaperData的所有功能
"""
from flask import Flask, render_template, request, jsonify
from flask.json.provider import DefaultJSONProvider
from flask_moment import Moment
from dotenv import load_dotenv
import logging
import sys
import os
import json
import signal
import time

# 加载环境变量
load_dotenv()

# 添加HomeSystem到路径
current_dir = os.path.dirname(__file__)
homesystem_root = os.path.normpath(os.path.join(current_dir, "..", ".."))
if homesystem_root not in sys.path:
    sys.path.insert(0, homesystem_root)

from config import Config
from routes.main import main_bp
from routes.collect import collect_bp
from routes.explore import explore_bp
from routes.analysis import analysis_bp, images_bp
from routes.task import task_bp
from routes.api import api_bp

# 导入ArxivSearchMode用于JSON序列化
from HomeSystem.utility.arxiv.arxiv import ArxivSearchMode


class CustomJSONProvider(DefaultJSONProvider):
    """自定义JSON提供器，处理ArxivSearchMode枚举和其他复杂对象"""
    
    def default(self, obj):
        if isinstance(obj, ArxivSearchMode):
            return obj.value
        return super().default(obj)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 创建Flask应用
app = Flask(__name__)
app.config.from_object(Config)

# 配置自定义JSON提供器
app.json = CustomJSONProvider(app)

# 初始化Flask-Moment
moment = Moment(app)

# 注册蓝图
app.register_blueprint(main_bp)
app.register_blueprint(collect_bp)
app.register_blueprint(explore_bp)
app.register_blueprint(analysis_bp)
app.register_blueprint(images_bp)  # 图片服务蓝图
app.register_blueprint(task_bp, url_prefix='/task')  # 任务执行蓝图
app.register_blueprint(api_bp)

# 添加模板上下文处理器
@app.context_processor
def inject_now():
    """注入当前时间到模板上下文"""
    from datetime import datetime
    try:
        # 尝试获取无任务论文数量
        from services.paper_explore_service import PaperService
        paper_service = PaperService()
        _, unassigned_count = paper_service.get_papers_without_tasks(page=1, per_page=1)
    except Exception as e:
        logger.warning(f"获取无任务论文数量失败: {e}")
        unassigned_count = 0
    
    return {
        'now': datetime.now(),
        'unassigned_papers_count': unassigned_count
    }

# 模板过滤器
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
        'running': 'info',
        'completed': 'success',
        'failed': 'danger',
        'stopped': 'secondary'
    }
    return status_map.get(status, 'secondary')

@app.template_filter('task_mode_badge')
def task_mode_badge(mode):
    """任务模式徽章过滤器"""
    mode_map = {
        'immediate': 'primary',
        'scheduled': 'info'
    }
    return mode_map.get(mode, 'secondary')

@app.template_filter('format_duration')
def format_duration(seconds):
    """格式化持续时间"""
    if not seconds:
        return "0秒"
    
    try:
        seconds = float(seconds)
        if seconds < 60:
            return f"{seconds:.1f}秒"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f}分钟"
        else:
            hours = seconds / 3600
            return f"{hours:.1f}小时"
    except (ValueError, TypeError):
        return "未知"

@app.template_filter('format_relevance_score')
def format_relevance_score(score):
    """格式化相关性分数"""
    if score is None:
        return "未评分"
    
    try:
        score = float(score)
        percentage = score * 100
        if percentage >= 80:
            badge_class = "success"
        elif percentage >= 60:
            badge_class = "warning"
        else:
            badge_class = "danger"
        
        return f'<span class="badge bg-{badge_class}">{percentage:.1f}%</span>'
    except (ValueError, TypeError):
        return "无效分数"

@app.template_filter('safe_strip')
def safe_strip(text):
    """安全strip过滤器"""
    if not text:
        return ""
    return str(text).strip()

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
    """相关性状态徽章过滤器"""
    if not isinstance(paper, dict):
        return ""
    
    score = paper.get('full_paper_relevance_score')
    if score is None:
        return '<span class="badge bg-secondary">未评分</span>'
    
    try:
        score = float(score)
        if score >= 8:
            return '<span class="badge bg-success">高相关</span>'
        elif score >= 6:
            return '<span class="badge bg-info">中相关</span>'
        elif score >= 4:
            return '<span class="badge bg-warning">低相关</span>'
        else:
            return '<span class="badge bg-danger">不相关</span>'
    except (ValueError, TypeError):
        return '<span class="badge bg-secondary">评分错误</span>'

@app.template_filter('relevance_score_stars')
def relevance_score_stars(paper):
    """相关性评分星星显示过滤器"""
    if not isinstance(paper, dict):
        return ""
    
    score = paper.get('full_paper_relevance_score')
    if score is None:
        return '<span class="text-muted">未评分</span>'
    
    try:
        score = float(score)
        full_stars = int(score // 2)  # Convert 10-point scale to 5-star scale
        half_star = 1 if (score % 2) >= 1 else 0
        empty_stars = 5 - full_stars - half_star
        
        stars_html = ''
        # Full stars
        for _ in range(full_stars):
            stars_html += '<i class="bi bi-star-fill text-warning"></i>'
        # Half star
        if half_star:
            stars_html += '<i class="bi bi-star-half text-warning"></i>'
        # Empty stars
        for _ in range(empty_stars):
            stars_html += '<i class="bi bi-star text-muted"></i>'
        
        stars_html += f' <span class="text-muted">({score:.1f})</span>'
        return stars_html
    except (ValueError, TypeError):
        return '<span class="text-muted">评分错误</span>'

@app.template_filter('relevance_justification_preview')
def relevance_justification_preview(paper, length=100):
    """相关性理由预览过滤器"""
    if not isinstance(paper, dict):
        return ""
    
    justification = paper.get('full_paper_relevance_justification', '')
    if not justification or not str(justification).strip():
        return '<span class="text-muted">无理由说明</span>'
    
    justification_str = str(justification).strip()
    if len(justification_str) <= length:
        return justification_str
    
    return justification_str[:length] + '...'

@app.template_filter('markdown')
def markdown_filter(text):
    """Markdown转HTML过滤器，支持HTML标签（包括视频）"""
    if not text:
        return ""
    
    try:
        import mistune
        # 创建支持HTML的markdown渲染器
        markdown = mistune.create_markdown(
            escape=False,  # 不转义HTML标签
            plugins=['strikethrough', 'footnotes', 'table']
        )
        return markdown(str(text))
    except ImportError:
        # 如果没有mistune，返回原始文本并转换换行符
        return str(text).replace('\n', '<br>')
    except Exception as e:
        logger.warning(f"Markdown转换失败: {e}")
        return str(text).replace('\n', '<br>')

# 错误处理
@app.errorhandler(404)
def not_found(error):
    """404错误处理"""
    return render_template('error.html', 
                         error="页面不存在",
                         error_code=404), 404

@app.errorhandler(500)
def internal_error(error):
    """500错误处理"""
    logger.error(f"内部错误: {error}")
    return render_template('error.html', 
                         error="服务器内部错误",
                         error_code=500), 500

@app.errorhandler(Exception)
def handle_exception(e):
    """通用异常处理"""
    logger.error(f"未处理的异常: {e}", exc_info=True)
    return render_template('error.html', 
                         error="系统发生异常，请稍后重试",
                         error_code=500), 500

# 应用启动前的初始化
def initialize():
    """应用首次启动时的初始化"""
    try:
        logger.info("🔧 开始应用初始化...")
        
        # 检查数据库连接
        try:
            from services.paper_explore_service import PaperService
            paper_service = PaperService()
            stats = paper_service.get_overview_stats()
            logger.info(f"📊 数据库连接正常，共有 {stats['basic']['total_papers']} 篇论文")
        except Exception as e:
            logger.warning(f"⚠️  数据库连接检查失败: {e}，功能可能受限")
        
        # 检查任务服务
        try:
            from services.task_service import paper_gather_service
            models = paper_gather_service.get_available_models()
            if models:
                logger.info(f"📦 发现 {len(models)} 个可用的LLM模型")
            else:
                logger.warning("⚠️  未发现可用的LLM模型")
        except Exception as e:
            logger.warning(f"⚠️  LLM模型检查失败: {e}")
        
        # 恢复被中断的深度分析任务
        try:
            logger.info("🔄 检查并恢复被中断的深度分析任务...")
            from services.paper_explore_service import PaperService
            paper_service = PaperService()
            
            # 恢复被中断的分析
            recovery_result = paper_service.recover_interrupted_analysis()
            if recovery_result['success']:
                if recovery_result['recovered_count'] > 0:
                    logger.info(f"✅ 成功恢复 {recovery_result['recovered_count']} 个被中断的深度分析任务")
                    for paper in recovery_result['interrupted_papers']:
                        logger.info(f"   - {paper['arxiv_id']}: {paper['title'][:50]}...")
                else:
                    logger.info("✅ 没有发现被中断的深度分析任务")
            else:
                logger.warning(f"⚠️ 恢复中断任务失败: {recovery_result.get('error', '未知错误')}")
            
            # 重置超时的分析任务（超过2小时仍在processing状态）
            stuck_result = paper_service.reset_stuck_analysis(max_hours=2)
            if stuck_result['success'] and stuck_result['reset_count'] > 0:
                logger.warning(f"⚠️ 发现并重置了 {stuck_result['reset_count']} 个超时的深度分析任务")
                for paper in stuck_result['stuck_papers']:
                    logger.warning(f"   - {paper['arxiv_id']}: 卡住 {paper['hours_stuck']:.1f} 小时")
            
        except Exception as e:
            logger.warning(f"⚠️ 深度分析状态恢复失败: {e}")
        
        logger.info("✅ 应用初始化完成")
        
    except Exception as e:
        logger.warning(f"⚠️  应用初始化部分失败: {e}，应用将继续启动")

def startup_with_timeout(timeout_seconds=60):
    """带超时保护的启动函数"""
    import threading
    result = [False]
    
    def startup_task():
        try:
            logger.info("🚀 开始启动PaperAnalysis应用...")
            start_time = time.time()
            
            initialize()
            
            elapsed_time = time.time() - start_time
            logger.info(f"⏱️  启动准备耗时: {elapsed_time:.2f} 秒")
            
            result[0] = True
            
        except Exception as e:
            logger.error(f"❌ 启动过程异常: {e}")
            result[0] = False
    
    startup_thread = threading.Thread(target=startup_task)
    startup_thread.daemon = True
    startup_thread.start()
    
    startup_thread.join(timeout=timeout_seconds)
    
    if startup_thread.is_alive():
        logger.error(f"❌ 应用启动超时 ({timeout_seconds} 秒)")
        print("❌ 应用启动超时！请检查系统状态并重试")
        return False
    
    if result[0]:
        logger.info("🌐 启动Web服务器...")
        logger.info(f"🚀 PaperAnalysis应用启动完成！")
        logger.info(f"📍 访问地址: http://{app.config['HOST']}:{app.config['PORT']}")
        logger.info("=" * 60)
        
        app.run(
            host=app.config['HOST'], 
            port=app.config['PORT'], 
            debug=app.config['DEBUG'],
            threaded=True
        )
        return True
    else:
        return False

if __name__ == '__main__':
    try:
        success = startup_with_timeout(60)
        if not success:
            exit(1)
        
    except Exception as e:
        logger.error(f"❌ 应用启动失败: {e}", exc_info=True)
        print("❌ 应用启动失败，请检查:")
        print("1. 数据库服务是否正常运行 (docker compose up -d)")
        print("2. HomeSystem模块是否可以正常导入")
        print("3. 环境变量配置是否正确")
        print("4. 依赖包是否完整安装")
        print("5. 端口是否被其他应用占用")
        exit(1)