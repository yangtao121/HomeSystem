"""
数据库操作模块 - 论文数据访问
"""
import psycopg2
import psycopg2.extras
import redis
import json
from typing import Dict, List, Any, Optional, Tuple
from config import DATABASE_CONFIG, REDIS_CONFIG
import logging

logger = logging.getLogger(__name__)

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
                    return json.loads(cached_data)
            except Exception as e:
                logger.warning(f"缓存读取失败: {e}")
        return None
    
    def set_cache(self, key: str, data: Any, timeout: int = 300):
        """设置缓存数据"""
        redis_client = self.get_redis_client()
        if redis_client:
            try:
                redis_client.setex(key, timeout, json.dumps(data, default=str))
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
                       created_at, research_objectives, keywords
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
            
            # 关键词分析
            cursor.execute("""
                SELECT keywords, COUNT(*) as frequency
                FROM arxiv_papers 
                WHERE keywords IS NOT NULL AND keywords != ''
                GROUP BY keywords
                ORDER BY frequency DESC
                LIMIT 50
            """)
            keyword_analysis = [dict(row) for row in cursor.fetchall()]
            
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