"""
任务执行路由 - 处理两种执行模式
"""
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from services.task_service import paper_gather_service, TaskMode
from services.paper_service import paper_data_service
import logging

logger = logging.getLogger(__name__)

task_bp = Blueprint('task', __name__)


@task_bp.route('/execute', methods=['POST'])
def execute_task():
    """执行任务 - 支持两种模式"""
    try:
        data = request.get_json()
        
        # 获取执行模式
        mode = data.get('mode', TaskMode.IMMEDIATE.value)
        config_data = data.get('config', {})
        
        # 验证配置
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
                'message': '任务已开始执行，请查看任务状态页面获取进度'
            })
        
        elif mode == TaskMode.SCHEDULED.value:
            # 后台定时执行模式
            success, task_id, error_msg = paper_gather_service.start_scheduled_task(config_data)
            
            if success:
                return jsonify({
                    'success': True,
                    'task_id': task_id,
                    'mode': 'scheduled',
                    'message': f'定时任务已启动，间隔: {config_data.get("interval_seconds", 3600)}秒'
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
        logger.error(f"执行任务失败: {e}")
        return jsonify({
            'success': False,
            'error': f'执行任务失败: {str(e)}'
        }), 500


@task_bp.route('/status/<task_id>')
def task_status(task_id):
    """任务状态页面"""
    try:
        task_result = paper_gather_service.get_task_result(task_id)
        
        if not task_result:
            return render_template('error.html', error="任务不存在"), 404
        
        return render_template('task_status.html', 
                             task_result=task_result,
                             task_id=task_id)
    
    except Exception as e:
        logger.error(f"获取任务状态失败: {e}")
        return render_template('error.html', error="获取任务状态失败"), 500


@task_bp.route('/results/<task_id>')
def task_results(task_id):
    """任务结果页面"""
    try:
        task_result = paper_gather_service.get_task_result(task_id)
        
        if not task_result:
            return render_template('error.html', error="任务不存在"), 404
        
        if task_result['status'] != 'completed':
            return redirect(url_for('task.task_status', task_id=task_id))
        
        # 解析结果数据，获取论文列表
        result_data = task_result.get('result_data', {})
        papers = []
        
        # 从结果数据中提取论文信息
        if 'papers' in result_data:
            for paper_data in result_data['papers']:
                # 这里可能需要根据实际的结果数据结构调整
                papers.append(paper_data)
        
        return render_template('results.html', 
                             task_result=task_result,
                             papers=papers,
                             task_id=task_id)
    
    except Exception as e:
        logger.error(f"获取任务结果失败: {e}")
        return render_template('error.html', error="获取任务结果失败"), 500


@task_bp.route('/cancel/<task_id>', methods=['POST'])
def cancel_task(task_id):
    """取消任务"""
    try:
        success, error_msg = paper_gather_service.cancel_task(task_id)
        
        return jsonify({
            'success': success,
            'error': error_msg
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
            'error': error_msg
        })
    
    except Exception as e:
        logger.error(f"停止定时任务失败: {e}")
        return jsonify({
            'success': False,
            'error': f'停止定时任务失败: {str(e)}'
        }), 500


@task_bp.route('/history')
def task_history():
    """任务执行历史"""
    try:
        # 获取分页参数
        page = int(request.args.get('page', 1))
        per_page = 20
        
        # 获取所有任务结果
        all_results = paper_gather_service.get_all_task_results()
        
        # 按时间排序
        sorted_results = sorted(all_results, key=lambda x: x['start_time'], reverse=True)
        
        # 分页
        total = len(sorted_results)
        start = (page - 1) * per_page
        end = start + per_page
        results = sorted_results[start:end]
        
        # 计算分页信息
        total_pages = (total + per_page - 1) // per_page
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
        
        return render_template('task_history.html', 
                             results=results,
                             pagination=pagination)
    
    except Exception as e:
        logger.error(f"获取任务历史失败: {e}")
        return render_template('error.html', error="获取任务历史失败"), 500


@task_bp.route('/scheduled')
def scheduled_tasks():
    """定时任务管理"""
    try:
        tasks = paper_gather_service.get_scheduled_tasks()
        
        return render_template('scheduled_tasks.html', tasks=tasks)
    
    except Exception as e:
        logger.error(f"获取定时任务失败: {e}")
        return render_template('error.html', error="获取定时任务失败"), 500