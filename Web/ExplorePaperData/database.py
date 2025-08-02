"""
数据库操作模块 - 论文数据访问
"""
import psycopg2
import psycopg2.extras
import redis
import json
import re
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from config import DATABASE_CONFIG, REDIS_CONFIG
import logging

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
                ORDER BY date DESC
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
                       full_paper_relevance_score, full_paper_relevance_justification
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
                       full_paper_relevance_score, full_paper_relevance_justification
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
                       full_paper_relevance_score, full_paper_relevance_justification
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