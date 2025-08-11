"""
数据库操作模块 - 论文数据访问
"""
import psycopg2
import psycopg2.extras
import redis
import json
import re
import sys
import os
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
try:
    from ..config import DATABASE_CONFIG, REDIS_CONFIG
except ImportError:
    # 如果相对导入失败，使用绝对导入
    from config import DATABASE_CONFIG, REDIS_CONFIG
import logging

# 添加 HomeSystem 模块路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

# 导入 Dify 和 ArXiv 模块
from HomeSystem.integrations.dify.dify_knowledge import DifyKnowledgeBaseClient, DifyKnowledgeBaseConfig
from HomeSystem.utility.arxiv.arxiv import ArxivData

logger = logging.getLogger(__name__)


def datetime_serializer(obj):
    """JSON序列化时处理datetime对象"""
    if isinstance(obj, datetime):
        return {'__datetime__': obj.isoformat()}
    return str(obj)


def datetime_deserializer(dct):
    """JSON反序列化时处理datetime对象"""
    if isinstance(dct, dict):
        if '__datetime__' in dct:
            return datetime.fromisoformat(dct['__datetime__'])
        # 处理嵌套结构中的datetime对象
        for key, value in dct.items():
            if isinstance(value, dict) and '__datetime__' in value:
                dct[key] = datetime.fromisoformat(value['__datetime__'])
    return dct


def sanitize_filename(filename: str, max_length: int = 200) -> str:
    """
    清理文件名，移除或替换不安全的字符
    
    Args:
        filename: 原始文件名
        max_length: 最大文件名长度
        
    Returns:
        清理后的安全文件名
    """
    if not filename:
        return 'document'
    
    # 确保filename是字符串并移除换行符和控制字符
    filename = str(filename).strip()
    filename = re.sub(r'[\r\n\t\v\f]', ' ', filename)  # 替换换行符和控制字符为空格
    filename = re.sub(r'\s+', ' ', filename)  # 压缩多个空格为单个空格
    
    # 移除或替换不安全的字符
    # 在Windows和许多文件系统中不允许的字符: / \ : * ? " < > |
    # 以及其他可能导致问题的字符
    unsafe_chars = r'[/\\:*?"<>|\x00-\x1f\x7f-\x9f]'
    safe_filename = re.sub(unsafe_chars, '_', filename)
    
    # 移除开头和结尾的空格、点号和下划线
    safe_filename = safe_filename.strip('. _')
    
    # 移除连续的下划线并替换为单个下划线
    safe_filename = re.sub(r'_+', '_', safe_filename)
    
    # 如果文件名为空或只包含无效字符，使用默认名称
    if not safe_filename or safe_filename == '_':
        safe_filename = 'document'
    
    # 限制长度（考虑UTF-8编码）
    if len(safe_filename.encode('utf-8')) > max_length:
        # 按字节长度截断，确保不破坏UTF-8字符
        encoded = safe_filename.encode('utf-8')[:max_length]
        # 找到最后一个完整的UTF-8字符
        while len(encoded) > 0:
            try:
                safe_filename = encoded.decode('utf-8')
                break
            except UnicodeDecodeError:
                encoded = encoded[:-1]
        
        # 移除末尾的空格、点号和下划线
        safe_filename = safe_filename.rstrip('. _')
    
    # 最终检查，确保不为空
    if not safe_filename:
        safe_filename = 'document'
    
    return safe_filename


def parse_keywords_string(keywords_string: str) -> List[str]:
    """
    解析关键词字符串，提取个别关键词
    
    支持格式:
    - JSON数组格式: {"keyword1","keyword2","keyword3"}
    - 逗号分隔格式: keyword1, keyword2, keyword3
    - 分号分隔格式: keyword1; keyword2; keyword3
    
    Args:
        keywords_string: 关键词字符串
        
    Returns:
        List[str]: 解析后的关键词列表
    """
    if not keywords_string:
        return []
    
    # 确保可以安全调用 strip()
    keywords_string = str(keywords_string).strip()
    if not keywords_string:
        return []
    
    # 处理JSON数组格式: {"keyword1","keyword2","keyword3"}
    if keywords_string.startswith('{') and keywords_string.endswith('}'):
        try:
            # 移除外层大括号
            content = keywords_string[1:-1]
            # 使用正则表达式提取所有引号内的内容
            keywords = re.findall(r'"([^"]*)"', content)
            return [kw.strip() for kw in keywords if kw.strip()]
        except Exception as e:
            logger.warning(f"解析JSON格式关键词失败: {e}, 原始字符串: {keywords_string}")
    
    # 处理标准JSON数组格式: ["keyword1","keyword2","keyword3"]
    if keywords_string.startswith('[') and keywords_string.endswith(']'):
        try:
            keywords_list = json.loads(keywords_string)
            return [str(kw).strip() for kw in keywords_list if str(kw).strip()]
        except Exception as e:
            logger.warning(f"解析标准JSON数组格式关键词失败: {e}, 原始字符串: {keywords_string}")
    
    # 处理逗号或分号分隔的格式
    separators = [',', ';', '|']
    for sep in separators:
        if sep in keywords_string:
            keywords = [kw.strip().strip('"\'') for kw in keywords_string.split(sep)]
            return [kw for kw in keywords if kw]
    
    # 如果没有分隔符，返回单个关键词
    return [keywords_string.strip().strip('"\'')]


class DatabaseManager:
    """数据库管理器"""
    
    def __init__(self):
        self.db_config = DATABASE_CONFIG
        self.redis_config = REDIS_CONFIG
        self._redis_client = None
    
    def get_db_connection(self):
        """获取数据库连接"""
        try:
            conn = psycopg2.connect(**self.db_config)
            return conn
        except Exception as e:
            logger.error(f"数据库连接失败: {e}")
            raise
    
    def get_redis_client(self):
        """获取Redis客户端"""
        if self._redis_client is None:
            try:
                self._redis_client = redis.Redis(
                    **self.redis_config, 
                    decode_responses=True
                )
                self._redis_client.ping()
            except Exception as e:
                logger.warning(f"Redis连接失败: {e}")
                self._redis_client = None
        return self._redis_client
    
    def get_cache(self, key: str) -> Optional[Any]:
        """从缓存获取数据"""
        redis_client = self.get_redis_client()
        if redis_client:
            try:
                cached_data = redis_client.get(key)
                if cached_data:
                    try:
                        return json.loads(cached_data, object_hook=datetime_deserializer)
                    except (ValueError, TypeError) as e:
                        # 如果反序列化失败，可能是旧格式的缓存，删除它
                        logger.warning(f"缓存格式不兼容，删除旧缓存: {key}")
                        redis_client.delete(key)
                        return None
            except Exception as e:
                logger.warning(f"缓存读取失败: {e}")
        return None
    
    def set_cache(self, key: str, data: Any, timeout: int = 300):
        """设置缓存数据"""
        redis_client = self.get_redis_client()
        if redis_client:
            try:
                redis_client.setex(key, timeout, json.dumps(data, default=datetime_serializer))
            except Exception as e:
                logger.warning(f"缓存设置失败: {e}")


class PaperService:
    """论文数据服务"""
    
    def __init__(self):
        self.db_manager = DatabaseManager()
    
    def get_overview_stats(self) -> Dict[str, Any]:
        """获取概览统计信息"""
        cache_key = "overview_stats"
        cached_data = self.db_manager.get_cache(cache_key)
        if cached_data:
            return cached_data
        
        with self.db_manager.get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            # 基础统计
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_papers,
                    COUNT(CASE WHEN processing_status = 'completed' THEN 1 END) as completed,
                    COUNT(CASE WHEN processing_status = 'pending' THEN 1 END) as pending,
                    COUNT(CASE WHEN processing_status = 'failed' THEN 1 END) as failed,
                    COUNT(CASE WHEN research_objectives IS NOT NULL THEN 1 END) as structured_count
                FROM arxiv_papers
            """)
            basic_stats = dict(cursor.fetchone())
            
            # 最近7天统计
            cursor.execute("""
                SELECT created_at::date as date, COUNT(*) as count
                FROM arxiv_papers 
                WHERE created_at >= NOW() - INTERVAL '7 days'
                GROUP BY created_at::date 
                ORDER BY date ASC
            """)
            recent_stats = [dict(row) for row in cursor.fetchall()]
            
            # 热门分类
            cursor.execute("""
                SELECT categories, COUNT(*) as count
                FROM arxiv_papers 
                WHERE categories IS NOT NULL AND categories != ''
                GROUP BY categories 
                ORDER BY count DESC 
                LIMIT 10
            """)
            popular_categories = [dict(row) for row in cursor.fetchall()]
            
            stats = {
                'basic': basic_stats,
                'recent': recent_stats,
                'categories': popular_categories
            }
            
            # 缓存结果
            self.db_manager.set_cache(cache_key, stats, timeout=900)
            return stats
    
    def search_papers(self, query: str = "", category: str = "", status: str = "",
                     task_name = None, task_id: str = "", 
                     page: int = 1, per_page: int = 20) -> Tuple[List[Dict], int]:
        """搜索论文"""
        with self.db_manager.get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            # 构建WHERE条件
            conditions = []
            params = []
            
            if query:
                conditions.append("""
                    (title ILIKE %s OR abstract ILIKE %s OR authors ILIKE %s 
                     OR research_objectives ILIKE %s OR keywords ILIKE %s)
                """)
                query_param = f"%{query}%"
                params.extend([query_param] * 5)
            
            if category:
                conditions.append("categories ILIKE %s")
                params.append(f"%{category}%")
            
            if status:
                conditions.append("processing_status = %s")
                params.append(status)
            
            # 处理任务名称筛选（支持多选和"未分配任务"）
            if task_name:
                # 支持单个字符串或列表
                if isinstance(task_name, str):
                    task_names = [task_name] if task_name.strip() else []
                else:
                    task_names = task_name
                
                if task_names:
                    task_conditions = []
                    
                    # 检查是否包含"未分配任务"选项
                    if "未分配任务" in task_names:
                        task_conditions.append("(task_name IS NULL OR task_name = '')")
                        task_names = [name for name in task_names if name != "未分配任务"]
                    
                    # 处理具体的任务名称
                    if task_names:
                        placeholders = ", ".join(["%s"] * len(task_names))
                        task_conditions.append(f"task_name IN ({placeholders})")
                        params.extend(task_names)
                    
                    if task_conditions:
                        conditions.append(f"({' OR '.join(task_conditions)})")
                
            if task_id:
                conditions.append("task_id = %s")
                params.append(task_id)
            
            where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
            
            # 获取总数
            count_query = f"""
                SELECT COUNT(*) as total
                FROM arxiv_papers 
                {where_clause}
            """
            cursor.execute(count_query, params)
            total = cursor.fetchone()['total']
            
            # 获取分页数据
            offset = (page - 1) * per_page
            data_query = f"""
                SELECT arxiv_id, title, authors, categories, processing_status, 
                       created_at, published_date, research_objectives, keywords, task_name, task_id,
                       full_paper_relevance_score, full_paper_relevance_justification,
                       dify_document_id, deep_analysis_result, deep_analysis_status
                FROM arxiv_papers 
                {where_clause}
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
            """
            cursor.execute(data_query, params + [per_page, offset])
            papers = [dict(row) for row in cursor.fetchall()]
            
            # 为每个论文添加深度分析标识
            for paper in papers:
                paper['has_deep_analysis'] = bool(paper.get('deep_analysis_result'))
            
            return papers, total
    
    def get_paper_detail(self, arxiv_id: str) -> Optional[Dict]:
        """获取论文详细信息，优先显示深度分析内容"""
        cache_key = f"paper_detail_{arxiv_id}"
        cached_data = self.db_manager.get_cache(cache_key)
        if cached_data:
            return cached_data
        
        with self.db_manager.get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            cursor.execute("""
                SELECT * FROM arxiv_papers WHERE arxiv_id = %s
            """, (arxiv_id,))
            
            paper = cursor.fetchone()
            if paper:
                paper_dict = dict(paper)
                # 处理JSON字段
                if isinstance(paper_dict.get('tags'), str):
                    try:
                        paper_dict['tags'] = json.loads(paper_dict['tags'])
                    except:
                        paper_dict['tags'] = []
                
                if isinstance(paper_dict.get('metadata'), str):
                    try:
                        paper_dict['metadata'] = json.loads(paper_dict['metadata'])
                    except:
                        paper_dict['metadata'] = {}
                
                # 检查是否存在深度分析内容，如果存在则优先使用
                if paper_dict.get('deep_analysis_result'):
                    # 标记内容来源为深度分析
                    paper_dict['content_source'] = 'deep_analysis'
                    paper_dict['has_deep_analysis'] = True
                    
                    # 使用深度分析内容替换原有的结构化字段（用于显示摘要部分）
                    # 保留原始数据库翻译字段以备查看
                    paper_dict['original_research_background'] = paper_dict.get('research_background')
                    paper_dict['original_research_objectives'] = paper_dict.get('research_objectives')
                    paper_dict['original_methods'] = paper_dict.get('methods')
                    paper_dict['original_key_findings'] = paper_dict.get('key_findings')
                    paper_dict['original_conclusions'] = paper_dict.get('conclusions')
                    paper_dict['original_limitations'] = paper_dict.get('limitations')
                    paper_dict['original_future_work'] = paper_dict.get('future_work')
                    
                    # 提取深度分析内容的前几段用于摘要显示
                    deep_analysis_text = paper_dict['deep_analysis_result']
                    if deep_analysis_text:
                        # 简单提取前500字符作为摘要
                        lines = deep_analysis_text.split('\n')
                        preview_lines = []
                        char_count = 0
                        for line in lines:
                            if char_count + len(line) > 500:
                                break
                            preview_lines.append(line)
                            char_count += len(line)
                        
                        paper_dict['deep_analysis_preview'] = '\n'.join(preview_lines)
                        if char_count >= 500:
                            paper_dict['deep_analysis_preview'] += '\n\n... (查看完整深度分析)'
                else:
                    # 使用数据库翻译字段
                    paper_dict['content_source'] = 'database_translation'
                    paper_dict['has_deep_analysis'] = False
                
                # 缓存结果
                self.db_manager.set_cache(cache_key, paper_dict, timeout=600)
                return paper_dict
        
        return None
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取详细统计信息"""
        cache_key = "detailed_statistics"
        cached_data = self.db_manager.get_cache(cache_key)
        if cached_data:
            return cached_data
        
        with self.db_manager.get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            # 按状态统计
            cursor.execute("""
                SELECT processing_status, COUNT(*) as count
                FROM arxiv_papers 
                GROUP BY processing_status
                ORDER BY count DESC
            """)
            status_stats = [dict(row) for row in cursor.fetchall()]
            
            # 月度趋势
            cursor.execute("""
                SELECT 
                    DATE_TRUNC('month', created_at) as month,
                    COUNT(*) as count
                FROM arxiv_papers 
                WHERE created_at >= NOW() - INTERVAL '12 months'
                GROUP BY DATE_TRUNC('month', created_at)
                ORDER BY month
            """)
            monthly_trend = [dict(row) for row in cursor.fetchall()]
            
            # 分类分布
            cursor.execute("""
                SELECT 
                    categories,
                    COUNT(*) as count,
                    COUNT(CASE WHEN research_objectives IS NOT NULL THEN 1 END) as structured_count
                FROM arxiv_papers 
                WHERE categories IS NOT NULL AND categories != ''
                GROUP BY categories
                ORDER BY count DESC
                LIMIT 20
            """)
            category_distribution = [dict(row) for row in cursor.fetchall()]
            
            # 结构化字段完整性
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(research_background) as has_background,
                    COUNT(research_objectives) as has_objectives,
                    COUNT(methods) as has_methods,
                    COUNT(key_findings) as has_findings,
                    COUNT(conclusions) as has_conclusions,
                    COUNT(keywords) as has_keywords
                FROM arxiv_papers
            """)
            structured_completeness = dict(cursor.fetchone())
            
            stats = {
                'status': status_stats,
                'monthly': monthly_trend,
                'categories': category_distribution,
                'structured': structured_completeness
            }
            
            # 缓存结果
            self.db_manager.set_cache(cache_key, stats, timeout=900)
            return stats
    
    def get_research_insights(self) -> Dict[str, Any]:
        """获取研究洞察"""
        cache_key = "research_insights"
        cached_data = self.db_manager.get_cache(cache_key)
        if cached_data:
            return cached_data
        
        with self.db_manager.get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            # 关键词分析 - 先获取所有关键词字符串，然后解析
            cursor.execute("""
                SELECT keywords
                FROM arxiv_papers 
                WHERE keywords IS NOT NULL AND keywords != ''
            """)
            raw_keywords = cursor.fetchall()
            
            # 解析关键词并统计频率
            keyword_frequency = {}
            for row in raw_keywords:
                keywords_string = row['keywords']  # 使用字典键访问
                parsed_keywords = parse_keywords_string(keywords_string)
                for keyword in parsed_keywords:
                    if keyword:  # 确保关键词不为空
                        keyword_frequency[keyword] = keyword_frequency.get(keyword, 0) + 1
            
            # 按频率排序并限制数量
            keyword_analysis = [
                {'keywords': keyword, 'frequency': frequency}
                for keyword, frequency in sorted(keyword_frequency.items(), key=lambda x: x[1], reverse=True)[:50]
            ]
            
            # 研究方法趋势
            cursor.execute("""
                SELECT methods, COUNT(*) as count
                FROM arxiv_papers 
                WHERE methods IS NOT NULL AND methods != ''
                GROUP BY methods
                ORDER BY count DESC
                LIMIT 20
            """)
            method_trends = [dict(row) for row in cursor.fetchall()]
            
            # 高影响力论文（基于结构化分析完整性）
            cursor.execute("""
                SELECT arxiv_id, title, authors,
                       CASE WHEN research_background IS NOT NULL THEN 1 ELSE 0 END +
                       CASE WHEN research_objectives IS NOT NULL THEN 1 ELSE 0 END +
                       CASE WHEN methods IS NOT NULL THEN 1 ELSE 0 END +
                       CASE WHEN key_findings IS NOT NULL THEN 1 ELSE 0 END +
                       CASE WHEN conclusions IS NOT NULL THEN 1 ELSE 0 END +
                       CASE WHEN keywords IS NOT NULL THEN 1 ELSE 0 END as completeness_score
                FROM arxiv_papers
                ORDER BY completeness_score DESC, created_at DESC
                LIMIT 10
            """)
            high_impact_papers = [dict(row) for row in cursor.fetchall()]
            
            insights = {
                'keywords': keyword_analysis,
                'methods': method_trends,
                'high_impact': high_impact_papers
            }
            
            # 缓存结果
            self.db_manager.set_cache(cache_key, insights, timeout=1800)
            return insights
    
    def get_available_tasks(self) -> Dict[str, Any]:
        """获取可用的任务列表"""
        cache_key = "available_tasks"
        cached_data = self.db_manager.get_cache(cache_key)
        if cached_data:
            return cached_data
        
        with self.db_manager.get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            # 获取所有任务名称及其论文数量
            cursor.execute("""
                SELECT task_name, COUNT(*) as paper_count
                FROM arxiv_papers 
                WHERE task_name IS NOT NULL AND task_name != ''
                GROUP BY task_name
                ORDER BY paper_count DESC, task_name
            """)
            task_names = [dict(row) for row in cursor.fetchall()]
            
            # 获取所有任务ID及其论文数量
            cursor.execute("""
                SELECT task_id, task_name, COUNT(*) as paper_count,
                       MIN(created_at) as first_created,
                       MAX(created_at) as last_created
                FROM arxiv_papers 
                WHERE task_id IS NOT NULL AND task_id != ''
                GROUP BY task_id, task_name
                ORDER BY last_created DESC
            """)
            task_ids = [dict(row) for row in cursor.fetchall()]
            
            tasks = {
                'task_names': task_names,
                'task_ids': task_ids
            }
            
            # 缓存结果
            self.db_manager.set_cache(cache_key, tasks, timeout=600)
            return tasks
    
    def update_task_name(self, arxiv_id: str, new_task_name: str) -> bool:
        """更新单个论文的任务名称"""
        try:
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    UPDATE arxiv_papers 
                    SET task_name = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE arxiv_id = %s
                """, (new_task_name, arxiv_id))
                
                success = cursor.rowcount > 0
                conn.commit()
                
                if success:
                    # 清除相关缓存
                    self._clear_task_related_cache()
                
                return success
                
        except Exception as e:
            logger.error(f"更新任务名称失败: {e}")
            return False
    
    def batch_update_task_name(self, old_task_name: str, new_task_name: str) -> int:
        """批量更新任务名称"""
        try:
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    UPDATE arxiv_papers 
                    SET task_name = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE task_name = %s
                """, (new_task_name, old_task_name))
                
                affected_rows = cursor.rowcount
                conn.commit()
                
                if affected_rows > 0:
                    # 清除相关缓存
                    self._clear_task_related_cache()
                
                return affected_rows
                
        except Exception as e:
            logger.error(f"批量更新任务名称失败: {e}")
            return 0
    
    def delete_paper(self, arxiv_id: str) -> bool:
        """删除单个论文"""
        try:
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    DELETE FROM arxiv_papers WHERE arxiv_id = %s
                """, (arxiv_id,))
                
                success = cursor.rowcount > 0
                conn.commit()
                
                if success:
                    # 清除相关缓存
                    self._clear_all_cache()
                
                return success
                
        except Exception as e:
            logger.error(f"删除论文失败: {e}")
            return False
    
    def delete_papers_by_task(self, task_name: str = None, task_id: str = None) -> int:
        """按任务删除论文"""
        if not task_name and not task_id:
            return 0
            
        try:
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor()
                
                if task_name:
                    cursor.execute("""
                        DELETE FROM arxiv_papers WHERE task_name = %s
                    """, (task_name,))
                elif task_id:
                    cursor.execute("""
                        DELETE FROM arxiv_papers WHERE task_id = %s
                    """, (task_id,))
                
                affected_rows = cursor.rowcount
                conn.commit()
                
                if affected_rows > 0:
                    # 清除相关缓存
                    self._clear_all_cache()
                
                return affected_rows
                
        except Exception as e:
            logger.error(f"按任务删除论文失败: {e}")
            return 0
    
    def get_papers_by_task_name(self, task_name: str) -> List[Dict]:
        """获取指定任务名称的所有论文"""
        with self.db_manager.get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            cursor.execute("""
                SELECT arxiv_id, title, authors, categories, processing_status, 
                       created_at, task_name, task_id,
                       full_paper_relevance_score, full_paper_relevance_justification,
                       dify_document_id
                FROM arxiv_papers 
                WHERE task_name = %s
                ORDER BY created_at DESC
            """, (task_name,))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_task_statistics(self) -> Dict[str, Any]:
        """获取任务统计信息"""
        cache_key = "task_statistics"
        cached_data = self.db_manager.get_cache(cache_key)
        if cached_data:
            return cached_data
        
        with self.db_manager.get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            # 按任务名称统计
            cursor.execute("""
                SELECT 
                    task_name,
                    COUNT(*) as paper_count,
                    COUNT(CASE WHEN processing_status = 'completed' THEN 1 END) as completed_count,
                    COUNT(CASE WHEN processing_status = 'pending' THEN 1 END) as pending_count,
                    COUNT(CASE WHEN processing_status = 'failed' THEN 1 END) as failed_count,
                    MIN(created_at) as first_paper,
                    MAX(created_at) as last_paper
                FROM arxiv_papers 
                WHERE task_name IS NOT NULL AND task_name != ''
                GROUP BY task_name
                ORDER BY paper_count DESC, task_name
            """)
            task_name_stats = [dict(row) for row in cursor.fetchall()]
            
            # 总体统计
            cursor.execute("""
                SELECT 
                    COUNT(CASE WHEN task_name IS NOT NULL THEN 1 END) as papers_with_task,
                    COUNT(CASE WHEN task_name IS NULL THEN 1 END) as papers_without_task,
                    COUNT(DISTINCT task_name) as unique_task_names,
                    COUNT(DISTINCT task_id) as unique_task_ids
                FROM arxiv_papers
            """)
            overall_stats = dict(cursor.fetchone())
            
            stats = {
                'task_name_stats': task_name_stats,
                'overall': overall_stats
            }
            
            # 缓存结果
            self.db_manager.set_cache(cache_key, stats, timeout=600)
            return stats
    
    def _clear_task_related_cache(self):
        """清除任务相关的缓存"""
        redis_client = self.db_manager.get_redis_client()
        if redis_client:
            try:
                keys_to_delete = [
                    "available_tasks",
                    "available_tasks_migration",
                    "task_statistics", 
                    "overview_stats",
                    "unassigned_papers_stats"
                ]
                for key in keys_to_delete:
                    redis_client.delete(key)
            except Exception as e:
                logger.warning(f"清除缓存失败: {e}")
    
    def _clear_all_cache(self):
        """清除所有相关缓存"""
        redis_client = self.db_manager.get_redis_client()
        if redis_client:
            try:
                # 删除统计相关缓存
                keys_to_delete = [
                    "overview_stats",
                    "detailed_statistics",
                    "research_insights",
                    "available_tasks",
                    "available_tasks_migration",
                    "task_statistics",
                    "unassigned_papers_stats"
                ]
                for key in keys_to_delete:
                    redis_client.delete(key)
                
                # 删除论文详情缓存 (使用模式匹配)
                for key in redis_client.scan_iter(match="paper_detail_*"):
                    redis_client.delete(key)
                    
            except Exception as e:
                logger.warning(f"清除缓存失败: {e}")
    
    def get_papers_without_tasks(self, page: int = 1, per_page: int = 20) -> Tuple[List[Dict], int]:
        """获取没有分配任务的论文"""
        with self.db_manager.get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            # 获取总数
            cursor.execute("""
                SELECT COUNT(*) as total
                FROM arxiv_papers 
                WHERE task_name IS NULL OR task_name = ''
            """)
            total = cursor.fetchone()['total']
            
            # 获取分页数据
            offset = (page - 1) * per_page
            cursor.execute("""
                SELECT arxiv_id, title, authors, categories, processing_status, 
                       created_at, published_date, research_objectives, keywords, task_name, task_id,
                       full_paper_relevance_score, full_paper_relevance_justification,
                       dify_document_id
                FROM arxiv_papers 
                WHERE task_name IS NULL OR task_name = ''
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
            """, (per_page, offset))
            
            papers = [dict(row) for row in cursor.fetchall()]
            return papers, total
    
    def assign_task_to_paper(self, arxiv_id: str, task_name: str, task_id: str = None) -> bool:
        """为单个论文分配任务"""
        try:
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    UPDATE arxiv_papers 
                    SET task_name = %s, task_id = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE arxiv_id = %s
                """, (task_name, task_id, arxiv_id))
                
                success = cursor.rowcount > 0
                conn.commit()
                
                if success:
                    # 清除相关缓存
                    self._clear_task_related_cache()
                
                return success
                
        except Exception as e:
            logger.error(f"分配任务失败: {e}")
            return False
    
    def batch_assign_task_to_papers(self, arxiv_ids: List[str], task_name: str, task_id: str = None) -> int:
        """批量为论文分配任务"""
        if not arxiv_ids:
            return 0
            
        try:
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor()
                
                # 使用IN子句批量更新
                placeholders = ','.join(['%s'] * len(arxiv_ids))
                cursor.execute(f"""
                    UPDATE arxiv_papers 
                    SET task_name = %s, task_id = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE arxiv_id IN ({placeholders})
                """, [task_name, task_id] + arxiv_ids)
                
                affected_rows = cursor.rowcount
                conn.commit()
                
                if affected_rows > 0:
                    # 清除相关缓存
                    self._clear_task_related_cache()
                
                return affected_rows
                
        except Exception as e:
            logger.error(f"批量分配任务失败: {e}")
            return 0
    
    def get_unassigned_papers_stats(self) -> Dict[str, Any]:
        """获取无任务论文统计信息"""
        cache_key = "unassigned_papers_stats"
        cached_data = self.db_manager.get_cache(cache_key)
        if cached_data:
            return cached_data
        
        with self.db_manager.get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            # 基础统计
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_unassigned,
                    COUNT(CASE WHEN processing_status = 'completed' THEN 1 END) as completed_unassigned,
                    COUNT(CASE WHEN processing_status = 'pending' THEN 1 END) as pending_unassigned,
                    COUNT(CASE WHEN processing_status = 'failed' THEN 1 END) as failed_unassigned
                FROM arxiv_papers
                WHERE task_name IS NULL OR task_name = ''
            """)
            basic_stats = dict(cursor.fetchone())
            
            # 按分类统计无任务论文
            cursor.execute("""
                SELECT categories, COUNT(*) as count
                FROM arxiv_papers 
                WHERE (task_name IS NULL OR task_name = '') 
                  AND categories IS NOT NULL AND categories != ''
                GROUP BY categories 
                ORDER BY count DESC 
                LIMIT 10
            """)
            category_stats = [dict(row) for row in cursor.fetchall()]
            
            # 最近无任务论文趋势
            cursor.execute("""
                SELECT created_at::date as date, COUNT(*) as count
                FROM arxiv_papers 
                WHERE (task_name IS NULL OR task_name = '') 
                  AND created_at >= NOW() - INTERVAL '7 days'
                GROUP BY created_at::date 
                ORDER BY date DESC
            """)
            recent_stats = [dict(row) for row in cursor.fetchall()]
            
            stats = {
                'basic': basic_stats,
                'categories': category_stats,
                'recent': recent_stats
            }
            
            # 缓存结果
            self.db_manager.set_cache(cache_key, stats, timeout=600)
            return stats
    
    def update_paper_relevance(self, arxiv_id: str, relevance_score: float = None, 
                              relevance_justification: str = None) -> bool:
        """更新论文相关度评分和理由"""
        try:
            # 验证评分范围
            if relevance_score is not None:
                if not (0 <= relevance_score <= 1):
                    logger.error(f"相关度评分超出范围: {relevance_score}，应在0-1之间")
                    return False
            
            # 验证理由长度
            if relevance_justification is not None:
                if len(relevance_justification.strip()) > 5000:
                    logger.error(f"相关度理由过长: {len(relevance_justification)} 字符，最大5000字符")
                    return False
            
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor()
                
                # 构建动态更新语句
                update_fields = []
                params = []
                
                if relevance_score is not None:
                    update_fields.append("full_paper_relevance_score = %s")
                    params.append(relevance_score)
                
                if relevance_justification is not None:
                    update_fields.append("full_paper_relevance_justification = %s") 
                    params.append(relevance_justification.strip())
                
                if not update_fields:
                    logger.warning("没有提供要更新的相关度字段")
                    return False
                
                # 添加更新时间
                update_fields.append("updated_at = CURRENT_TIMESTAMP")
                params.append(arxiv_id)
                
                sql = f"""
                    UPDATE arxiv_papers 
                    SET {', '.join(update_fields)}
                    WHERE arxiv_id = %s
                """
                
                cursor.execute(sql, params)
                success = cursor.rowcount > 0
                conn.commit()
                
                if success:
                    # 清除相关缓存
                    self._clear_paper_detail_cache(arxiv_id)
                    logger.info(f"成功更新论文相关度: {arxiv_id}")
                else:
                    logger.warning(f"论文不存在，无法更新相关度: {arxiv_id}")
                
                return success
                
        except Exception as e:
            logger.error(f"更新论文相关度失败: {e}")
            return False
    
    def _clear_paper_detail_cache(self, arxiv_id: str):
        """清除特定论文的详情缓存"""
        redis_client = self.db_manager.get_redis_client()
        if redis_client:
            try:
                cache_key = f"paper_detail_{arxiv_id}"
                redis_client.delete(cache_key)
            except Exception as e:
                logger.warning(f"清除论文详情缓存失败: {e}")
    
    def get_paper_navigation(self, arxiv_id: str) -> Dict[str, Optional[Dict]]:
        """获取论文导航信息（上一篇和下一篇）"""
        try:
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                
                # 获取当前论文的创建时间
                cursor.execute("""
                    SELECT created_at FROM arxiv_papers WHERE arxiv_id = %s
                """, (arxiv_id,))
                
                current_paper = cursor.fetchone()
                if not current_paper:
                    return {'previous': None, 'next': None}
                
                current_time = current_paper['created_at']
                
                # 获取上一篇论文（创建时间较早的最近一篇）
                cursor.execute("""
                    SELECT arxiv_id, title, created_at
                    FROM arxiv_papers 
                    WHERE created_at < %s
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (current_time,))
                
                previous_paper = cursor.fetchone()
                previous_paper_dict = dict(previous_paper) if previous_paper else None
                
                # 获取下一篇论文（创建时间较晚的最近一篇）
                cursor.execute("""
                    SELECT arxiv_id, title, created_at
                    FROM arxiv_papers 
                    WHERE created_at > %s
                    ORDER BY created_at ASC
                    LIMIT 1
                """, (current_time,))
                
                next_paper = cursor.fetchone()
                next_paper_dict = dict(next_paper) if next_paper else None
                
                return {
                    'previous': previous_paper_dict,
                    'next': next_paper_dict
                }
                
        except Exception as e:
            logger.error(f"获取论文导航信息失败: {e}")
            return {'previous': None, 'next': None}
    
    def get_available_tasks_for_migration(self) -> Dict[str, Any]:
        """获取可用于迁移的任务列表（包含详细信息）"""
        cache_key = "available_tasks_migration"
        cached_data = self.db_manager.get_cache(cache_key)
        if cached_data:
            return cached_data
        
        with self.db_manager.get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            # 获取所有任务的详细信息
            cursor.execute("""
                SELECT 
                    task_name,
                    task_id,
                    COUNT(*) as paper_count,
                    MIN(created_at) as first_created,
                    MAX(created_at) as last_created,
                    COUNT(CASE WHEN processing_status = 'completed' THEN 1 END) as completed_count,
                    COUNT(CASE WHEN processing_status = 'pending' THEN 1 END) as pending_count,
                    COUNT(CASE WHEN processing_status = 'failed' THEN 1 END) as failed_count
                FROM arxiv_papers 
                WHERE task_name IS NOT NULL AND task_name != ''
                GROUP BY task_name, task_id
                ORDER BY last_created DESC, paper_count DESC
            """)
            
            tasks = [dict(row) for row in cursor.fetchall()]
            
            # 获取每个任务的代表性分类
            for task in tasks:
                cursor.execute("""
                    SELECT categories, COUNT(*) as count
                    FROM arxiv_papers 
                    WHERE task_name = %s AND categories IS NOT NULL AND categories != ''
                    GROUP BY categories
                    ORDER BY count DESC
                    LIMIT 3
                """, (task['task_name'],))
                
                categories = [row['categories'] for row in cursor.fetchall()]
                task['top_categories'] = categories
            
            result = {'tasks': tasks}
            
            # 缓存结果
            self.db_manager.set_cache(cache_key, result, timeout=300)
            return result
    
    def migrate_paper_to_task(self, arxiv_id: str, target_task_name: str, target_task_id: str = None) -> bool:
        """将论文迁移到指定任务"""
        try:
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor()
                
                # 检查论文是否存在
                cursor.execute("""
                    SELECT task_name, task_id FROM arxiv_papers WHERE arxiv_id = %s
                """, (arxiv_id,))
                
                current_paper = cursor.fetchone()
                if not current_paper:
                    logger.error(f"论文不存在: {arxiv_id}")
                    return False
                
                # 执行迁移
                cursor.execute("""
                    UPDATE arxiv_papers 
                    SET task_name = %s, task_id = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE arxiv_id = %s
                """, (target_task_name, target_task_id, arxiv_id))
                
                success = cursor.rowcount > 0
                conn.commit()
                
                if success:
                    # 清除相关缓存
                    self._clear_task_related_cache()
                    logger.info(f"论文迁移成功: {arxiv_id} -> {target_task_name}")
                
                return success
                
        except Exception as e:
            logger.error(f"论文迁移失败: {e}")
            return False
    
    def batch_migrate_papers_to_task(self, arxiv_ids: List[str], target_task_name: str, 
                                   target_task_id: str = None) -> Tuple[int, List[str]]:
        """批量将论文迁移到指定任务"""
        if not arxiv_ids:
            return 0, []
            
        try:
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor()
                
                # 检查哪些论文存在
                placeholders = ','.join(['%s'] * len(arxiv_ids))
                cursor.execute(f"""
                    SELECT arxiv_id FROM arxiv_papers WHERE arxiv_id IN ({placeholders})
                """, arxiv_ids)
                
                existing_papers = [row[0] for row in cursor.fetchall()]
                missing_papers = list(set(arxiv_ids) - set(existing_papers))
                
                if not existing_papers:
                    return 0, arxiv_ids
                
                # 批量迁移存在的论文
                placeholders = ','.join(['%s'] * len(existing_papers))
                cursor.execute(f"""
                    UPDATE arxiv_papers 
                    SET task_name = %s, task_id = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE arxiv_id IN ({placeholders})
                """, [target_task_name, target_task_id] + existing_papers)
                
                affected_rows = cursor.rowcount
                conn.commit()
                
                if affected_rows > 0:
                    # 清除相关缓存
                    self._clear_task_related_cache()
                    logger.info(f"批量迁移成功: {affected_rows} 篇论文 -> {target_task_name}")
                
                return affected_rows, missing_papers
                
        except Exception as e:
            logger.error(f"批量迁移失败: {e}")
            return 0, arxiv_ids
    
    def merge_tasks(self, source_task_name: str, target_task_name: str, 
                   target_task_id: str = None) -> int:
        """合并任务：将源任务的所有论文迁移到目标任务"""
        try:
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor()
                
                # 执行任务合并
                cursor.execute("""
                    UPDATE arxiv_papers 
                    SET task_name = %s, task_id = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE task_name = %s
                """, (target_task_name, target_task_id, source_task_name))
                
                affected_rows = cursor.rowcount
                conn.commit()
                
                if affected_rows > 0:
                    # 清除相关缓存
                    self._clear_task_related_cache()
                    logger.info(f"任务合并成功: {source_task_name} -> {target_task_name}, 影响 {affected_rows} 篇论文")
                
                return affected_rows
                
        except Exception as e:
            logger.error(f"任务合并失败: {e}")
            return 0
    
    def get_task_migration_preview(self, arxiv_ids: List[str], target_task_name: str) -> Dict[str, Any]:
        """获取任务迁移预览信息"""
        if not arxiv_ids:
            return {'valid_papers': [], 'invalid_papers': [], 'summary': {}}
        
        try:
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                
                # 获取有效论文信息
                placeholders = ','.join(['%s'] * len(arxiv_ids))
                cursor.execute(f"""
                    SELECT arxiv_id, title, task_name, task_id
                    FROM arxiv_papers 
                    WHERE arxiv_id IN ({placeholders})
                """, arxiv_ids)
                
                valid_papers = [dict(row) for row in cursor.fetchall()]
                valid_ids = [paper['arxiv_id'] for paper in valid_papers]
                invalid_ids = list(set(arxiv_ids) - set(valid_ids))
                
                # 统计信息
                same_task_count = sum(1 for paper in valid_papers if paper['task_name'] == target_task_name)
                different_task_count = len(valid_papers) - same_task_count
                
                # 获取目标任务信息
                cursor.execute("""
                    SELECT COUNT(*) as paper_count, 
                           MAX(created_at) as last_updated
                    FROM arxiv_papers 
                    WHERE task_name = %s
                """, (target_task_name,))
                
                target_task_info = dict(cursor.fetchone()) if cursor.rowcount > 0 else {
                    'paper_count': 0, 'last_updated': None
                }
                
                return {
                    'valid_papers': valid_papers,
                    'invalid_papers': invalid_ids,
                    'summary': {
                        'total_selected': len(arxiv_ids),
                        'valid_count': len(valid_papers),
                        'invalid_count': len(invalid_ids),
                        'same_task_count': same_task_count,
                        'different_task_count': different_task_count,
                        'target_task_info': target_task_info
                    }
                }
                
        except Exception as e:
            logger.error(f"获取迁移预览失败: {e}")
            return {'valid_papers': [], 'invalid_papers': arxiv_ids, 'summary': {}}

    # === 深度论文分析相关方法 ===
    
    def update_analysis_status(self, arxiv_id: str, status: str) -> bool:
        """
        更新论文深度分析状态
        
        Args:
            arxiv_id: ArXiv论文ID
            status: 状态 (pending/processing/completed/failed/cancelled)
            
        Returns:
            bool: 更新是否成功
        """
        try:
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor()
                
                # 首先检查是否需要添加新列（用于兼容性）
                cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'arxiv_papers' 
                    AND column_name IN ('deep_analysis_status', 'deep_analysis_result', 'deep_analysis_created_at', 'deep_analysis_updated_at')
                """)
                existing_columns = [row[0] for row in cursor.fetchall()]
                
                # 如果列不存在，添加它们
                if 'deep_analysis_status' not in existing_columns:
                    cursor.execute("""
                        ALTER TABLE arxiv_papers 
                        ADD COLUMN IF NOT EXISTS deep_analysis_status VARCHAR(20) DEFAULT NULL,
                        ADD COLUMN IF NOT EXISTS deep_analysis_result TEXT DEFAULT NULL,
                        ADD COLUMN IF NOT EXISTS deep_analysis_created_at TIMESTAMP DEFAULT NULL,
                        ADD COLUMN IF NOT EXISTS deep_analysis_updated_at TIMESTAMP DEFAULT NULL
                    """)
                    conn.commit()
                
                # 更新状态
                if status == 'processing' and not self._has_analysis_status(cursor, arxiv_id):
                    # 首次开始分析
                    cursor.execute("""
                        UPDATE arxiv_papers 
                        SET deep_analysis_status = %s,
                            deep_analysis_created_at = CURRENT_TIMESTAMP,
                            deep_analysis_updated_at = CURRENT_TIMESTAMP
                        WHERE arxiv_id = %s
                    """, (status, arxiv_id))
                else:
                    # 更新现有状态
                    cursor.execute("""
                        UPDATE arxiv_papers 
                        SET deep_analysis_status = %s,
                            deep_analysis_updated_at = CURRENT_TIMESTAMP
                        WHERE arxiv_id = %s
                    """, (status, arxiv_id))
                
                success = cursor.rowcount > 0
                conn.commit()
                
                if success:
                    logger.info(f"Updated analysis status for {arxiv_id} to {status}")
                
                return success
                
        except Exception as e:
            logger.error(f"Failed to update analysis status for {arxiv_id}: {e}")
            return False
    
    def _has_analysis_status(self, cursor, arxiv_id: str) -> bool:
        """检查论文是否已有分析状态记录"""
        try:
            cursor.execute("""
                SELECT deep_analysis_status 
                FROM arxiv_papers 
                WHERE arxiv_id = %s 
                AND deep_analysis_status IS NOT NULL
            """, (arxiv_id,))
            return cursor.fetchone() is not None
        except:
            return False
    
    def save_analysis_result(self, arxiv_id: str, markdown_content: str) -> bool:
        """
        保存深度分析结果
        
        Args:
            arxiv_id: ArXiv论文ID
            markdown_content: 分析结果的Markdown内容
            
        Returns:
            bool: 保存是否成功
        """
        try:
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    UPDATE arxiv_papers 
                    SET deep_analysis_result = %s,
                        deep_analysis_status = 'completed',
                        deep_analysis_updated_at = CURRENT_TIMESTAMP
                    WHERE arxiv_id = %s
                """, (markdown_content, arxiv_id))
                
                success = cursor.rowcount > 0
                conn.commit()
                
                if success:
                    logger.info(f"Saved analysis result for {arxiv_id}, {len(markdown_content)} characters")
                    
                    # 清除相关缓存
                    cache_key = f"paper_detail_{arxiv_id}"
                    redis_client = self.db_manager.get_redis_client()
                    if redis_client:
                        redis_client.delete(cache_key)
                
                return success
                
        except Exception as e:
            logger.error(f"Failed to save analysis result for {arxiv_id}: {e}")
            return False
    
    def get_analysis_status(self, arxiv_id: str) -> Optional[Dict[str, Any]]:
        """
        获取深度分析状态信息
        
        Args:
            arxiv_id: ArXiv论文ID
            
        Returns:
            Dict: 状态信息，如果不存在返回None
        """
        try:
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                
                cursor.execute("""
                    SELECT deep_analysis_status as status,
                           deep_analysis_created_at as created_at,
                           deep_analysis_updated_at as updated_at,
                           CASE 
                               WHEN deep_analysis_result IS NOT NULL 
                               THEN LENGTH(deep_analysis_result) 
                               ELSE 0 
                           END as result_length
                    FROM arxiv_papers 
                    WHERE arxiv_id = %s
                """, (arxiv_id,))
                
                result = cursor.fetchone()
                
                if result and result['status']:
                    return dict(result)
                
                return None
                
        except Exception as e:
            logger.error(f"Failed to get analysis status for {arxiv_id}: {e}")
            return None
    
    def get_analysis_result(self, arxiv_id: str) -> Optional[Dict[str, Any]]:
        """
        获取深度分析结果
        
        Args:
            arxiv_id: ArXiv论文ID
            
        Returns:
            Dict: 分析结果信息，如果不存在返回None
        """
        try:
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                
                cursor.execute("""
                    SELECT deep_analysis_result as content,
                           deep_analysis_status as status,
                           deep_analysis_created_at as created_at,
                           deep_analysis_updated_at as updated_at,
                           title, arxiv_id
                    FROM arxiv_papers 
                    WHERE arxiv_id = %s
                    AND deep_analysis_result IS NOT NULL
                """, (arxiv_id,))
                
                result = cursor.fetchone()
                
                if result:
                    return dict(result)
                
                return None
                
        except Exception as e:
            logger.error(f"Failed to get analysis result for {arxiv_id}: {e}")
            return None
    
    def has_analysis_result(self, arxiv_id: str) -> bool:
        """
        检查论文是否已有深度分析结果
        
        Args:
            arxiv_id: ArXiv论文ID
            
        Returns:
            bool: 是否已有分析结果
        """
        try:
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT 1 FROM arxiv_papers 
                    WHERE arxiv_id = %s 
                    AND deep_analysis_result IS NOT NULL 
                    AND deep_analysis_status = 'completed'
                """, (arxiv_id,))
                
                return cursor.fetchone() is not None
                
        except Exception as e:
            logger.error(f"Failed to check analysis result for {arxiv_id}: {e}")
            return False
    
    def get_papers_with_analysis(self, page: int = 1, per_page: int = 20) -> Tuple[List[Dict[str, Any]], int]:
        """
        获取已有深度分析结果的论文列表
        
        Args:
            page: 页码
            per_page: 每页数量
            
        Returns:
            Tuple: (论文列表, 总数量)
        """
        try:
            offset = (page - 1) * per_page
            
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                
                # 获取总数
                cursor.execute("""
                    SELECT COUNT(*) as total
                    FROM arxiv_papers 
                    WHERE deep_analysis_result IS NOT NULL 
                    AND deep_analysis_status = 'completed'
                """)
                total = cursor.fetchone()['total']
                
                # 获取分页数据
                cursor.execute("""
                    SELECT arxiv_id, title, authors, categories, published_date,
                           deep_analysis_status, deep_analysis_created_at, deep_analysis_updated_at,
                           LENGTH(deep_analysis_result) as result_length,
                           task_name, processing_status
                    FROM arxiv_papers 
                    WHERE deep_analysis_result IS NOT NULL 
                    AND deep_analysis_status = 'completed'
                    ORDER BY deep_analysis_updated_at DESC
                    LIMIT %s OFFSET %s
                """, (per_page, offset))
                
                papers = [dict(row) for row in cursor.fetchall()]
                
                return papers, total
                
        except Exception as e:
            logger.error(f"Failed to get papers with analysis: {e}")
            return [], 0
    
    def delete_analysis_result(self, arxiv_id: str) -> bool:
        """
        删除深度分析结果
        
        Args:
            arxiv_id: ArXiv论文ID
            
        Returns:
            bool: 删除是否成功
        """
        try:
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    UPDATE arxiv_papers 
                    SET deep_analysis_result = NULL,
                        deep_analysis_status = NULL,
                        deep_analysis_created_at = NULL,
                        deep_analysis_updated_at = NULL
                    WHERE arxiv_id = %s
                """, (arxiv_id,))
                
                success = cursor.rowcount > 0
                conn.commit()
                
                if success:
                    logger.info(f"Deleted analysis result for {arxiv_id}")
                    
                    # 清除相关缓存
                    cache_key = f"paper_detail_{arxiv_id}"
                    redis_client = self.db_manager.get_redis_client()
                    if redis_client:
                        redis_client.delete(cache_key)
                
                return success
                
        except Exception as e:
            logger.error(f"Failed to delete analysis result for {arxiv_id}: {e}")
            return False

    def get_all_task_names(self) -> List[str]:
        """
        获取所有不同的任务名称
        
        Returns:
            任务名称列表
        """
        try:
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                
                cursor.execute("""
                    SELECT DISTINCT task_name 
                    FROM arxiv_papers 
                    WHERE task_name IS NOT NULL AND task_name != '' 
                    ORDER BY task_name ASC
                """)
                
                result = cursor.fetchall()
                return [row['task_name'] for row in result]
                
        except Exception as e:
            logger.error(f"获取任务名称列表失败: {e}")
            return []
    
    def get_paper_statistics(self) -> Dict[str, Any]:
        """获取论文统计信息，包括Dify相关统计"""
        try:
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                
                # 基础统计
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_papers,
                        COUNT(CASE WHEN processing_status = 'completed' THEN 1 END) as completed_papers,
                        COUNT(CASE WHEN processing_status = 'pending' THEN 1 END) as pending_papers,
                        COUNT(CASE WHEN processing_status = 'failed' THEN 1 END) as failed_papers,
                        COUNT(CASE WHEN research_objectives IS NOT NULL AND research_objectives != '' THEN 1 END) as analyzed_papers,
                        COUNT(CASE WHEN task_name IS NOT NULL AND task_name != '' THEN 1 END) as papers_with_tasks,
                        COUNT(CASE WHEN dify_document_id IS NOT NULL AND dify_document_id != '' THEN 1 END) as dify_uploaded
                    FROM arxiv_papers
                """)
                
                stats = dict(cursor.fetchone())
                
                return stats
                
        except Exception as e:
            logger.error(f"获取论文统计失败: {e}")
            return {
                'total_papers': 0,
                'completed_papers': 0, 
                'pending_papers': 0,
                'failed_papers': 0,
                'analyzed_papers': 0,
                'papers_with_tasks': 0,
                'dify_uploaded': 0
            }

    def recover_interrupted_analysis(self) -> Dict[str, Any]:
        """
        恢复被中断的深度分析任务
        在应用启动时调用，将所有处于'processing'状态的论文重置为'pending'或'failed'
        
        Returns:
            Dict: 恢复操作的结果统计
        """
        try:
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                
                # 查找所有处于processing状态的论文
                cursor.execute("""
                    SELECT arxiv_id, title, deep_analysis_created_at, deep_analysis_updated_at
                    FROM arxiv_papers 
                    WHERE deep_analysis_status = 'processing'
                """)
                
                interrupted_papers = cursor.fetchall()
                
                if not interrupted_papers:
                    logger.info("没有发现被中断的深度分析任务")
                    return {
                        'success': True,
                        'recovered_count': 0,
                        'interrupted_papers': []
                    }
                
                logger.info(f"发现 {len(interrupted_papers)} 个被中断的深度分析任务")
                
                # 将所有中断的任务重置为pending状态
                cursor.execute("""
                    UPDATE arxiv_papers 
                    SET deep_analysis_status = 'pending',
                        deep_analysis_updated_at = CURRENT_TIMESTAMP
                    WHERE deep_analysis_status = 'processing'
                """)
                
                updated_count = cursor.rowcount
                conn.commit()
                
                # 清理Redis中可能残留的进程记录
                redis_client = self.db_manager.get_redis_client()
                if redis_client:
                    try:
                        # 查找所有deep_analysis相关的键
                        pattern = "deep_analysis:process:*"
                        keys = redis_client.keys(pattern)
                        if keys:
                            redis_client.delete(*keys)
                            logger.info(f"清理了 {len(keys)} 个Redis进程记录")
                    except Exception as e:
                        logger.warning(f"清理Redis记录失败: {e}")
                
                logger.info(f"成功恢复 {updated_count} 个被中断的深度分析任务")
                
                return {
                    'success': True,
                    'recovered_count': updated_count,
                    'interrupted_papers': [
                        {
                            'arxiv_id': row['arxiv_id'],
                            'title': row['title'],
                            'created_at': row['deep_analysis_created_at'],
                            'updated_at': row['deep_analysis_updated_at']
                        }
                        for row in interrupted_papers
                    ]
                }
                
        except Exception as e:
            logger.error(f"恢复中断的深度分析任务失败: {e}")
            return {
                'success': False,
                'error': str(e),
                'recovered_count': 0,
                'interrupted_papers': []
            }
    
    def reset_stuck_analysis(self, max_hours: int = 2) -> Dict[str, Any]:
        """
        重置卡住的深度分析任务
        将超过指定时间仍在processing状态的任务标记为失败
        
        Args:
            max_hours: 最大允许运行时间（小时）
            
        Returns:
            Dict: 重置操作的结果统计
        """
        try:
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                
                # 查找超时的处理中任务
                cursor.execute("""
                    SELECT arxiv_id, title, deep_analysis_created_at, deep_analysis_updated_at,
                           EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - deep_analysis_updated_at))/3600 as hours_stuck
                    FROM arxiv_papers 
                    WHERE deep_analysis_status = 'processing' 
                    AND deep_analysis_updated_at < CURRENT_TIMESTAMP - INTERVAL '%s hours'
                """, (max_hours,))
                
                stuck_papers = cursor.fetchall()
                
                if not stuck_papers:
                    logger.info(f"没有发现超过 {max_hours} 小时的卡住任务")
                    return {
                        'success': True,
                        'reset_count': 0,
                        'stuck_papers': []
                    }
                
                logger.warning(f"发现 {len(stuck_papers)} 个超过 {max_hours} 小时的卡住任务")
                
                # 将卡住的任务标记为失败
                cursor.execute("""
                    UPDATE arxiv_papers 
                    SET deep_analysis_status = 'failed',
                        deep_analysis_updated_at = CURRENT_TIMESTAMP
                    WHERE deep_analysis_status = 'processing' 
                    AND deep_analysis_updated_at < CURRENT_TIMESTAMP - INTERVAL '%s hours'
                """, (max_hours,))
                
                reset_count = cursor.rowcount
                conn.commit()
                
                logger.info(f"成功重置 {reset_count} 个卡住的深度分析任务")
                
                return {
                    'success': True,
                    'reset_count': reset_count,
                    'stuck_papers': [
                        {
                            'arxiv_id': row['arxiv_id'],
                            'title': row['title'],
                            'created_at': row['deep_analysis_created_at'],
                            'updated_at': row['deep_analysis_updated_at'],
                            'hours_stuck': float(row['hours_stuck'])
                        }
                        for row in stuck_papers
                    ]
                }
                
        except Exception as e:
            logger.error(f"重置卡住的深度分析任务失败: {e}")
            return {
                'success': False,
                'error': str(e),
                'reset_count': 0,
                'stuck_papers': []
            }
    
    def batch_reset_analysis_status(self, arxiv_ids: List[str], status: str = 'pending') -> Dict[str, Any]:
        """
        批量重置深度分析状态
        
        Args:
            arxiv_ids: 要重置的论文ID列表
            status: 目标状态 ('pending', 'failed', 'cancelled')
            
        Returns:
            Dict: 批量重置操作的结果
        """
        if not arxiv_ids:
            return {
                'success': False,
                'error': '论文ID列表为空'
            }
        
        valid_statuses = ['pending', 'failed', 'cancelled']
        if status not in valid_statuses:
            return {
                'success': False,
                'error': f'无效状态: {status}，允许的状态: {valid_statuses}'
            }
        
        try:
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor()
                
                # 批量更新状态
                placeholders = ','.join(['%s'] * len(arxiv_ids))
                cursor.execute(f"""
                    UPDATE arxiv_papers 
                    SET deep_analysis_status = %s,
                        deep_analysis_updated_at = CURRENT_TIMESTAMP
                    WHERE arxiv_id IN ({placeholders})
                """, [status] + arxiv_ids)
                
                updated_count = cursor.rowcount
                conn.commit()
                
                # 清理相关的Redis记录
                redis_client = self.db_manager.get_redis_client()
                if redis_client:
                    try:
                        for arxiv_id in arxiv_ids:
                            process_key = f"deep_analysis:process:{arxiv_id}"
                            redis_client.delete(process_key)
                    except Exception as e:
                        logger.warning(f"清理Redis记录失败: {e}")
                
                logger.info(f"批量重置 {updated_count} 个论文的分析状态为: {status}")
                
                return {
                    'success': True,
                    'updated_count': updated_count,
                    'status': status,
                    'arxiv_ids': arxiv_ids
                }
                
        except Exception as e:
            logger.error(f"批量重置分析状态失败: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_analysis_statistics(self) -> Dict[str, Any]:
        """
        获取深度分析统计信息
        
        Returns:
            Dict: 包含各种状态的论文数量统计
        """
        try:
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                
                # 获取深度分析状态统计
                cursor.execute("""
                    SELECT 
                        deep_analysis_status,
                        COUNT(*) as count
                    FROM arxiv_papers 
                    WHERE deep_analysis_status IS NOT NULL
                    GROUP BY deep_analysis_status
                """)
                
                status_counts = {row['deep_analysis_status']: row['count'] for row in cursor.fetchall()}
                
                # 获取总体统计
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_papers,
                        COUNT(CASE WHEN deep_analysis_status IS NOT NULL THEN 1 END) as papers_with_status,
                        COUNT(CASE WHEN deep_analysis_result IS NOT NULL THEN 1 END) as papers_with_result
                    FROM arxiv_papers
                """)
                
                total_stats = dict(cursor.fetchone())
                
                return {
                    'success': True,
                    'total_papers': total_stats['total_papers'],
                    'papers_with_status': total_stats['papers_with_status'],
                    'papers_with_result': total_stats['papers_with_result'],
                    'status_breakdown': {
                        'completed': status_counts.get('completed', 0),
                        'processing': status_counts.get('processing', 0),
                        'failed': status_counts.get('failed', 0),
                        'pending': status_counts.get('pending', 0),
                        'cancelled': status_counts.get('cancelled', 0)
                    }
                }
                
        except Exception as e:
            logger.error(f"获取深度分析统计失败: {e}")
            return {
                'success': False,
                'error': str(e)
            }


class DifyService:
    """Dify 知识库服务"""
    
    def __init__(self):
        self.db_manager = DatabaseManager()
        self.dify_client = None
        self._init_dify_client()
    
    def _init_dify_client(self):
        """初始化 Dify 客户端"""
        try:
            # 从环境变量创建配置
            config = DifyKnowledgeBaseConfig.from_environment()
            config.validate()
            self.dify_client = DifyKnowledgeBaseClient(config)
            logger.info("Dify 客户端初始化成功")
        except Exception as e:
            logger.error(f"Dify 客户端初始化失败: {e}")
            self.dify_client = None
    
    def is_available(self) -> bool:
        """检查 Dify 服务是否可用"""
        if not self.dify_client:
            logger.error("Dify 客户端未初始化，请检查环境变量配置")
            return False
        
        try:
            # 尝试调用 health_check 或简单的 API 调用来验证连接
            health_status = self.dify_client.health_check()
            if not health_status:
                logger.error("Dify 服务健康检查失败，请检查服务状态和网络连接")
            return health_status
        except Exception as e:
            logger.error(f"Dify 服务连接测试失败: {e}")
            return False
    
    def get_or_create_dataset(self, task_name: str) -> Optional[str]:
        """获取或创建以 task_name 命名的知识库"""
        if not self.dify_client:
            logger.error("Dify 客户端未初始化")
            return None
        
        try:
            logger.info(f"正在查找或创建知识库: {task_name}")
            
            # 查找现有知识库
            datasets = self.dify_client.list_datasets(limit=100)
            logger.info(f"找到 {len(datasets)} 个现有知识库")
            
            for dataset in datasets:
                logger.debug(f"检查知识库: {dataset.name} (ID: {dataset.dify_dataset_id})")
                if dataset.name == task_name:
                    logger.info(f"找到现有知识库: {task_name} (ID: {dataset.dify_dataset_id})")
                    return dataset.dify_dataset_id
            
            # 创建新知识库
            logger.info(f"创建新知识库: {task_name}")
            dataset = self.dify_client.create_dataset(
                name=task_name,
                description=f"论文知识库 - {task_name}",
                permission="only_me"
            )
            logger.info(f"成功创建知识库: {task_name} (ID: {dataset.dify_dataset_id})")
            return dataset.dify_dataset_id
            
        except Exception as e:
            logger.error(f"获取或创建知识库失败: {e}")
            return None
    
    def validate_upload_preconditions(self, arxiv_id: str) -> Dict[str, Any]:
        """验证上传前置条件"""
        validation_result = {
            "success": True,
            "errors": [],
            "warnings": []
        }
        
        try:
            # 检查 Dify 客户端状态
            if not self.dify_client:
                validation_result["errors"].append("Dify 客户端未初始化")
                validation_result["success"] = False
                return validation_result
            
            # 检查 Dify 服务连接
            if not self.is_available():
                validation_result["errors"].append("无法连接到 Dify 服务，请检查网络连接和服务状态")
                validation_result["success"] = False
            
            # 从数据库获取论文信息并验证
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cursor.execute("""
                    SELECT arxiv_id, title, authors, abstract, categories, pdf_url, task_name,
                           dify_dataset_id, dify_document_id
                    FROM arxiv_papers 
                    WHERE arxiv_id = %s
                """, (arxiv_id,))
                
                paper = cursor.fetchone()
                if not paper:
                    validation_result["errors"].append("论文不存在")
                    validation_result["success"] = False
                    return validation_result
                
                paper_dict = dict(paper)
                
                # 检查论文是否已上传
                if paper_dict.get('dify_document_id'):
                    validation_result["errors"].append("论文已上传到 Dify")
                    validation_result["success"] = False
                
                # 检查任务名称
                task_name = paper_dict.get('task_name')
                if not task_name:
                    validation_result["errors"].append("论文未分配任务名称，无法确定目标知识库")
                    validation_result["success"] = False
                elif len(task_name.strip()) < 2:
                    validation_result["errors"].append("任务名称过短，无法创建有效的知识库")
                    validation_result["success"] = False
                
                # 检查论文基本信息完整性
                if not paper_dict.get('title'):
                    validation_result["errors"].append("论文标题缺失")
                    validation_result["success"] = False
                elif len(paper_dict['title'].strip()) < 10:
                    validation_result["warnings"].append("论文标题过短，可能影响上传质量")
                
                if not paper_dict.get('abstract'):
                    validation_result["warnings"].append("论文摘要缺失，可能影响知识库检索效果")
                elif len(paper_dict['abstract'].strip()) < 100:
                    validation_result["warnings"].append("论文摘要过短，可能影响知识库检索效果")
                
                if not paper_dict.get('authors'):
                    validation_result["warnings"].append("论文作者信息缺失")
                
                # 检查PDF下载可能性（简单验证）
                if paper_dict.get('pdf_url'):
                    if not paper_dict['pdf_url'].startswith('http'):
                        validation_result["warnings"].append("PDF链接格式异常，可能无法下载")
                else:
                    validation_result["warnings"].append("缺少PDF链接，系统将尝试从ArXiv下载")
                
                # 预估文档大小（基于摘要长度）
                abstract_length = len(paper_dict.get('abstract', ''))
                if abstract_length > 10000:
                    validation_result["warnings"].append("论文摘要过长，上传可能需要较长时间")
            
            # 检查知识库配置
            if validation_result["success"]:  # 只有在基本验证通过时才检查
                try:
                    # 测试知识库操作权限
                    datasets = self.dify_client.list_datasets(limit=1)
                    if datasets is None:
                        validation_result["warnings"].append("无法获取知识库列表，可能影响自动创建知识库")
                except Exception as e:
                    validation_result["warnings"].append(f"知识库权限检查失败: {str(e)}")
            
        except Exception as e:
            validation_result["errors"].append(f"验证过程中发生错误: {str(e)}")
            validation_result["success"] = False
        
        return validation_result
    
    def upload_paper_to_dify(self, arxiv_id: str) -> Dict[str, Any]:
        """上传论文到 Dify 知识库"""
        # 首先进行预上传验证
        validation = self.validate_upload_preconditions(arxiv_id)
        if not validation["success"]:
            return {
                "success": False, 
                "error": "; ".join(validation["errors"]),
                "validation_errors": validation["errors"],
                "validation_warnings": validation["warnings"]
            }
        
        # 如果有警告，记录到日志
        if validation["warnings"]:
            logger.warning(f"论文 {arxiv_id} 上传前警告: {'; '.join(validation['warnings'])}")
        
        if not self.dify_client:
            return {"success": False, "error": "Dify 客户端未初始化"}
        
        try:
            # 从数据库获取论文信息
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cursor.execute("""
                    SELECT arxiv_id, title, authors, abstract, categories, pdf_url, task_name,
                           dify_dataset_id, dify_document_id
                    FROM arxiv_papers 
                    WHERE arxiv_id = %s
                """, (arxiv_id,))
                
                paper = cursor.fetchone()
                if not paper:
                    return {"success": False, "error": "论文不存在"}
                
                paper_dict = dict(paper)
                task_name = paper_dict.get('task_name')
                if not task_name:
                    return {"success": False, "error": "论文未分配任务名称"}
                
                # 检查是否已上传
                if paper_dict.get('dify_document_id'):
                    return {"success": False, "error": "论文已上传到 Dify"}
            
            # 获取或创建知识库
            dataset_id = self.get_or_create_dataset(task_name)
            logger.info(f"获取到的知识库ID: {dataset_id}")
            
            if not dataset_id:
                return {"success": False, "error": "无法创建或获取知识库"}
            
            # 创建 ArxivData 对象并下载 PDF
            arxiv_data = ArxivData({
                'title': paper_dict['title'],
                'link': f"http://arxiv.org/abs/{arxiv_id}",
                'snippet': paper_dict['abstract'],
                'categories': paper_dict['categories'] or ''
            })
            
            try:
                # 下载 PDF
                logger.info(f"开始下载论文 PDF: {arxiv_id}")
                pdf_content = arxiv_data.downloadPdf()
                
                if not pdf_content:
                    return {"success": False, "error": "PDF 下载失败"}
                
                # 临时保存 PDF 文件，使用论文标题作为文件名
                import tempfile
                
                # 创建安全的文件名
                safe_title = sanitize_filename(paper_dict['title'], max_length=150)
                temp_filename = f"{arxiv_id}_{safe_title}.pdf"
                
                # 创建临时目录并使用自定义文件名
                temp_dir = tempfile.gettempdir()
                temp_pdf_path = os.path.join(temp_dir, temp_filename)
                
                # 写入PDF内容
                with open(temp_pdf_path, 'wb') as temp_file:
                    temp_file.write(pdf_content)
                
                try:
                    # 上传到 Dify (with retry for newly created datasets)
                    logger.info(f"开始上传论文到 Dify: {arxiv_id}, 使用知识库ID: {dataset_id}")
                    
                    # 对于新创建的知识库，可能需要等待一下才能上传
                    import time
                    for attempt in range(3):
                        try:
                            logger.info(f"第 {attempt + 1} 次尝试上传: dataset_id={dataset_id}, file_path={temp_pdf_path}")
                            document = self.dify_client.upload_document_file(
                                dataset_id=dataset_id,
                                file_path=temp_pdf_path,
                                name=f"{arxiv_id} - {paper_dict['title']}"
                            )
                            break  # 成功则退出重试循环
                        except Exception as upload_error:
                            logger.warning(f"第 {attempt + 1} 次上传尝试失败: {upload_error}")
                            if attempt < 2:  # 前两次失败后等待重试
                                time.sleep(2)  # 等待2秒
                            else:
                                raise  # 最后一次失败则抛出异常
                    
                    # 更新数据库记录
                    with self.db_manager.get_db_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("""
                            UPDATE arxiv_papers 
                            SET dify_dataset_id = %s,
                                dify_document_id = %s,
                                dify_upload_time = CURRENT_TIMESTAMP,
                                dify_document_name = %s,
                                dify_character_count = %s,
                                dify_segment_count = 0,
                                dify_metadata = %s,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE arxiv_id = %s
                        """, (
                            dataset_id,
                            document.dify_document_id,
                            document.name,
                            document.character_count or 0,
                            json.dumps({
                                "upload_source": "explore_paper_data",
                                "task_name": task_name,
                                "upload_method": "pdf_file"
                            }),
                            arxiv_id
                        ))
                        conn.commit()
                    
                    # 清除缓存
                    self.db_manager.set_cache(f"paper_detail_{arxiv_id}", None)
                    
                    return {
                        "success": True,
                        "dataset_id": dataset_id,
                        "document_id": document.dify_document_id,
                        "document_name": document.name
                    }
                
                finally:
                    # 清理临时文件
                    try:
                        os.unlink(temp_pdf_path)
                    except:
                        pass
                
            finally:
                # 清理 ArxivData 对象
                arxiv_data.cleanup()
                
        except Exception as e:
            logger.error(f"上传论文到 Dify 失败: {e}")
            # 如果是 Dify 知识库异常，提供详细的错误信息
            if hasattr(e, 'to_dict'):
                error_info = e.to_dict()
                return {
                    "success": False, 
                    "error": error_info["user_friendly_message"],
                    "error_details": error_info,
                    "is_retryable": error_info["is_retryable"],
                    "retry_delay": error_info["retry_delay"],
                    "suggested_actions": error_info["suggested_actions"]
                }
            else:
                return {"success": False, "error": str(e)}
    
    def batch_upload_papers_to_dify(self, arxiv_ids: List[str]) -> Dict[str, Any]:
        """批量上传论文到 Dify"""
        if not arxiv_ids:
            return {"success": False, "error": "没有提供论文ID"}
        
        results = {
            "success_count": 0,
            "failed_count": 0,
            "results": [],
            "errors": [],
            "error_summary": {
                "authentication": 0,
                "network": 0,
                "upload": 0,
                "processing": 0,
                "configuration": 0,
                "rate_limit": 0,
                "other": 0
            },
            "retryable_errors": [],
            "manual_intervention_required": []
        }
        
        for arxiv_id in arxiv_ids:
            try:
                result = self.upload_paper_to_dify(arxiv_id)
                if result["success"]:
                    results["success_count"] += 1
                    results["results"].append({
                        "arxiv_id": arxiv_id,
                        "status": "success",
                        "dataset_id": result.get("dataset_id"),
                        "document_id": result.get("document_id")
                    })
                else:
                    results["failed_count"] += 1
                    
                    # 获取错误详情和分类
                    error_info = {
                        "arxiv_id": arxiv_id,
                        "error": result["error"]
                    }
                    
                    # 如果有详细错误信息，添加更多上下文
                    if "error_details" in result:
                        error_details = result["error_details"]
                        error_category = error_details.get("category", "other")
                        
                        # 更新错误分类统计
                        results["error_summary"][error_category] += 1
                        
                        # 添加详细错误信息
                        error_info.update({
                            "category": error_category,
                            "is_retryable": result.get("is_retryable", False),
                            "retry_delay": result.get("retry_delay", 0),
                            "suggested_actions": result.get("suggested_actions", [])
                        })
                        
                        # 分类到可重试或需要手动处理
                        if result.get("is_retryable", False):
                            results["retryable_errors"].append(error_info)
                        else:
                            results["manual_intervention_required"].append(error_info)
                    else:
                        # 没有详细错误信息的情况
                        results["error_summary"]["other"] += 1
                        results["manual_intervention_required"].append(error_info)
                    
                    results["errors"].append(error_info)
                    
            except Exception as e:
                results["failed_count"] += 1
                results["error_summary"]["other"] += 1
                
                error_info = {
                    "arxiv_id": arxiv_id,
                    "error": str(e),
                    "category": "other",
                    "is_retryable": False
                }
                
                results["errors"].append(error_info)
                results["manual_intervention_required"].append(error_info)
        
        # 添加整体统计和建议
        total_papers = len(arxiv_ids)
        results["total_papers"] = total_papers
        results["success_rate"] = (results["success_count"] / total_papers * 100) if total_papers > 0 else 0
        
        # 生成批量操作建议
        results["recommendations"] = self._generate_batch_recommendations(results)
        
        return results
    
    def _generate_batch_recommendations(self, results: Dict[str, Any]) -> List[str]:
        """生成批量操作建议"""
        recommendations = []
        
        error_summary = results["error_summary"]
        retryable_count = len(results["retryable_errors"])
        manual_count = len(results["manual_intervention_required"])
        
        if retryable_count > 0:
            recommendations.append(f"有 {retryable_count} 个错误可以重试，建议稍后批量重试")
        
        if manual_count > 0:
            recommendations.append(f"有 {manual_count} 个错误需要手动处理")
        
        if error_summary["authentication"] > 0:
            recommendations.append("检查 API 密钥配置")
        
        if error_summary["network"] > 0:
            recommendations.append("检查网络连接和 Dify 服务可用性")
        
        if error_summary["rate_limit"] > 0:
            recommendations.append("降低并发上传数量或增加延迟")
        
        if error_summary["configuration"] > 0:
            recommendations.append("检查知识库配置和权限设置")
        
        if results["success_rate"] < 50:
            recommendations.append("成功率较低，建议检查系统配置后再次尝试")
        
        return recommendations
    
    def remove_paper_from_dify(self, arxiv_id: str) -> Dict[str, Any]:
        """从 Dify 知识库移除论文"""
        if not self.dify_client:
            return {"success": False, "error": "Dify 客户端未初始化"}
        
        try:
            # 获取论文的 Dify 信息
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cursor.execute("""
                    SELECT dify_dataset_id, dify_document_id
                    FROM arxiv_papers 
                    WHERE arxiv_id = %s
                """, (arxiv_id,))
                
                paper = cursor.fetchone()
                if not paper:
                    return {"success": False, "error": "论文不存在"}
                
                dataset_id = paper['dify_dataset_id']
                document_id = paper['dify_document_id']
                
                if not dataset_id or not document_id:
                    return {"success": False, "error": "论文未上传到 Dify"}
            
            # 从 Dify 删除文档
            success = self.dify_client.delete_document(dataset_id, document_id)
            
            if success:
                # 更新数据库记录
                with self.db_manager.get_db_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE arxiv_papers 
                        SET dify_dataset_id = NULL,
                            dify_document_id = NULL,
                            dify_upload_time = NULL,
                            dify_document_name = NULL,
                            dify_character_count = NULL,
                            dify_segment_count = NULL,
                            dify_metadata = NULL,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE arxiv_id = %s
                    """, (arxiv_id,))
                    conn.commit()
                
                # 清除缓存
                self.db_manager.set_cache(f"paper_detail_{arxiv_id}", None)
                
                return {"success": True}
            else:
                return {"success": False, "error": "从 Dify 删除文档失败"}
                
        except Exception as e:
            logger.error(f"从 Dify 移除论文失败: {e}")
            return {"success": False, "error": str(e)}
    
    def get_dify_upload_status(self, arxiv_id: str) -> Dict[str, Any]:
        """获取论文的 Dify 上传状态"""
        try:
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cursor.execute("""
                    SELECT dify_dataset_id, dify_document_id, dify_upload_time,
                           dify_document_name, dify_character_count, dify_segment_count,
                           task_name
                    FROM arxiv_papers 
                    WHERE arxiv_id = %s
                """, (arxiv_id,))
                
                paper = cursor.fetchone()
                if not paper:
                    return {"success": False, "error": "论文不存在"}
                
                paper_dict = dict(paper)
                is_uploaded = bool(paper_dict.get('dify_document_id'))
                
                return {
                    "success": True,
                    "is_uploaded": is_uploaded,
                    "dataset_id": paper_dict.get('dify_dataset_id'),
                    "document_id": paper_dict.get('dify_document_id'),
                    "upload_time": paper_dict.get('dify_upload_time'),
                    "document_name": paper_dict.get('dify_document_name'),
                    "character_count": paper_dict.get('dify_character_count'),
                    "segment_count": paper_dict.get('dify_segment_count'),
                    "task_name": paper_dict.get('task_name')
                }
                
        except Exception as e:
            logger.error(f"获取 Dify 上传状态失败: {e}")
            return {"success": False, "error": str(e)}
    
    def verify_dify_document(self, arxiv_id: str) -> Dict[str, Any]:
        """
        验证论文是否真正上传到 Dify 服务器
        
        Args:
            arxiv_id: ArXiv ID
            
        Returns:
            验证结果字典
        """
        try:
            # 首先获取本地数据库中的记录
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cursor.execute("""
                    SELECT dify_dataset_id, dify_document_id, dify_document_name,
                           title, dify_upload_time
                    FROM arxiv_papers 
                    WHERE arxiv_id = %s
                """, (arxiv_id,))
                
                paper = cursor.fetchone()
                if not paper:
                    return {"success": False, "error": "论文不存在"}
                
                paper_dict = dict(paper)
                dataset_id = paper_dict.get('dify_dataset_id')
                document_id = paper_dict.get('dify_document_id')
                
                if not dataset_id or not document_id:
                    return {
                        "success": True,
                        "verified": False,
                        "status": "not_uploaded",
                        "message": "论文尚未上传到 Dify"
                    }
                
                # 尝试从 Dify 服务器获取文档信息
                try:
                    config = DifyKnowledgeBaseConfig.from_environment()
                    dify_client = DifyKnowledgeBaseClient(config)
                    dify_document = dify_client.get_document(dataset_id, document_id)
                    
                    # 验证成功，文档存在于 Dify 服务器
                    return {
                        "success": True,
                        "verified": True,
                        "status": "verified",
                        "message": "文档已成功验证存在于 Dify 服务器",
                        "document_info": {
                            "dify_name": dify_document.name,
                            "local_name": paper_dict.get('dify_document_name'),
                            "character_count": dify_document.character_count,
                            "status": dify_document.status,
                            "indexing_status": dify_document.indexing_status
                        }
                    }
                    
                except Exception as dify_error:
                    # Dify API 调用失败，可能文档不存在或服务器问题
                    error_message = str(dify_error)
                    if "404" in error_message or "not found" in error_message.lower():
                        # 文档不存在，需要清理本地记录
                        return {
                            "success": True,
                            "verified": False,
                            "status": "missing",
                            "message": "文档在 Dify 服务器上不存在，可能已被删除",
                            "suggestion": "建议重新上传或清理本地记录"
                        }
                    else:
                        # 其他错误，无法确定状态
                        return {
                            "success": False,
                            "verified": False,
                            "status": "error",
                            "error": f"验证过程中出现错误: {error_message}",
                            "message": "无法连接到 Dify 服务器进行验证"
                        }
                
        except Exception as e:
            logger.error(f"验证 Dify 文档失败 [{arxiv_id}]: {e}")
            return {"success": False, "error": str(e)}
    
    def clean_missing_dify_record(self, arxiv_id: str) -> Dict[str, Any]:
        """
        清理本地数据库中已在 Dify 服务器丢失的文档记录
        
        Args:
            arxiv_id: ArXiv ID
            
        Returns:
            清理结果
        """
        try:
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE arxiv_papers 
                    SET dify_dataset_id = NULL,
                        dify_document_id = NULL,
                        dify_upload_time = NULL,
                        dify_document_name = NULL,
                        dify_character_count = NULL,
                        dify_segment_count = NULL,
                        dify_metadata = NULL,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE arxiv_id = %s
                """, (arxiv_id,))
                conn.commit()
                
                # 清除缓存
                self.db_manager.set_cache(f"paper_detail_{arxiv_id}", None)
                
                return {
                    "success": True,
                    "message": "已清理本地 Dify 记录，论文状态重置为未上传"
                }
                
        except Exception as e:
            logger.error(f"清理 Dify 记录失败 [{arxiv_id}]: {e}")
            return {"success": False, "error": str(e)}
    
    def get_dify_statistics(self) -> Dict[str, Any]:
        """获取 Dify 相关统计信息"""
        cache_key = "dify_statistics"
        cached_data = self.db_manager.get_cache(cache_key)
        if cached_data:
            return cached_data
        
        try:
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                
                # 基础统计
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_papers,
                        COUNT(CASE WHEN dify_document_id IS NOT NULL THEN 1 END) as uploaded_papers,
                        COUNT(CASE WHEN dify_document_id IS NULL THEN 1 END) as not_uploaded_papers,
                        COUNT(DISTINCT dify_dataset_id) as unique_datasets,
                        SUM(dify_character_count) as total_characters,
                        AVG(dify_character_count) as avg_characters
                    FROM arxiv_papers
                """)
                basic_stats = dict(cursor.fetchone())
                
                # 按任务统计
                cursor.execute("""
                    SELECT 
                        task_name,
                        COUNT(*) as total_papers,
                        COUNT(CASE WHEN dify_document_id IS NOT NULL THEN 1 END) as uploaded_papers,
                        SUM(dify_character_count) as total_characters
                    FROM arxiv_papers 
                    WHERE task_name IS NOT NULL AND task_name != ''
                    GROUP BY task_name
                    ORDER BY uploaded_papers DESC, total_papers DESC
                    LIMIT 20
                """)
                task_stats = [dict(row) for row in cursor.fetchall()]
                
                # 最近上传趋势
                cursor.execute("""
                    SELECT 
                        dify_upload_time::date as upload_date,
                        COUNT(*) as upload_count
                    FROM arxiv_papers 
                    WHERE dify_upload_time IS NOT NULL 
                      AND dify_upload_time >= NOW() - INTERVAL '30 days'
                    GROUP BY dify_upload_time::date
                    ORDER BY upload_date DESC
                """)
                upload_trend = [dict(row) for row in cursor.fetchall()]
                
                stats = {
                    "basic": basic_stats,
                    "by_task": task_stats,
                    "upload_trend": upload_trend
                }
                
                # 缓存结果
                self.db_manager.set_cache(cache_key, stats, timeout=900)
                return stats
                
        except Exception as e:
            logger.error(f"获取 Dify 统计信息失败: {e}")
            return {
                "basic": {},
                "by_task": [],
                "upload_trend": []
            }
    
    def batch_verify_all_documents(self) -> Dict[str, Any]:
        """
        批量验证所有已上传文档的状态
        
        Returns:
            验证结果统计
        """
        try:
            # 获取所有已上传的论文
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cursor.execute("""
                    SELECT arxiv_id, title, dify_document_id, dify_dataset_id
                    FROM arxiv_papers 
                    WHERE dify_document_id IS NOT NULL 
                      AND dify_document_id != ''
                    ORDER BY dify_upload_time DESC
                """)
                
                papers_to_verify = [dict(row) for row in cursor.fetchall()]
            
            if not papers_to_verify:
                return {
                    "success": True,
                    "total": 0,
                    "verified": 0,
                    "failed": 0,
                    "missing": 0,
                    "progress": 100,
                    "message": "没有需要验证的论文",
                    "failed_papers": [],
                    "missing_papers": []
                }
            
            total = len(papers_to_verify)
            verified_count = 0
            failed_count = 0
            missing_count = 0
            failed_papers = []
            missing_papers = []
            
            logger.info(f"开始批量验证 {total} 篇论文的 Dify 文档状态")
            
            # 逐个验证每篇论文
            for i, paper in enumerate(papers_to_verify):
                arxiv_id = paper['arxiv_id']
                title = paper['title']
                
                try:
                    # 调用单篇验证方法
                    verify_result = self.verify_dify_document(arxiv_id)
                    
                    if verify_result.get('success'):
                        if verify_result.get('verified'):
                            verified_count += 1
                            logger.debug(f"验证成功: {arxiv_id}")
                        elif verify_result.get('status') == 'missing':
                            missing_count += 1
                            missing_papers.append({
                                'arxiv_id': arxiv_id,
                                'title': title,
                                'error': '文档在 Dify 服务器上不存在'
                            })
                            logger.warning(f"文档丢失: {arxiv_id}")
                        else:
                            failed_count += 1
                            failed_papers.append({
                                'arxiv_id': arxiv_id,
                                'title': title,
                                'error': verify_result.get('error', '验证失败')
                            })
                            logger.warning(f"验证失败: {arxiv_id} - {verify_result.get('error')}")
                    else:
                        failed_count += 1
                        failed_papers.append({
                            'arxiv_id': arxiv_id,
                            'title': title,
                            'error': verify_result.get('error', '验证过程出错')
                        })
                        logger.error(f"验证出错: {arxiv_id} - {verify_result.get('error')}")
                        
                except Exception as e:
                    failed_count += 1
                    error_msg = str(e)
                    failed_papers.append({
                        'arxiv_id': arxiv_id,
                        'title': title,
                        'error': f'验证异常: {error_msg}'
                    })
                    logger.error(f"验证异常: {arxiv_id} - {error_msg}")
                
                # 可以在这里添加进度回调或日志
                progress = int((i + 1) / total * 100)
                if (i + 1) % 10 == 0 or i == total - 1:
                    logger.info(f"验证进度: {i + 1}/{total} ({progress}%)")
            
            # 汇总结果
            result = {
                "success": True,
                "total": total,
                "verified": verified_count,
                "failed": failed_count,
                "missing": missing_count,
                "progress": 100,
                "message": f"批量验证完成：{verified_count} 个成功，{failed_count} 个失败，{missing_count} 个丢失",
                "failed_papers": failed_papers,
                "missing_papers": missing_papers
            }
            
            logger.info(f"批量验证完成: {result['message']}")
            return result
            
        except Exception as e:
            logger.error(f"批量验证文档失败: {e}")
            return {
                "success": False,
                "total": 0,
                "verified": 0,
                "failed": 0,
                "missing": 0,
                "progress": 0,
                "error": str(e),
                "message": f"批量验证过程中发生错误: {e}",
                "failed_papers": [],
                "missing_papers": []
            }
    
    def get_eligible_papers_for_upload(self, filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        获取符合上传条件的论文列表
        
        Args:
            filters: 过滤条件
                - task_name: 指定任务名称
                - category: 指定分类
                - exclude_already_uploaded: 排除已上传的论文 (默认True)
                - require_task_name: 要求有任务名称 (默认True)
                - max_papers: 最大论文数量
        
        Returns:
            符合条件的论文列表
        """
        if filters is None:
            filters = {}
        
        try:
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                
                # 构建基础查询
                base_query = """
                    SELECT arxiv_id, title, authors, abstract, categories, pdf_url, task_name,
                           dify_dataset_id, dify_document_id, created_at, published_date
                    FROM arxiv_papers 
                    WHERE 1=1
                """
                
                query_params = []
                
                # 应用过滤条件
                if filters.get('exclude_already_uploaded', True):
                    base_query += " AND (dify_document_id IS NULL OR dify_document_id = '')"
                
                if filters.get('require_task_name', True):
                    base_query += " AND task_name IS NOT NULL AND task_name != ''"
                
                if filters.get('task_name'):
                    base_query += " AND task_name = %s"
                    query_params.append(filters['task_name'])
                
                if filters.get('category'):
                    base_query += " AND categories LIKE %s"
                    query_params.append(f"%{filters['category']}%")
                
                # 排序和限制
                base_query += " ORDER BY created_at DESC"
                
                if filters.get('max_papers'):
                    base_query += " LIMIT %s"
                    query_params.append(filters['max_papers'])
                
                cursor.execute(base_query, query_params)
                papers = cursor.fetchall()
                
                # 转换为字典列表
                return [dict(paper) for paper in papers]
                
        except Exception as e:
            logger.error(f"获取符合条件的论文失败: {e}")
            return []
    
    def upload_all_eligible_papers_with_summary(self, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        上传所有符合条件的论文并生成详细总结
        
        Args:
            filters: 过滤条件
        
        Returns:
            包含详细统计和失败信息的结果字典
        """
        if not self.dify_client:
            return {
                "success": False,
                "error": "Dify 客户端未初始化",
                "total_eligible": 0,
                "total_attempted": 0,
                "success_count": 0,
                "failed_count": 0,
                "skipped_count": 0,
                "progress": 0,
                "successful_papers": [],
                "failed_papers": [],
                "skipped_papers": [],
                "failure_summary": {},
                "suggestions": []
            }
        
        try:
            # 获取符合条件的论文
            eligible_papers = self.get_eligible_papers_for_upload(filters)
            total_eligible = len(eligible_papers)
            
            if total_eligible == 0:
                return {
                    "success": True,
                    "total_eligible": 0,
                    "total_attempted": 0,
                    "success_count": 0,
                    "failed_count": 0,
                    "skipped_count": 0,
                    "progress": 100,
                    "message": "没有找到符合条件的论文",
                    "successful_papers": [],
                    "failed_papers": [],
                    "skipped_papers": [],
                    "failure_summary": {},
                    "suggestions": []
                }
            
            # 初始化结果统计
            successful_papers = []
            failed_papers = []
            skipped_papers = []
            failure_summary = {}
            
            logger.info(f"开始批量上传 {total_eligible} 篇符合条件的论文")
            
            # 批量上传
            for i, paper in enumerate(eligible_papers):
                arxiv_id = paper['arxiv_id']
                title = paper.get('title', 'Unknown Title')
                
                try:
                    # 上传单个论文
                    upload_result = self.upload_paper_to_dify(arxiv_id)
                    
                    if upload_result['success']:
                        successful_papers.append({
                            'arxiv_id': arxiv_id,
                            'title': title,
                            'task_name': paper.get('task_name'),
                            'dataset_id': upload_result.get('dataset_id'),
                            'document_id': upload_result.get('document_id')
                        })
                        logger.info(f"上传成功: {arxiv_id} - {title}")
                    else:
                        error = upload_result.get('error', '未知错误')
                        failed_papers.append({
                            'arxiv_id': arxiv_id,
                            'title': title,
                            'task_name': paper.get('task_name'),
                            'error': error,
                            'error_type': self._classify_error_type(error)
                        })
                        
                        # 统计失败原因
                        error_type = self._classify_error_type(error)
                        failure_summary[error_type] = failure_summary.get(error_type, 0) + 1
                        
                        logger.warning(f"上传失败: {arxiv_id} - {error}")
                
                except Exception as e:
                    error_msg = str(e)
                    failed_papers.append({
                        'arxiv_id': arxiv_id,
                        'title': title,
                        'task_name': paper.get('task_name'),
                        'error': f'上传异常: {error_msg}',
                        'error_type': 'system_error'
                    })
                    
                    failure_summary['system_error'] = failure_summary.get('system_error', 0) + 1
                    logger.error(f"上传异常: {arxiv_id} - {error_msg}")
                
                # 可以在这里添加进度回调
                progress = int((i + 1) / total_eligible * 100)
                if (i + 1) % 5 == 0 or i == total_eligible - 1:
                    logger.info(f"上传进度: {i + 1}/{total_eligible} ({progress}%)")
            
            # 生成建议
            suggestions = self._generate_upload_suggestions(failed_papers, failure_summary)
            
            # 汇总结果
            result = {
                "success": True,
                "total_eligible": total_eligible,
                "total_attempted": total_eligible,
                "success_count": len(successful_papers),
                "failed_count": len(failed_papers),
                "skipped_count": len(skipped_papers),
                "progress": 100,
                "message": f"批量上传完成：成功 {len(successful_papers)} 篇，失败 {len(failed_papers)} 篇",
                "successful_papers": successful_papers,
                "failed_papers": failed_papers,
                "skipped_papers": skipped_papers,
                "failure_summary": failure_summary,
                "suggestions": suggestions
            }
            
            logger.info(f"批量上传完成: {result['message']}")
            return result
            
        except Exception as e:
            logger.error(f"批量上传失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "total_eligible": 0,
                "total_attempted": 0,
                "success_count": 0,
                "failed_count": 0,
                "skipped_count": 0,
                "progress": 0,
                "message": f"批量上传过程中发生错误: {e}",
                "successful_papers": [],
                "failed_papers": [],
                "skipped_papers": [],
                "failure_summary": {},
                "suggestions": []
            }
    
    def _classify_error_type(self, error: str) -> str:
        """分类错误类型"""
        error_lower = error.lower()
        
        if '任务名称' in error or 'task_name' in error_lower:
            return 'missing_task_name'
        elif '已上传' in error or 'already uploaded' in error_lower:
            return 'already_uploaded'
        elif 'pdf' in error_lower or '下载' in error:
            return 'pdf_download_error'
        elif '连接' in error or 'connection' in error_lower or 'network' in error_lower:
            return 'network_error'
        elif '服务' in error or 'service' in error_lower:
            return 'service_error'
        elif '权限' in error or 'permission' in error_lower or 'unauthorized' in error_lower:
            return 'permission_error'
        elif '知识库' in error or 'dataset' in error_lower:
            return 'dataset_error'
        else:
            return 'other_error'
    
    def _generate_upload_suggestions(self, failed_papers: List[Dict], failure_summary: Dict) -> List[Dict]:
        """生成上传建议"""
        suggestions = []
        
        # 分析失败原因并生成对应建议
        if failure_summary.get('missing_task_name', 0) > 0:
            suggestions.append({
                'type': 'missing_task_name',
                'count': failure_summary['missing_task_name'],
                'title': '缺少任务名称',
                'description': f'有 {failure_summary["missing_task_name"]} 篇论文缺少任务名称',
                'action': '为这些论文分配任务名称后重新上传',
                'severity': 'warning'
            })
        
        if failure_summary.get('pdf_download_error', 0) > 0:
            suggestions.append({
                'type': 'pdf_download_error',
                'count': failure_summary['pdf_download_error'],
                'title': 'PDF下载失败',
                'description': f'有 {failure_summary["pdf_download_error"]} 篇论文的PDF下载失败',
                'action': '检查网络连接或手动下载PDF文件',
                'severity': 'error'
            })
        
        if failure_summary.get('network_error', 0) > 0:
            suggestions.append({
                'type': 'network_error',
                'count': failure_summary['network_error'],
                'title': '网络连接问题',
                'description': f'有 {failure_summary["network_error"]} 篇论文因网络问题上传失败',
                'action': '检查网络连接后重试上传',
                'severity': 'error'
            })
        
        if failure_summary.get('already_uploaded', 0) > 0:
            suggestions.append({
                'type': 'already_uploaded',
                'count': failure_summary['already_uploaded'],
                'title': '论文已上传',
                'description': f'有 {failure_summary["already_uploaded"]} 篇论文已经上传过',
                'action': '这些论文可以跳过或通过验证功能检查状态',
                'severity': 'info'
            })
        
        return suggestions
    
    def generate_failed_papers_download(self, failed_papers: List[Dict], download_type: str = 'links') -> Dict[str, Any]:
        """
        为失败的论文生成下载链接或压缩包
        
        Args:
            failed_papers: 失败的论文列表
            download_type: 下载类型 ('links', 'csv', 'zip')
        
        Returns:
            下载数据字典
        """
        try:
            if not failed_papers:
                return {
                    "success": False,
                    "error": "没有失败的论文数据"
                }
            
            download_links = []
            
            # 为每篇失败论文生成下载信息
            for paper in failed_papers:
                arxiv_id = paper.get('arxiv_id', '')
                title = paper.get('title', 'Unknown Title')
                error = paper.get('error', 'Unknown Error')
                
                if arxiv_id:
                    download_links.append({
                        'arxiv_id': arxiv_id,
                        'title': title,
                        'error': error,
                        'pdf_url': f"https://arxiv.org/pdf/{arxiv_id}.pdf",
                        'abs_url': f"https://arxiv.org/abs/{arxiv_id}",
                        'download_filename': sanitize_filename(f"{arxiv_id}_{title}.pdf")
                    })
            
            if download_type == 'links':
                # 返回链接列表
                return {
                    "success": True,
                    "download_type": "links",
                    "count": len(download_links),
                    "links": download_links
                }
            
            elif download_type == 'csv':
                # 生成CSV内容
                import csv
                import io
                
                output = io.StringIO()
                writer = csv.writer(output)
                
                # 写入标题行
                writer.writerow(['ArXiv ID', 'Title', 'Error', 'PDF URL', 'Abstract URL'])
                
                # 写入数据行
                for link in download_links:
                    writer.writerow([
                        link['arxiv_id'],
                        link['title'],
                        link['error'],
                        link['pdf_url'],
                        link['abs_url']
                    ])
                
                csv_content = output.getvalue()
                output.close()
                
                return {
                    "success": True,
                    "download_type": "csv",
                    "count": len(download_links),
                    "csv_content": csv_content,
                    "filename": f"failed_papers_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                }
            
            elif download_type == 'zip':
                # 生成包含CSV和说明的压缩包信息
                import csv
                import io
                
                # 生成CSV内容
                csv_output = io.StringIO()
                writer = csv.writer(csv_output)
                writer.writerow(['ArXiv ID', 'Title', 'Error', 'PDF URL', 'Abstract URL', 'Suggested Filename'])
                
                for link in download_links:
                    writer.writerow([
                        link['arxiv_id'],
                        link['title'],
                        link['error'],
                        link['pdf_url'],
                        link['abs_url'],
                        link['download_filename']
                    ])
                
                csv_content = csv_output.getvalue()
                csv_output.close()
                
                # 生成说明文件
                readme_content = f"""# 失败论文下载说明

## 统计信息
- 失败论文总数: {len(download_links)}
- 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 使用方法
1. 打开 failed_papers.csv 文件查看所有失败论文的详细信息
2. 点击 PDF URL 列中的链接直接下载对应论文的PDF文件
3. 建议的文件名在 Suggested Filename 列中提供

## 批量下载建议
您可以使用下载管理器或脚本工具批量下载所有PDF文件。

## 错误类型说明
请查看 Error 列了解每篇论文的具体失败原因，并根据错误类型采取相应的解决措施。
"""
                
                return {
                    "success": True,
                    "download_type": "zip",
                    "count": len(download_links),
                    "files": {
                        "failed_papers.csv": csv_content,
                        "README.md": readme_content
                    },
                    "filename": f"failed_papers_download_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
                }
            
            else:
                return {
                    "success": False,
                    "error": f"不支持的下载类型: {download_type}"
                }
                
        except Exception as e:
            logger.error(f"生成失败论文下载失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
