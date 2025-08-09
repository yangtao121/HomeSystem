"""
论文收集路由 - 来自PaperGather的功能
包括任务配置、执行、监控等功能
"""
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from services.task_service import paper_gather_service, TaskMode
from services.paper_gather_service import paper_data_service
from config import DEFAULT_TASK_CONFIG
import logging

logger = logging.getLogger(__name__)

collect_bp = Blueprint('collect', __name__, url_prefix='/collect')


@collect_bp.route('/')
def index():
    """收集功能首页 - 重定向到任务配置"""
    return redirect(url_for('collect.config'))


@collect_bp.route('/config')
def config():
    """配置页面 - 论文收集任务配置"""
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
            available_search_modes = [
                {'value': 'latest', 'label': '最新论文', 'description': '按提交日期降序排列'},
                {'value': 'most_relevant', 'label': '最相关', 'description': '按相关性排序'}
            ]
            config_status['config_errors'].append(f"搜索模式加载失败: {str(modes_error)}")
        
        return render_template('collect/config.html',
                             available_models=available_models,
                             available_search_modes=available_search_modes,
                             default_config=DEFAULT_TASK_CONFIG,
                             config_status=config_status)
    
    except Exception as e:
        logger.error(f"配置页面加载失败: {e}")
        return render_template('error.html', error="配置页面加载失败"), 500


@collect_bp.route('/execute', methods=['POST'])
def execute_task():
    """执行任务 - 支持即时和定时两种模式"""
    try:
        data = request.get_json()
        
        # 获取执行模式
        mode = data.get('mode', TaskMode.IMMEDIATE.value)
        config_data = data.get('config', {})
        
        # 记录接收到的模型配置参数（用于调试）
        received_model_params = {k: v for k, v in config_data.items() 
                               if k in ['llm_model_name', 'deep_analysis_model', 'vision_model', 
                                       'analysis_timeout', 'enable_deep_analysis']}
        logger.info(f"📥 收到任务配置的模型参数: {received_model_params}")
        
        # 验证任务名称
        task_name = config_data.get('task_name', '').strip()
        if not task_name:
            return jsonify({
                'success': False,
                'error': '任务名称不能为空，请输入有意义的任务名称'
            }), 400
        
        if len(task_name) < 1 or len(task_name) > 100:
            return jsonify({
                'success': False,
                'error': '任务名称长度必须在1-100个字符之间'
            }), 400
        
        # 验证其他配置
        is_valid, error_msg = paper_gather_service.validate_config(config_data)
        if not is_valid:
            return jsonify({
                'success': False,
                'error': error_msg
            }), 400
        
        if mode == TaskMode.IMMEDIATE.value:
            # 即时执行模式
            task_id = paper_gather_service.start_immediate_task(config_data)
            
            return jsonify({
                'success': True,
                'task_id': task_id,
                'mode': 'immediate',
                'message': '任务已启动，正在后台执行...'
            })
        
        elif mode == TaskMode.SCHEDULED.value:
            # 定时执行模式
            interval_seconds = config_data.get('interval_seconds', 3600)
            task_id = paper_gather_service.start_scheduled_task(config_data, interval_seconds)
            
            return jsonify({
                'success': True,
                'task_id': task_id,
                'mode': 'scheduled',
                'interval_seconds': interval_seconds,
                'message': f'定时任务已创建，每 {interval_seconds} 秒执行一次'
            })
        
        else:
            return jsonify({
                'success': False,
                'error': f'不支持的执行模式: {mode}'
            }), 400
    
    except Exception as e:
        logger.error(f"任务执行失败: {e}")
        return jsonify({
            'success': False,
            'error': f'任务执行失败: {str(e)}'
        }), 500


@collect_bp.route('/status/<task_id>')
def task_status(task_id):
    """任务状态页面"""
    try:
        # 获取任务结果
        task_result = paper_gather_service.get_task_result(task_id)
        if not task_result:
            return render_template('error.html', error="任务不存在"), 404
        
        # 获取任务详细信息
        task_details = paper_gather_service.get_task_details(task_id)
        
        return render_template('collect/task_status.html', 
                             task_result=task_result,
                             task_details=task_details,
                             task_id=task_id)
    
    except Exception as e:
        logger.error(f"任务状态页面加载失败: {e}")
        return render_template('error.html', error="任务状态页面加载失败"), 500




@collect_bp.route('/results/<task_id>')
def task_results(task_id):
    """任务结果页面"""
    try:
        # 获取任务结果
        task_result = paper_gather_service.get_task_result(task_id)
        if not task_result:
            return render_template('error.html', error="任务结果不存在"), 404
        
        # 获取任务收集的论文
        papers = paper_data_service.get_papers_by_task(task_id)
        
        return render_template('collect/results.html', 
                             task_result=task_result,
                             papers=papers,
                             task_id=task_id)
    
    except Exception as e:
        logger.error(f"任务结果页面加载失败: {e}")
        return render_template('error.html', error="任务结果页面加载失败"), 500


@collect_bp.route('/tasks')
def tasks():
    """统一任务查看页面"""
    try:
        # 获取统一的任务列表数据
        tasks_data = paper_gather_service.get_all_tasks_unified()
        
        # 计算各类型任务数量
        scheduled_count = sum(1 for task in tasks_data if task.get('task_type') == 'scheduled')
        immediate_count = sum(1 for task in tasks_data if task.get('task_type') == 'immediate')
        running_count = sum(1 for task in tasks_data if task.get('status') == 'running')
        total_count = len(tasks_data)
        
        return render_template('collect/tasks.html', 
                             tasks=tasks_data,
                             scheduled_count=scheduled_count,
                             immediate_count=immediate_count,
                             running_count=running_count,
                             total_count=total_count)
    
    except Exception as e:
        logger.error(f"统一任务查看页面加载失败: {e}")
        return render_template('error.html', error="任务查看页面加载失败，请检查系统状态"), 500


@collect_bp.route('/history')
def task_history():
    """执行历史页面 - 重定向到统一任务查看"""
    return redirect(url_for('collect.tasks'))


@collect_bp.route('/scheduled')
def scheduled_tasks():
    """定时任务管理页面 - 重定向到统一任务查看"""
    return redirect(url_for('collect.tasks'))