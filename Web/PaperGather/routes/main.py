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
    """配置页面 - 增强错误处理和配置状态显示"""
    config_status = {
        'models_loaded': False,
        'search_modes_loaded': False,
        'config_errors': []
    }
    
    try:
        # 获取可用的LLM模型
        try:
            available_models = paper_gather_service.get_available_models()
            config_status['models_loaded'] = True
            logger.info(f"✅ 成功获取 {len(available_models)} 个LLM模型")
        except Exception as models_error:
            logger.error(f"❌ 获取LLM模型失败: {models_error}")
            available_models = ["deepseek.DeepSeek_V3", "ollama.Qwen3_30B"]  # 备用模型
            config_status['config_errors'].append(f"LLM模型加载失败: {str(models_error)}")
        
        # 获取可用的搜索模式
        try:
            available_search_modes = paper_gather_service.get_available_search_modes()
            config_status['search_modes_loaded'] = True
            logger.info(f"✅ 成功获取 {len(available_search_modes)} 个搜索模式")
        except Exception as modes_error:
            logger.error(f"❌ 获取搜索模式失败: {modes_error}")
            # 提供备用搜索模式
            available_search_modes = [
                {'value': 'latest', 'label': '最新论文', 'description': '按提交日期降序排列'},
                {'value': 'most_relevant', 'label': '最相关', 'description': '按相关性排序'}
            ]
            config_status['config_errors'].append(f"搜索模式加载失败: {str(modes_error)}")
        
        # 构建用户友好的错误信息
        friendly_errors = []
        for error in config_status['config_errors']:
            if "LLM模型加载失败" in error:
                friendly_errors.append({
                    'type': 'warning',
                    'title': 'LLM模型配置问题',
                    'message': '部分LLM模型可能无法使用，请检查网络连接和API密钥配置',
                    'details': error,
                    'suggestions': [
                        '检查Ollama服务是否正常运行 (ollama serve)',
                        '确认API密钥已正确配置在环境变量中',
                        '检查网络连接是否正常'
                    ]
                })
            elif "搜索模式加载失败" in error:
                friendly_errors.append({
                    'type': 'error',
                    'title': '搜索模式配置错误',
                    'message': '搜索模式配置异常，已使用默认模式',
                    'details': error,
                    'suggestions': ['重启应用', '检查代码配置']
                })
        
        return render_template('config.html', 
                             default_config=DEFAULT_TASK_CONFIG,
                             available_models=available_models,
                             available_search_modes=available_search_modes,
                             config_status=config_status,
                             config_errors=friendly_errors)
    
    except Exception as e:
        logger.error(f"❌ 配置页面加载失败: {e}")
        error_info = {
            'type': 'critical',
            'title': '配置页面加载失败',
            'message': '系统配置出现严重问题，请联系管理员',
            'details': str(e),
            'suggestions': [
                '检查数据库连接是否正常',
                '确认HomeSystem模块是否正确安装',
                '重启应用服务'
            ]
        }
        return render_template('error.html', error=error_info), 500


@main_bp.route('/config/validate', methods=['POST'])
def validate_config():
    """验证配置参数 - 增强版本，提供详细的验证反馈"""
    try:
        config_data = request.get_json()
        
        if not config_data:
            return jsonify({
                'success': False,
                'error': '请提供配置数据',
                'error_type': 'missing_data'
            }), 400
        
        is_valid, error_msg = paper_gather_service.validate_config(config_data)
        
        response_data = {
            'success': is_valid,
            'error': error_msg
        }
        
        # 如果验证成功，提供额外的配置信息
        if is_valid:
            response_data.update({
                'message': '配置验证通过',
                'config_summary': {
                    'search_query': config_data.get('search_query', '')[:50] + ('...' if len(config_data.get('search_query', '')) > 50 else ''),
                    'llm_model_name': config_data.get('llm_model_name'),
                    'relevance_threshold': config_data.get('relevance_threshold'),
                    'search_mode': config_data.get('search_mode')
                }
            })
        else:
            # 提供错误类型和建议
            error_type = 'validation_error'
            suggestions = []
            
            if '缺少必需参数' in error_msg:
                error_type = 'missing_required_field'
                suggestions = ['请填写所有必需的配置项']
            elif '范围内' in error_msg:
                error_type = 'value_out_of_range'
                suggestions = ['请检查数值范围是否正确']
            elif '模型不可用' in error_msg:
                error_type = 'model_unavailable' 
                suggestions = ['请选择其他可用的模型', '检查网络连接和API配置']
            elif '搜索模式' in error_msg:
                error_type = 'invalid_search_mode'
                suggestions = ['请选择有效的搜索模式']
            elif '年份' in error_msg:
                error_type = 'invalid_date_range'
                suggestions = ['请检查年份设置是否合理']
            
            response_data.update({
                'error_type': error_type,
                'suggestions': suggestions
            })
        
        return jsonify(response_data)
    
    except Exception as e:
        logger.error(f"❌ 配置验证异常: {e}")
        return jsonify({
            'success': False,
            'error': f"配置验证时发生异常，请稍后重试",
            'error_type': 'system_error',
            'details': str(e),
            'suggestions': ['请稍后重试', '如问题持续请联系管理员']
        }), 500


@main_bp.route('/help')
def help_page():
    """帮助页面"""
    return render_template('help.html')


@main_bp.route('/about')
def about():
    """关于页面"""
    return render_template('about.html')