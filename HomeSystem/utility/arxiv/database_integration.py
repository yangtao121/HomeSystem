# ArXiv模块数据库集成
from typing import List, Optional, Callable, Any
from loguru import logger

from ...integrations.database.connection import get_database_manager
from ...integrations.database.operations import DatabaseOperations, CacheOperations
from ...integrations.database.models import ArxivPaperModel
from .arxiv import ArxivData, ArxivResult, ArxivTool


class ArxivDatabaseManager:
    """ArXiv数据库管理器，专门处理ArXiv论文的数据库操作"""
    
    def __init__(self):
        self.db_ops = DatabaseOperations()
        self.cache_ops = CacheOperations()
        self._init_database()
    
    def _init_database(self):
        """初始化数据库"""
        try:
            # 创建ArXiv论文表
            arxiv_model = ArxivPaperModel()
            success = self.db_ops.init_tables([arxiv_model])
            if success:
                logger.info("ArXiv数据库表初始化成功")
            else:
                logger.error("ArXiv数据库表初始化失败")
        except Exception as e:
            logger.error(f"ArXiv数据库初始化异常: {e}")
    
    def save_paper(self, arxiv_data: ArxivData) -> bool:
        """保存单篇论文到数据库"""
        try:
            # 转换为数据库模型
            paper_model = self._arxiv_data_to_model(arxiv_data)
            
            # 检查是否已存在
            existing = self.db_ops.get_by_field(ArxivPaperModel, 'arxiv_id', paper_model.arxiv_id)
            if existing:
                logger.debug(f"论文已存在: {paper_model.arxiv_id}")
                return False
            
            # 保存到数据库
            success = self.db_ops.create(paper_model)
            
            # 缓存到Redis
            if success:
                self.cache_ops.cache_model(paper_model, expire=3600)  # 1小时过期
                logger.debug(f"论文已保存: {paper_model.arxiv_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"保存论文失败: {e}")
            return False
    
    def batch_save_papers(self, arxiv_results: ArxivResult) -> int:
        """批量保存论文到数据库"""
        if not arxiv_results.results:
            return 0
        
        try:
            # 转换为数据库模型
            paper_models = []
            for arxiv_data in arxiv_results.results:
                # 检查是否已存在
                if not self.is_paper_exists(arxiv_data.arxiv_id):
                    paper_model = self._arxiv_data_to_model(arxiv_data)
                    paper_models.append(paper_model)
            
            if not paper_models:
                logger.info("所有论文均已存在，跳过批量保存")
                return 0
            
            # 批量保存
            count = self.db_ops.batch_create(paper_models)
            
            # 批量缓存
            for model in paper_models:
                self.cache_ops.cache_model(model, expire=3600)
            
            logger.info(f"批量保存论文完成: {count}/{len(paper_models)}")
            return count
            
        except Exception as e:
            logger.error(f"批量保存论文失败: {e}")
            return 0
    
    def get_paper_by_arxiv_id(self, arxiv_id: str) -> Optional[ArxivPaperModel]:
        """根据ArXiv ID获取论文"""
        try:
            # 先尝试从缓存获取
            cached_paper = self.cache_ops.get_cached_model(ArxivPaperModel, arxiv_id)
            if cached_paper and cached_paper.arxiv_id == arxiv_id:
                return cached_paper
            
            # 从数据库获取
            paper = self.db_ops.get_by_field(ArxivPaperModel, 'arxiv_id', arxiv_id)
            
            # 更新缓存
            if paper:
                self.cache_ops.cache_model(paper, expire=3600)
            
            return paper
            
        except Exception as e:
            logger.error(f"获取论文失败: {e}")
            return None
    
    def is_paper_exists(self, arxiv_id: str) -> bool:
        """检查论文是否已存在"""
        try:
            # 先检查缓存
            cache_key = f"exists:arxiv:{arxiv_id}"
            cached_exists = self.cache_ops.get(cache_key)
            if cached_exists is not None:
                return cached_exists == "1"
            
            # 检查数据库
            exists = self.db_ops.exists(ArxivPaperModel, 'arxiv_id', arxiv_id)
            
            # 缓存结果
            self.cache_ops.set(cache_key, "1" if exists else "0", expire=300)  # 5分钟过期
            
            return exists
            
        except Exception as e:
            logger.error(f"检查论文存在性失败: {e}")
            return False
    
    def is_processed(self, arxiv_id: str) -> bool:
        """检查论文是否已处理"""
        try:
            # 先检查缓存
            cache_key = f"processed:arxiv:{arxiv_id}"
            if self.cache_ops.sismember("processed_papers", arxiv_id):
                return True
            
            # 检查数据库
            paper = self.get_paper_by_arxiv_id(arxiv_id)
            if paper and paper.processing_status == 'completed':
                # 更新缓存
                self.cache_ops.sadd("processed_papers", arxiv_id)
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"检查论文处理状态失败: {e}")
            return False
    
    def mark_processed(self, arxiv_id: str, status: str = 'completed') -> bool:
        """标记论文为已处理"""
        try:
            paper = self.get_paper_by_arxiv_id(arxiv_id)
            if not paper:
                logger.warning(f"未找到论文: {arxiv_id}")
                return False
            
            # 更新数据库状态
            success = self.db_ops.update(paper, {'processing_status': status})
            
            # 更新缓存
            if success and status == 'completed':
                self.cache_ops.sadd("processed_papers", arxiv_id)
                # 使模型缓存失效
                self.cache_ops.invalidate_model_cache(paper)
            
            return success
            
        except Exception as e:
            logger.error(f"标记论文处理状态失败: {e}")
            return False
    
    def get_unprocessed_papers(self, limit: int = 10) -> List[ArxivPaperModel]:
        """获取未处理的论文"""
        try:
            with get_database_manager().get_postgres_sync() as cursor:
                cursor.execute("""
                    SELECT * FROM arxiv_papers 
                    WHERE processing_status = 'pending'
                    ORDER BY created_at ASC
                    LIMIT %s
                """, (limit,))
                
                results = cursor.fetchall()
                return [ArxivPaperModel.from_dict(dict(row)) for row in results]
                
        except Exception as e:
            logger.error(f"获取未处理论文失败: {e}")
            return []
    
    def get_papers_by_status(self, status: str, limit: int = 50) -> List[ArxivPaperModel]:
        """根据处理状态获取论文"""
        try:
            with get_database_manager().get_postgres_sync() as cursor:
                cursor.execute("""
                    SELECT * FROM arxiv_papers 
                    WHERE processing_status = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                """, (status, limit))
                
                results = cursor.fetchall()
                return [ArxivPaperModel.from_dict(dict(row)) for row in results]
                
        except Exception as e:
            logger.error(f"根据状态获取论文失败: {e}")
            return []
    
    def get_statistics(self) -> dict:
        """获取统计信息"""
        try:
            stats = {}
            
            # 总论文数
            stats['total'] = self.db_ops.count(ArxivPaperModel)
            
            # 按状态统计
            for status in ['pending', 'completed', 'failed']:
                stats[status] = self.db_ops.count(
                    ArxivPaperModel, 
                    'processing_status = %s', 
                    (status,)
                )
            
            # 今日新增
            with get_database_manager().get_postgres_sync() as cursor:
                cursor.execute("""
                    SELECT COUNT(*) FROM arxiv_papers 
                    WHERE DATE(created_at) = CURRENT_DATE
                """)
                result = cursor.fetchone()
                stats['today'] = result[0] if result else 0
            
            return stats
            
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {}
    
    def _arxiv_data_to_model(self, arxiv_data: ArxivData) -> ArxivPaperModel:
        """将ArxivData转换为ArxivPaperModel"""
        return ArxivPaperModel(
            arxiv_id=arxiv_data.arxiv_id or '',
            title=arxiv_data.title or '',
            authors='',  # ArxivData中没有authors字段，可以后续扩展
            abstract=arxiv_data.snippet or '',
            categories=arxiv_data.categories or '',
            published_date=arxiv_data.published_date or '',
            pdf_url=arxiv_data.pdf_link or '',
            processing_status='pending',
            tags=arxiv_data.tag or [],
            metadata={
                'link': arxiv_data.link,
                'pdf_path': arxiv_data.pdf_path
            }
        )

