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
                     task_name: str = "", task_id: str = "", 
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
            
            if task_name:
                conditions.append("task_name ILIKE %s")
                params.append(f"%{task_name}%")
                
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
                       created_at, research_objectives, keywords, task_name, task_id,
                       full_paper_relevance_score, full_paper_relevance_justification,
                       dify_document_id
                FROM arxiv_papers 
                {where_clause}
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
            """
            cursor.execute(data_query, params + [per_page, offset])
            papers = [dict(row) for row in cursor.fetchall()]
            
            return papers, total
    
    def get_paper_detail(self, arxiv_id: str) -> Optional[Dict]:
        """获取论文详细信息"""
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
                       created_at, research_objectives, keywords, task_name, task_id,
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
        return self.dify_client is not None and self.dify_client.health_check()
    
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
    
    def upload_paper_to_dify(self, arxiv_id: str) -> Dict[str, Any]:
        """上传论文到 Dify 知识库"""
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
            return {"success": False, "error": str(e)}
    
    def batch_upload_papers_to_dify(self, arxiv_ids: List[str]) -> Dict[str, Any]:
        """批量上传论文到 Dify"""
        if not arxiv_ids:
            return {"success": False, "error": "没有提供论文ID"}
        
        results = {
            "success_count": 0,
            "failed_count": 0,
            "results": [],
            "errors": []
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
                    results["errors"].append({
                        "arxiv_id": arxiv_id,
                        "error": result["error"]
                    })
                    
            except Exception as e:
                results["failed_count"] += 1
                results["errors"].append({
                    "arxiv_id": arxiv_id,
                    "error": str(e)
                })
        
        return results
    
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
                    dify_client = DifyKnowledgeBaseClient.from_environment()
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