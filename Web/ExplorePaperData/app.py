"""
ArXiv论文数据可视化Web应用
提供直观的论文数据探索界面
"""
from flask import Flask, render_template, request, jsonify, redirect, url_for, send_file
from flask_moment import Moment
from database import PaperService, DifyService
from config import Config
from utils.markdown_utils import markdown_filter, markdown_safe_filter
from services.analysis_service import DeepAnalysisService
import logging
import math
import os
import zipfile
import tempfile
import re
import sys
import json
import redis

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config.from_object(Config)

# 初始化Flask-Moment
moment = Moment(app)

# 初始化服务
paper_service = PaperService()
dify_service = DifyService()

# 添加HomeSystem模块路径以导入LLMFactory
PROJECT_ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.append(PROJECT_ROOT)

# 初始化Redis连接用于配置存储
try:
    redis_client = redis.Redis(
        host=app.config.get('REDIS_HOST', 'localhost'),
        port=app.config.get('REDIS_PORT', 16379),
        db=app.config.get('REDIS_DB', 0),
        decode_responses=True
    )
    redis_client.ping()  # 测试连接
    logger.info("Redis连接成功")
except Exception as e:
    logger.warning(f"Redis连接失败，将使用内存存储: {e}")
    redis_client = None

# 初始化分析服务（需要在Redis初始化之后）
analysis_service = DeepAnalysisService(paper_service, redis_client)

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

@app.route('/api/tasks/available_for_migration')
def api_available_tasks_for_migration():
    """API接口 - 获取可用于迁移的任务列表"""
    try:
        tasks_data = paper_service.get_available_tasks_for_migration()
        return jsonify({'success': True, 'data': tasks_data})
    
    except Exception as e:
        logger.error(f"获取迁移任务列表失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/migrate_paper_to_task', methods=['POST'])
def api_migrate_paper_to_task():
    """API接口 - 将论文迁移到指定任务"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': '无效的请求数据'}), 400
        
        arxiv_id = (data.get('arxiv_id') or '').strip()
        target_task_name = (data.get('target_task_name') or '').strip()
        target_task_id = (data.get('target_task_id') or '').strip() or None
        
        if not arxiv_id or not target_task_name:
            return jsonify({'success': False, 'error': '缺少必要参数'}), 400
        
        success = paper_service.migrate_paper_to_task(
            arxiv_id=arxiv_id,
            target_task_name=target_task_name,
            target_task_id=target_task_id
        )
        
        if success:
            return jsonify({
                'success': True, 
                'message': f'论文已成功迁移到任务: {target_task_name}',
                'data': {
                    'arxiv_id': arxiv_id,
                    'target_task_name': target_task_name,
                    'target_task_id': target_task_id
                }
            })
        else:
            return jsonify({'success': False, 'error': '迁移失败，论文不存在'}), 404
    
    except Exception as e:
        logger.error(f"论文迁移失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/batch_migrate_to_task', methods=['POST'])
def api_batch_migrate_to_task():
    """API接口 - 批量将论文迁移到指定任务"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': '无效的请求数据'}), 400
        
        arxiv_ids = data.get('arxiv_ids', [])
        target_task_name = (data.get('target_task_name') or '').strip()
        target_task_id = (data.get('target_task_id') or '').strip() or None
        
        if not arxiv_ids or not target_task_name:
            return jsonify({'success': False, 'error': '缺少必要参数'}), 400
        
        if not isinstance(arxiv_ids, list):
            return jsonify({'success': False, 'error': 'arxiv_ids必须是数组'}), 400
        
        affected_rows, missing_papers = paper_service.batch_migrate_papers_to_task(
            arxiv_ids=arxiv_ids,
            target_task_name=target_task_name,
            target_task_id=target_task_id
        )
        
        result = {
            'success': True,
            'message': f'成功迁移 {affected_rows} 篇论文到任务: {target_task_name}',
            'affected_rows': affected_rows,
            'total_requested': len(arxiv_ids),
            'missing_papers': missing_papers
        }
        
        if missing_papers:
            result['warning'] = f'有 {len(missing_papers)} 篇论文不存在'
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"批量迁移失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/merge_tasks', methods=['POST'])
def api_merge_tasks():
    """API接口 - 合并任务"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': '无效的请求数据'}), 400
        
        source_task_name = (data.get('source_task_name') or '').strip()
        target_task_name = (data.get('target_task_name') or '').strip()
        target_task_id = (data.get('target_task_id') or '').strip() or None
        
        if not source_task_name or not target_task_name:
            return jsonify({'success': False, 'error': '缺少必要参数'}), 400
        
        if source_task_name == target_task_name:
            return jsonify({'success': False, 'error': '源任务和目标任务不能相同'}), 400
        
        affected_rows = paper_service.merge_tasks(
            source_task_name=source_task_name,
            target_task_name=target_task_name,
            target_task_id=target_task_id
        )
        
        return jsonify({
            'success': True,
            'message': f'成功合并任务: {source_task_name} -> {target_task_name}，影响 {affected_rows} 篇论文',
            'affected_rows': affected_rows,
            'source_task_name': source_task_name,
            'target_task_name': target_task_name
        })
    
    except Exception as e:
        logger.error(f"任务合并失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/dify_upload/<arxiv_id>', methods=['POST'])
def api_dify_upload_paper(arxiv_id):
    """API接口 - 上传单个论文到 Dify 知识库"""
    try:
        # 检查 Dify 服务可用性
        if not dify_service.is_available():
            return jsonify({
                'success': False, 
                'error': 'Dify 服务不可用，请检查配置和连接'
            }), 503
        
        result = dify_service.upload_paper_to_dify(arxiv_id)
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': '论文上传成功',
                'data': {
                    'arxiv_id': arxiv_id,
                    'dataset_id': result.get('dataset_id'),
                    'document_id': result.get('document_id'),
                    'document_name': result.get('document_name')
                }
            })
        else:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 400
    
    except Exception as e:
        logger.error(f"上传论文到 Dify 失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/dify_batch_upload', methods=['POST'])
def api_dify_batch_upload():
    """API接口 - 批量上传论文到 Dify 知识库"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': '无效的请求数据'}), 400
        
        arxiv_ids = data.get('arxiv_ids', [])
        if not arxiv_ids or not isinstance(arxiv_ids, list):
            return jsonify({'success': False, 'error': '缺少有效的论文ID列表'}), 400
        
        # 检查 Dify 服务可用性
        if not dify_service.is_available():
            return jsonify({
                'success': False, 
                'error': 'Dify 服务不可用，请检查配置和连接'
            }), 503
        
        results = dify_service.batch_upload_papers_to_dify(arxiv_ids)
        
        return jsonify({
            'success': True,
            'message': f'批量上传完成: 成功 {results["success_count"]} 篇，失败 {results["failed_count"]} 篇',
            'data': results
        })
    
    except Exception as e:
        logger.error(f"批量上传论文到 Dify 失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/dify_remove/<arxiv_id>', methods=['DELETE'])
def api_dify_remove_paper(arxiv_id):
    """API接口 - 从 Dify 知识库移除论文"""
    try:
        # 检查 Dify 服务可用性
        if not dify_service.is_available():
            return jsonify({
                'success': False, 
                'error': 'Dify 服务不可用，请检查配置和连接'
            }), 503
        
        result = dify_service.remove_paper_from_dify(arxiv_id)
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': '论文从知识库移除成功'
            })
        else:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 400
    
    except Exception as e:
        logger.error(f"从 Dify 移除论文失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/dify_status/<arxiv_id>')
def api_dify_status(arxiv_id):
    """API接口 - 查询论文的 Dify 上传状态"""
    try:
        result = dify_service.get_dify_upload_status(arxiv_id)
        
        if result['success']:
            return jsonify({
                'success': True,
                'data': result
            })
        else:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 404
    
    except Exception as e:
        logger.error(f"查询 Dify 状态失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/dify_verify/<arxiv_id>', methods=['POST'])
def api_dify_verify(arxiv_id):
    """API接口 - 验证论文是否存在于 Dify 服务器"""
    try:
        result = dify_service.verify_dify_document(arxiv_id)
        
        if result['success']:
            return jsonify({
                'success': True,
                'data': result
            })
        else:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 400
    
    except Exception as e:
        logger.error(f"验证 Dify 文档失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/dify_clean/<arxiv_id>', methods=['POST'])
def api_dify_clean(arxiv_id):
    """API接口 - 清理丢失的 Dify 文档记录"""
    try:
        result = dify_service.clean_missing_dify_record(arxiv_id)
        
        if result['success']:
            return jsonify({
                'success': True,
                'data': result
            })
        else:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 400
    
    except Exception as e:
        logger.error(f"清理 Dify 记录失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/dify_statistics')
def api_dify_statistics():
    """API接口 - 获取 Dify 相关统计信息"""
    try:
        stats = dify_service.get_dify_statistics()
        return jsonify({'success': True, 'data': stats})
    
    except Exception as e:
        logger.error(f"获取 Dify 统计信息失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/dify_validate_upload/<arxiv_id>')
def api_dify_validate_upload(arxiv_id):
    """API接口 - 验证论文上传前置条件"""
    try:
        validation_result = dify_service.validate_upload_preconditions(arxiv_id)
        return jsonify({'success': True, 'data': validation_result})
    
    except Exception as e:
        logger.error(f"验证论文上传条件失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/dify_batch_validate', methods=['POST'])
def api_dify_batch_validate():
    """API接口 - 批量验证论文上传前置条件"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': '无效的请求数据'}), 400
        
        arxiv_ids = data.get('arxiv_ids', [])
        if not arxiv_ids:
            return jsonify({'success': False, 'error': '没有提供论文ID'}), 400
        
        if not isinstance(arxiv_ids, list):
            return jsonify({'success': False, 'error': 'arxiv_ids必须是数组'}), 400
        
        results = {
            "total_papers": len(arxiv_ids),
            "valid_papers": 0,
            "invalid_papers": 0,
            "papers_with_warnings": 0,
            "results": [],
            "error_summary": {
                "missing_task_name": 0,
                "already_uploaded": 0,
                "missing_data": 0,
                "service_unavailable": 0,
                "other": 0
            },
            "warnings_summary": {
                "short_abstract": 0,
                "missing_authors": 0,
                "pdf_issues": 0,
                "other": 0
            }
        }
        
        for arxiv_id in arxiv_ids:
            try:
                validation = dify_service.validate_upload_preconditions(arxiv_id)
                
                result_item = {
                    "arxiv_id": arxiv_id,
                    "valid": validation["success"],
                    "errors": validation["errors"],
                    "warnings": validation["warnings"]
                }
                
                results["results"].append(result_item)
                
                if validation["success"]:
                    results["valid_papers"] += 1
                else:
                    results["invalid_papers"] += 1
                    
                    # 分类错误
                    for error in validation["errors"]:
                        if "任务名称" in error:
                            results["error_summary"]["missing_task_name"] += 1
                        elif "已上传" in error:
                            results["error_summary"]["already_uploaded"] += 1
                        elif "不存在" in error or "缺失" in error:
                            results["error_summary"]["missing_data"] += 1
                        elif "连接" in error or "服务" in error:
                            results["error_summary"]["service_unavailable"] += 1
                        else:
                            results["error_summary"]["other"] += 1
                
                if validation["warnings"]:
                    results["papers_with_warnings"] += 1
                    
                    # 分类警告
                    for warning in validation["warnings"]:
                        if "摘要" in warning:
                            results["warnings_summary"]["short_abstract"] += 1
                        elif "作者" in warning:
                            results["warnings_summary"]["missing_authors"] += 1
                        elif "PDF" in warning or "链接" in warning:
                            results["warnings_summary"]["pdf_issues"] += 1
                        else:
                            results["warnings_summary"]["other"] += 1
                            
            except Exception as e:
                logger.error(f"验证论文 {arxiv_id} 失败: {e}")
                results["invalid_papers"] += 1
                results["results"].append({
                    "arxiv_id": arxiv_id,
                    "valid": False,
                    "errors": [f"验证过程发生错误: {str(e)}"],
                    "warnings": []
                })
                results["error_summary"]["other"] += 1
        
        return jsonify({'success': True, 'data': results})
    
    except Exception as e:
        logger.error(f"批量验证失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/dify_batch_verify', methods=['POST'])
def api_dify_batch_verify():
    """API接口 - 批量验证所有已上传文档的状态"""
    try:
        # 检查 Dify 服务是否可用
        if not dify_service.is_available():
            return jsonify({
                'success': False, 
                'error': 'Dify 服务不可用，请检查服务配置和连接状态'
            }), 503
        
        # 执行批量验证
        result = dify_service.batch_verify_all_documents()
        
        if result['success']:
            return jsonify({
                'success': True, 
                'data': result
            })
        else:
            return jsonify({
                'success': False, 
                'error': result.get('error', '批量验证失败'),
                'data': result
            }), 500
    
    except Exception as e:
        logger.error(f"批量验证文档失败: {e}")
        return jsonify({
            'success': False, 
            'error': str(e),
            'data': {
                'total': 0,
                'verified': 0,
                'failed': 0,
                'missing': 0,
                'progress': 0,
                'message': f'批量验证过程中发生错误: {e}',
                'failed_papers': [],
                'missing_papers': []
            }
        }), 500

@app.route('/api/dify_upload_all_eligible', methods=['POST'])
def api_dify_upload_all_eligible():
    """API接口 - 一键上传所有符合条件的论文到 Dify 知识库"""
    import time
    
    start_time = time.time()
    app.logger.info("开始一键上传操作")
    
    try:
        # 详细的服务可用性检查
        if not dify_service.is_available():
            error_details = {
                'error_type': 'service_unavailable',
                'details': 'Dify 服务连接失败',
                'suggestions': [
                    '检查 Dify 服务是否正在运行',
                    '验证网络连接到 Dify 服务器',
                    '确认 API 密钥和端点配置正确',
                    '查看应用日志获取更多信息'
                ]
            }
            app.logger.error(f"Dify 服务不可用: {error_details}")
            return jsonify({
                'success': False, 
                'error': 'Dify 服务不可用，请检查服务配置和连接状态',
                'error_details': error_details
            }), 503
        
        # 获取可选的过滤参数
        data = request.get_json() if request.get_json() else {}
        
        # 支持的过滤选项
        filters = {
            'task_name': data.get('task_name'),
            'category': data.get('category'),
            'exclude_already_uploaded': data.get('exclude_already_uploaded', True),
            'require_task_name': data.get('require_task_name', True),
            'max_papers': data.get('max_papers')  # 可选择限制数量
        }
        
        app.logger.info(f"一键上传过滤条件: {filters}")
        
        # 执行智能批量上传
        result = dify_service.upload_all_eligible_papers_with_summary(filters)
        
        processing_time = time.time() - start_time
        app.logger.info(f"一键上传完成，耗时: {processing_time:.2f}秒，结果: {result.get('success_count', 0)}/{result.get('total_eligible', 0)}")
        
        return jsonify({
            'success': True,
            'data': result,
            'processing_time': processing_time
        })
    
    except Exception as e:
        processing_time = time.time() - start_time
        app.logger.error(f"一键上传失败 (耗时{processing_time:.2f}秒): {e}")
        return jsonify({
            'success': False, 
            'error': str(e),
            'error_details': {
                'error_type': 'upload_error',
                'details': str(e),
                'processing_time': processing_time
            },
            'data': {
                'total_eligible': 0,
                'total_attempted': 0,
                'success_count': 0,
                'failed_count': 0,
                'skipped_count': 0,
                'progress': 0,
                'message': f'一键上传过程中发生错误: {e}',
                'successful_papers': [],
                'failed_papers': [],
                'skipped_papers': [],
                'failure_summary': {},
                'suggestions': []
            }
        }), 500

@app.route('/api/generate_failed_papers_download', methods=['POST'])
def api_generate_failed_papers_download():
    """API接口 - 为失败的论文生成下载链接或压缩包"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': '无效的请求数据'}), 400
        
        failed_papers = data.get('failed_papers', [])
        download_type = data.get('download_type', 'links')  # 'links', 'csv', 'zip'
        
        if not failed_papers:
            return jsonify({'success': False, 'error': '没有提供失败论文数据'}), 400
        
        # 生成下载内容
        result = dify_service.generate_failed_papers_download(failed_papers, download_type)
        
        return jsonify({
            'success': True,
            'data': result
        })
    
    except Exception as e:
        logger.error(f"生成失败论文下载失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/migration_preview', methods=['POST'])
def api_migration_preview():
    """API接口 - 获取迁移预览信息"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': '无效的请求数据'}), 400
        
        arxiv_ids = data.get('arxiv_ids', [])
        target_task_name = (data.get('target_task_name') or '').strip()
        
        if not arxiv_ids or not target_task_name:
            return jsonify({'success': False, 'error': '缺少必要参数'}), 400
        
        if not isinstance(arxiv_ids, list):
            return jsonify({'success': False, 'error': 'arxiv_ids必须是数组'}), 400
        
        preview_data = paper_service.get_task_migration_preview(
            arxiv_ids=arxiv_ids,
            target_task_name=target_task_name
        )
        
        return jsonify({'success': True, 'data': preview_data})
    
    except Exception as e:
        logger.error(f"获取迁移预览失败: {e}")
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


# === 深度论文分析API接口 ===

@app.route('/api/paper/<arxiv_id>/analyze', methods=['POST'])
def api_start_analysis(arxiv_id):
    """API接口 - 启动深度论文分析"""
    try:
        logger.info(f"🎯 收到深度分析请求 - ArXiv ID: {arxiv_id}")
        
        # 获取配置参数
        data = request.get_json() if request.is_json else {}
        config = data.get('config', {})
        logger.info(f"📋 分析配置: {config}")
        
        # 启动分析
        logger.info(f"🔄 调用分析服务...")
        result = analysis_service.start_analysis(arxiv_id, config)
        logger.info(f"📤 分析服务返回结果: {result}")
        
        if result['success']:
            logger.info(f"✅ 分析启动成功: {arxiv_id}")
            return jsonify(result)
        else:
            logger.error(f"❌ 分析启动失败: {arxiv_id}, 错误: {result.get('error')}")
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"启动深度分析失败 {arxiv_id}: {e}")
        return jsonify({
            'success': False,
            'error': f"启动分析失败: {str(e)}"
        }), 500

@app.route('/api/paper/<arxiv_id>/analysis_status')
def api_analysis_status(arxiv_id):
    """API接口 - 查询分析状态"""
    try:
        result = analysis_service.get_analysis_status(arxiv_id)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 404
            
    except Exception as e:
        logger.error(f"获取分析状态失败 {arxiv_id}: {e}")
        return jsonify({
            'success': False,
            'error': f"获取状态失败: {str(e)}"
        }), 500

@app.route('/api/paper/<arxiv_id>/analysis_result')
def api_analysis_result(arxiv_id):
    """API接口 - 获取分析结果"""
    try:
        result = analysis_service.get_analysis_result(arxiv_id)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 404
            
    except Exception as e:
        logger.error(f"获取分析结果失败 {arxiv_id}: {e}")
        return jsonify({
            'success': False,
            'error': f"获取结果失败: {str(e)}"
        }), 500

@app.route('/api/paper/<arxiv_id>/cancel_analysis', methods=['POST'])
def api_cancel_analysis(arxiv_id):
    """API接口 - 取消正在进行的分析"""
    try:
        result = analysis_service.cancel_analysis(arxiv_id)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"取消分析失败 {arxiv_id}: {e}")
        return jsonify({
            'success': False,
            'error': f"取消失败: {str(e)}"
        }), 500

@app.route('/api/analysis_config', methods=['GET'])
def get_analysis_config():
    """获取深度分析配置和可用模型"""
    try:
        # 导入LLMFactory
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
                    current_config.update(json.loads(saved_config))
            except Exception as e:
                logger.warning(f"读取Redis配置失败: {e}")
        
        # 获取可用模型列表和详细信息
        available_models = factory.get_available_llm_models()
        vision_models = factory.get_available_vision_models()
        
        # 构建模型详细信息字典
        model_details = {}
        for model_key in available_models:
            if model_key in factory.available_llm_models:
                model_info = factory.available_llm_models[model_key]
                model_details[model_key] = {
                    'display_name': model_info['display_name'],
                    'description': model_info.get('description', ''),
                    'provider': model_info['provider'],
                    'max_tokens': model_info.get('max_tokens'),
                    'context_length': model_info.get('context_length'),
                    'supports_functions': model_info.get('supports_functions', False),
                    'supports_vision': model_info.get('supports_vision', False),
                    'is_local': model_info['type'] == 'ollama'
                }
        
        return jsonify({
            'success': True,
            'data': {
                'current_config': current_config,
                'available_models': {
                    'analysis_models': available_models,
                    'vision_models': vision_models
                },
                'model_details': model_details,
                'recommended_models': {
                    'reasoning': ['deepseek.DeepSeek_R1', 'volcano.Doubao_1_6_Thinking'],
                    'coding': ['ollama.Qwen3_30B', 'moonshot.Kimi_K2'],
                    'general': ['deepseek.DeepSeek_V3', 'zhipuai.GLM_4_5'],
                    'vision': vision_models[:3] if vision_models else []
                }
            }
        })
        
    except Exception as e:
        logger.error(f"获取分析配置失败: {e}")
        return jsonify({
            'success': False,
            'error': f"获取配置失败: {str(e)}"
        }), 500

@app.route('/api/analysis_config', methods=['POST'])
def save_analysis_config():
    """保存深度分析配置"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': '请求数据不能为空'
            }), 400
        
        # 验证必要字段
        analysis_model = data.get('analysis_model')
        vision_model = data.get('vision_model')
        timeout = data.get('timeout', 600)
        
        if not analysis_model or not vision_model:
            return jsonify({
                'success': False,
                'error': '分析模型和视觉模型不能为空'
            }), 400
        
        # 验证超时时间
        try:
            timeout = int(timeout)
            if timeout < 300 or timeout > 1800:
                return jsonify({
                    'success': False,
                    'error': '超时时间必须在300-1800秒之间'
                }), 400
        except (ValueError, TypeError):
            return jsonify({
                'success': False,
                'error': '超时时间必须为有效的整数'
            }), 400
        
        # 验证模型是否可用
        from HomeSystem.graph.llm_factory import LLMFactory
        factory = LLMFactory()
        
        available_llm_models = factory.get_available_llm_models()
        available_vision_models = factory.get_available_vision_models()
        
        if analysis_model not in available_llm_models:
            return jsonify({
                'success': False,
                'error': f'分析模型 {analysis_model} 不可用'
            }), 400
        
        if vision_model not in available_vision_models:
            return jsonify({
                'success': False,
                'error': f'视觉模型 {vision_model} 不可用'
            }), 400
        
        # 构建配置
        config = {
            'analysis_model': analysis_model,
            'vision_model': vision_model,
            'timeout': timeout
        }
        
        # 保存到Redis
        config_key = "analysis_config:global"
        if redis_client:
            try:
                redis_client.set(config_key, json.dumps(config))
                logger.info(f"配置已保存到Redis: {config}")
            except Exception as e:
                logger.error(f"保存配置到Redis失败: {e}")
                return jsonify({
                    'success': False,
                    'error': f'保存配置失败: {str(e)}'
                }), 500
        else:
            # 如果Redis不可用，记录警告但不阻止操作
            logger.warning("Redis不可用，配置仅在当前会话有效")
        
        # 更新analysis_service的配置
        analysis_service.default_config.update({
            'analysis_model': analysis_model,
            'vision_model': vision_model,
            'timeout': timeout
        })
        
        return jsonify({
            'success': True,
            'message': '配置保存成功',
            'config': config
        })
        
    except Exception as e:
        logger.error(f"保存分析配置失败: {e}")
        return jsonify({
            'success': False,
            'error': f"保存配置失败: {str(e)}"
        }), 500

@app.route('/paper/<arxiv_id>/analysis')
def paper_analysis_view(arxiv_id):
    """论文深度分析显示页面"""
    try:
        # 获取分析结果
        result = analysis_service.get_analysis_result(arxiv_id)
        
        if not result['success']:
            return render_template('error.html', 
                                   error="分析结果不存在，请先进行深度分析"), 404
        
        # 获取论文基本信息
        paper = paper_service.get_paper_detail(arxiv_id)
        if not paper:
            return render_template('error.html', error="论文不存在"), 404
        
        return render_template('paper_analysis.html', 
                             paper=paper, 
                             analysis=result)
    
    except Exception as e:
        logger.error(f"显示分析结果失败 {arxiv_id}: {e}")
        return render_template('error.html', error="加载分析结果失败"), 500

@app.route('/paper/<arxiv_id>/analysis_images/<filename>')
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

@app.route('/paper/<arxiv_id>/imgs/<filename>')
def serve_analysis_image_fallback(arxiv_id, filename):
    """
    向后兼容的图片服务路由
    将旧的 imgs/ 路径重定向到正确的 analysis_images/ 路径
    """
    try:
        logger.info(f"Fallback route accessed for {arxiv_id}/imgs/{filename}, redirecting to analysis_images")
        # 重定向到正确的analysis_images路由
        from flask import redirect, url_for
        return redirect(url_for('serve_analysis_image', arxiv_id=arxiv_id, filename=filename), code=301)
    except Exception as e:
        logger.error(f"Fallback route failed {arxiv_id}/{filename}: {e}")
        return "Image redirect failed", 500

@app.route('/api/paper/<arxiv_id>/download_analysis')
def api_download_analysis(arxiv_id):
    """API接口 - 下载分析结果（Markdown + 图片打包为ZIP）"""
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
            # 清理临时文件（在发送后会被自动删除）
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
    
    Args:
        content: 原始Markdown内容
        arxiv_id: ArXiv论文ID
        
    Returns:
        str: 处理后的Markdown内容
    """
    try:
        # 将网页URL路径转换为相对路径
        pattern = rf'/paper/{re.escape(arxiv_id)}/analysis_images/([^)]+)'
        replacement = r'imgs/\1'
        
        processed_content = re.sub(pattern, replacement, content)
        
        return processed_content
        
    except Exception as e:
        logger.error(f"处理Markdown下载内容失败: {e}")
        return content

@app.route('/api/analysis/active')
def api_active_analyses():
    """API接口 - 获取当前活跃的分析任务"""
    try:
        result = analysis_service.get_active_analyses()
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"获取活跃分析失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


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