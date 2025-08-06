"""
深度分析路由 - 论文深度分析功能
包括深度分析、公式纠错等高级功能
"""
from flask import Blueprint, render_template, request, jsonify, send_file
from services.paper_explore_service import PaperService
from services.analysis_service import DeepAnalysisService
import logging
import os
import sys
import tempfile
import zipfile
import re

logger = logging.getLogger(__name__)

analysis_bp = Blueprint('analysis', __name__, url_prefix='/analysis')

# 初始化服务
paper_service = PaperService()

# 添加HomeSystem模块路径
PROJECT_ROOT = os.path.join(os.path.dirname(__file__), '..', '..', '..')
sys.path.append(PROJECT_ROOT)

# 初始化Redis连接
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
    logger.info("Analysis模块Redis连接成功")
except Exception as e:
    logger.warning(f"Analysis模块Redis连接失败: {e}")
    redis_client = None

# 初始化分析服务
analysis_service = DeepAnalysisService(paper_service, redis_client)


@analysis_bp.route('/')
def index():
    """分析功能首页"""
    try:
        # 获取活跃的分析任务
        active_analyses = analysis_service.get_active_analyses()
        
        # 获取一些基本统计
        stats = {
            'active_analyses': len(active_analyses.get('data', [])),
            'total_papers': paper_service.get_overview_stats()['basic']['total_papers']
        }
        
        return render_template('analysis/index.html', 
                             stats=stats,
                             active_analyses=active_analyses)
    
    except Exception as e:
        logger.error(f"分析首页加载失败: {e}")
        return render_template('error.html', error="分析功能首页加载失败"), 500


@analysis_bp.route('/config')
def config():
    """分析配置页面"""
    try:
        # 获取当前配置和可用模型
        from HomeSystem.graph.llm_factory import LLMFactory
        factory = LLMFactory()
        
        # 从Redis获取当前配置，如果不存在则使用默认值
        config_key = "analysis_config:global"
        current_config = {
            "analysis_model": "deepseek.DeepSeek_V3",
            "vision_model": "ollama.Qwen2_5_VL_7B",
            "timeout": 600
        }
        
        if redis_client:
            try:
                saved_config = redis_client.get(config_key)
                if saved_config:
                    import json
                    current_config.update(json.loads(saved_config))
            except Exception as e:
                logger.warning(f"读取Redis配置失败: {e}")
        
        # 获取可用模型列表
        available_models = factory.get_available_llm_models()
        vision_models = factory.get_available_vision_models()
        
        return render_template('analysis/config.html',
                             current_config=current_config,
                             available_models=available_models,
                             vision_models=vision_models)
    
    except Exception as e:
        logger.error(f"分析配置页面加载失败: {e}")
        return render_template('error.html', error="分析配置页面加载失败"), 500


@analysis_bp.route('/paper/<arxiv_id>/imgs/<filename>')
def serve_analysis_image(arxiv_id, filename):
    """服务分析图片文件"""
    try:
        # 安全检查：防止路径遍历攻击
        if '..' in filename or '/' in filename or '\\' in filename:
            logger.warning(f"Suspicious filename requested: {filename}")
            return "Invalid filename", 400
        
        # 验证ArXiv ID格式
        if not re.match(r'^\d{4}\.\d{4,5}$', arxiv_id):
            logger.warning(f"Invalid ArXiv ID format: {arxiv_id}")
            return "Invalid ArXiv ID", 400
        
        # 构建安全的文件路径
        base_path = os.path.join(PROJECT_ROOT, "data/paper_analyze")
        image_path = os.path.join(base_path, arxiv_id, "imgs", filename)
        
        # 确保路径在允许的目录内
        real_image_path = os.path.realpath(image_path)
        real_base_path = os.path.realpath(os.path.join(base_path, arxiv_id))
        
        if not real_image_path.startswith(real_base_path):
            logger.warning(f"Path traversal attempt: {image_path}")
            return "Access denied", 403
        
        # 检查文件是否存在
        if not os.path.exists(real_image_path):
            logger.info(f"Image not found: {real_image_path}")
            return "Image not found", 404
        
        # 检查是否是图片文件
        allowed_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
        file_ext = os.path.splitext(filename.lower())[1]
        if file_ext not in allowed_extensions:
            logger.warning(f"Invalid file type requested: {filename}")
            return "Invalid file type", 400
        
        # 发送文件
        return send_file(real_image_path)
        
    except Exception as e:
        logger.error(f"Serve image failed {arxiv_id}/{filename}: {e}")
        return "Server error", 500


@analysis_bp.route('/paper/<arxiv_id>/download')
def download_analysis(arxiv_id):
    """下载分析结果（Markdown + 图片打包为ZIP）"""
    try:
        # 获取分析结果
        result = analysis_service.get_analysis_result(arxiv_id)
        
        if not result['success']:
            return jsonify({
                'success': False,
                'error': '分析结果不存在'
            }), 404
        
        # 创建临时ZIP文件
        temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
        
        try:
            with zipfile.ZipFile(temp_zip.name, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                # 添加Markdown文件
                markdown_content = result['content']
                
                # 处理图片路径，转换为相对路径
                processed_markdown = _process_markdown_for_download(markdown_content, arxiv_id)
                
                zip_file.writestr(f"{arxiv_id}_analysis.md", processed_markdown)
                
                # 添加图片文件
                images_dir = os.path.join(PROJECT_ROOT, "data/paper_analyze", arxiv_id, "imgs")
                if os.path.exists(images_dir):
                    for filename in os.listdir(images_dir):
                        if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                            image_path = os.path.join(images_dir, filename)
                            if os.path.isfile(image_path):
                                zip_file.write(image_path, f"imgs/{filename}")
            
            # 返回ZIP文件
            return send_file(
                temp_zip.name,
                as_attachment=True,
                download_name=f"{arxiv_id}_deep_analysis.zip",
                mimetype='application/zip'
            )
            
        finally:
            # 清理临时文件
            pass
            
    except Exception as e:
        logger.error(f"下载分析结果失败 {arxiv_id}: {e}")
        return jsonify({
            'success': False,
            'error': f"下载失败: {str(e)}"
        }), 500


def _process_markdown_for_download(content: str, arxiv_id: str) -> str:
    """
    处理Markdown内容，将网页URL路径转换为本地相对路径
    """
    try:
        # 将网页URL路径转换为相对路径
        pattern = rf'/analysis/paper/{re.escape(arxiv_id)}/imgs/([^)]+)'
        replacement = r'imgs/\1'
        
        processed_content = re.sub(pattern, replacement, content)
        
        return processed_content
        
    except Exception as e:
        logger.error(f"处理Markdown下载内容失败: {e}")
        return content