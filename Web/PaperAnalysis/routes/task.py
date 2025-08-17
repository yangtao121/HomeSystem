"""
任务执行路由 - 处理任务执行、监控和管理功能
从PaperGather移植的任务管理功能，适配PaperAnalysis结构
"""
from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from services.task_service import paper_gather_service, TaskMode
from services.paper_gather_service import paper_data_service
import logging
import json

logger = logging.getLogger(__name__)

# 导入Redis配置
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
    logger.info("Task模块Redis连接成功")
except Exception as e:
    logger.warning(f"Task模块Redis连接失败: {e}")
    redis_client = None

task_bp = Blueprint('task', __name__)


@task_bp.route('/execute', methods=['POST'])
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
        
        # 加载系统设置（包括远程OCR配置）
        if redis_client:
            try:
                system_settings_key = "system_settings:global"
                system_settings_data = redis_client.get(system_settings_key)
                if system_settings_data:
                    system_settings = json.loads(system_settings_data)
                    
                    # 将远程OCR设置添加到任务配置中
                    if 'enable_remote_ocr' in system_settings:
                        config_data['enable_remote_ocr'] = system_settings['enable_remote_ocr']
                    if 'remote_ocr_endpoint' in system_settings:
                        config_data['remote_ocr_endpoint'] = system_settings['remote_ocr_endpoint']
                    if 'remote_ocr_timeout' in system_settings:
                        config_data['remote_ocr_timeout'] = system_settings['remote_ocr_timeout']
                    if 'remote_ocr_max_pages' in system_settings:
                        config_data['remote_ocr_max_pages'] = system_settings['remote_ocr_max_pages']
                    
                    logger.info(f"📥 已加载远程OCR配置: enable={config_data.get('enable_remote_ocr', False)}, endpoint={config_data.get('remote_ocr_endpoint', 'N/A')}, max_pages={config_data.get('remote_ocr_max_pages', 25)}")
                else:
                    logger.debug("未找到系统设置，使用默认配置")
            except Exception as e:
                logger.warning(f"加载系统设置失败: {e}")
        
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
            success, task_id, error_msg = paper_gather_service.start_scheduled_task(config_data)
            
            if success:
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
                    'error': error_msg
                }), 500
        
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


@task_bp.route('/status/<task_id>')
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


@task_bp.route('/results/<task_id>')
def task_results(task_id):
    """任务结果页面"""
    try:
        # 获取任务结果
        task_result = paper_gather_service.get_task_result(task_id)
        if not task_result:
            return render_template('error.html', error="任务结果不存在"), 404
        
        # 如果任务还在运行，重定向到状态页面
        if task_result['status'] != 'completed':
            return redirect(url_for('task.task_status', task_id=task_id))
        
        # 获取任务收集的论文
        papers = paper_data_service.get_papers_by_task(task_id)
        
        return render_template('collect/results.html', 
                             task_result=task_result,
                             papers=papers,
                             task_id=task_id)
    
    except Exception as e:
        logger.error(f"任务结果页面加载失败: {e}")
        return render_template('error.html', error="任务结果页面加载失败"), 500


@task_bp.route('/result/<task_id>')
def task_result(task_id):
    """任务结果页面 - 别名路由，与 /results/<task_id> 功能相同"""
    return task_results(task_id)


@task_bp.route('/cancel/<task_id>', methods=['POST'])
def cancel_task(task_id):
    """取消任务"""
    try:
        success, error_msg = paper_gather_service.cancel_task(task_id)
        
        return jsonify({
            'success': success,
            'error': error_msg,
            'message': '任务已取消' if success else None
        })
    
    except Exception as e:
        logger.error(f"取消任务失败: {e}")
        return jsonify({
            'success': False,
            'error': f'取消任务失败: {str(e)}'
        }), 500


@task_bp.route('/stop_scheduled/<task_id>', methods=['POST'])
def stop_scheduled_task(task_id):
    """停止定时任务"""
    try:
        success, error_msg = paper_gather_service.stop_scheduled_task(task_id)
        
        return jsonify({
            'success': success,
            'error': error_msg,
            'message': '定时任务已停止' if success else None
        })
    
    except Exception as e:
        logger.error(f"停止定时任务失败: {e}")
        return jsonify({
            'success': False,
            'error': f'停止定时任务失败: {str(e)}'
        }), 500


@task_bp.route('/history')
def task_history():
    """任务执行历史 - 重定向到统一任务管理页面"""
    return redirect(url_for('collect.tasks'))


@task_bp.route('/scheduled')
def scheduled_tasks():
    """定时任务管理 - 重定向到统一任务管理页面"""
    return redirect(url_for('collect.tasks'))


@task_bp.route('/trigger_scheduled/<task_id>', methods=['POST'])
def trigger_scheduled_task(task_id):
    """手动触发定时任务"""
    try:
        success, error_msg = paper_gather_service.trigger_scheduled_task_manual(task_id)
        
        return jsonify({
            'success': success,
            'error': error_msg,
            'message': '任务已手动触发，将在几秒内开始执行' if success else None
        })
    
    except Exception as e:
        logger.error(f"手动触发定时任务失败: {e}")
        return jsonify({
            'success': False,
            'error': f'手动触发定时任务失败: {str(e)}'
        }), 500