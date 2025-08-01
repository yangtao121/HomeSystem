"""
PaperGather Web应用
论文收集任务的Web界面
"""
from flask import Flask, render_template, request, jsonify
from flask.json.provider import DefaultJSONProvider
from flask_moment import Moment
from dotenv import load_dotenv
import logging
import sys
import os
import json

# 加载环境变量
load_dotenv()

# 添加HomeSystem到路径
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from config import Config
from routes.main import main_bp
from routes.task import task_bp
from routes.api import api_bp
from services.task_service import paper_gather_service
from services.paper_service import paper_data_service
import signal
import time

# 导入ArxivSearchMode用于JSON序列化
from HomeSystem.utility.arxiv.arxiv import ArxivSearchMode


class CustomJSONProvider(DefaultJSONProvider):
    """自定义JSON提供器，处理ArxivSearchMode枚举"""
    
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

# 配置自定义JSON提供器（Flask 3.0+方式）
app.json = CustomJSONProvider(app)

# 初始化Flask-Moment
moment = Moment(app)

# 注册蓝图
app.register_blueprint(main_bp)
app.register_blueprint(task_bp, url_prefix='/task')
app.register_blueprint(api_bp)

# 添加模板上下文处理器
@app.context_processor
def inject_now():
    """注入当前时间到模板上下文"""
    from datetime import datetime
    return {'now': datetime.now()}

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
        
        return f'<span class="badge badge-{badge_class}">{percentage:.1f}%</span>'
    except (ValueError, TypeError):
        return "无效分数"

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

# 应用启动前的初始化（移除了已废弃的before_first_request装饰器）
def initialize():
    """应用首次启动时的初始化"""
    try:
        # 清理旧的任务结果
        paper_gather_service.cleanup_old_results(keep_last_n=100)
        logger.info("应用初始化完成")
    except Exception as e:
        logger.error(f"应用初始化失败: {e}")

def startup_with_timeout(timeout_seconds=60):
    """带超时保护的启动函数"""
    def timeout_handler(signum, frame):
        raise TimeoutError(f"应用启动超时 ({timeout_seconds} 秒)")
    
    # 设置超时处理
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(timeout_seconds)
    
    try:
        logger.info("🚀 开始启动PaperGather Web应用...")
        start_time = time.time()
        
        # 初始化应用
        logger.info("📋 初始化应用基础设施中...")
        initialize()
        logger.info("✅ 应用基础设施初始化完成")
        
        # 测试服务连接 - 使用超时保护
        logger.info("🔍 检查服务连接状态...")
        try:
            models = paper_gather_service.get_available_models()
            logger.info(f"📦 发现 {len(models)} 个可用的LLM模型")
        except Exception as e:
            logger.warning(f"⚠️  LLM模型检查失败: {e}，应用将继续启动")
        
        try:
            stats = paper_data_service.get_paper_statistics()
            logger.info(f"📊 数据库中有 {stats['total_papers']} 篇论文")
        except Exception as e:
            logger.warning(f"⚠️  数据库统计检查失败: {e}，应用将继续启动")
        
        # 启动后台服务初始化
        logger.info("🔧 启动后台服务初始化...")
        paper_gather_service.initialize_background_services()
        
        # 计算启动时间
        elapsed_time = time.time() - start_time
        logger.info(f"⏱️  启动准备耗时: {elapsed_time:.2f} 秒")
        
        # 取消超时警报
        signal.alarm(0)
        
        # 启动应用
        logger.info("🌐 启动Web服务器...")
        logger.info(f"🚀 PaperGather Web应用启动完成！")
        logger.info(f"📍 访问地址: http://{app.config['HOST']}:{app.config['PORT']}")
        logger.info("=" * 60)
        
        app.run(
            host=app.config['HOST'], 
            port=app.config['PORT'], 
            debug=app.config['DEBUG'],
            threaded=True  # 启用多线程支持
        )
        
    except TimeoutError as e:
        logger.error(f"❌ {e}")
        print("❌ 应用启动超时！可能的原因:")
        print("1. LLM服务响应过慢或不可用")
        print("2. 数据库连接异常")  
        print("3. 网络连接问题")
        print("4. 系统资源不足")
        print("建议检查服务状态并重试")
        return False
    finally:
        # 确保取消超时警报
        signal.alarm(0)

if __name__ == '__main__':
    try:
        success = startup_with_timeout(60)  # 60秒超时
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