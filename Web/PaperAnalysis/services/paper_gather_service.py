"""
论文数据服务
用于查询和管理论文数据
"""
import sys
import os
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

# 添加HomeSystem到路径 - 使用更稳定的相对路径计算
current_dir = os.path.dirname(__file__)
homesystem_root = os.path.normpath(os.path.join(current_dir, "..", "..", ".."))
if homesystem_root not in sys.path:
    sys.path.insert(0, homesystem_root)

from HomeSystem.integrations.database import DatabaseOperations, ArxivPaperModel
from loguru import logger


class PaperDataService:
    """论文数据服务"""
    
    def __init__(self):
        self.db_ops = DatabaseOperations()
    
    def search_papers(self, query: str = "", category: str = "", 
                     status: str = "", page: int = 1, 
                     per_page: int = 20) -> Tuple[List[Dict[str, Any]], int]:
        """
        搜索论文
        
        Args:
            query: 搜索关键词
            category: 论文分类
            status: 状态筛选
            page: 页码
            per_page: 每页数量
        
        Returns:
            (papers, total): 论文列表和总数
        """
        try:
            # 构建WHERE子句
            where_conditions = []
            params = []
            
            if query:
                # 在标题、摘要、关键词中搜索
                where_conditions.append("(title ILIKE %s OR abstract ILIKE %s OR keywords ILIKE %s)")
                search_term = f"%{query}%"
                params.extend([search_term, search_term, search_term])
            
            if category:
                where_conditions.append("categories ILIKE %s")
                params.append(f"%{category}%")
            
            # 组合WHERE子句
            where_clause = " AND ".join(where_conditions) if where_conditions else None
            
            # 获取总数
            total = self.db_ops.count(ArxivPaperModel, where_clause, tuple(params) if params else None)
            
            # 分页查询
            offset = (page - 1) * per_page
            papers = self.db_ops.list_all(
                ArxivPaperModel, 
                limit=per_page, 
                offset=offset,
                order_by="created_at DESC"
            )
            
            # 转换为字典格式
            paper_dicts = []
            for paper in papers:
                paper_dict = self._paper_to_dict(paper)
                paper_dicts.append(paper_dict)
            
            return paper_dicts, total
            
        except Exception as e:
            logger.error(f"搜索论文失败: {e}")
            return [], 0
    
    def get_paper_detail(self, arxiv_id: str) -> Optional[Dict[str, Any]]:
        """获取论文详情"""
        try:
            paper = self.db_ops.get_by_field(ArxivPaperModel, 'arxiv_id', arxiv_id)
            if paper:
                return self._paper_to_dict(paper)
            return None
            
        except Exception as e:
            logger.error(f"获取论文详情失败: {arxiv_id}, {e}")
            return None
    
    def get_recent_papers(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取最近添加的论文"""
        try:
            papers = self.db_ops.list_all(
                ArxivPaperModel, 
                limit=limit,
                order_by="created_at DESC"
            )
            return [self._paper_to_dict(paper) for paper in papers]
            
        except Exception as e:
            logger.error(f"获取最近论文失败: {e}")
            return []
    
    def get_paper_statistics(self) -> Dict[str, Any]:
        """获取论文统计信息"""
        try:
            # 使用基础的count方法统计
            total_papers = self.db_ops.count(ArxivPaperModel)
            
            # 统计已分析论文（有research_objectives字段的论文）
            analyzed_papers = self.db_ops.count(
                ArxivPaperModel, 
                "research_objectives IS NOT NULL AND research_objectives != ''"
            )
            
            # 统计相关论文（有research_objectives且processing_status为completed的论文）
            relevant_papers = self.db_ops.count(
                ArxivPaperModel, 
                "research_objectives IS NOT NULL AND research_objectives != '' AND processing_status = 'completed'"
            )
            
            stats = {
                'total_papers': total_papers,
                'analyzed_papers': analyzed_papers,
                'relevant_papers': relevant_papers,
                'categories': {},  # 暂时为空，可以后续实现
                'daily_additions': [],  # 暂时为空，可以后续实现
                'analysis_summary': {}  # 暂时为空，可以后续实现
            }
            return stats
            
        except Exception as e:
            logger.error(f"获取论文统计失败: {e}")
            return {
                'total_papers': 0,
                'analyzed_papers': 0,
                'relevant_papers': 0,
                'categories': {},
                'daily_additions': [],
                'analysis_summary': {}
            }
    
    def _paper_to_dict(self, paper: ArxivPaperModel) -> Dict[str, Any]:
        """将论文模型转换为字典"""
        try:
            # 获取论文的所有属性，根据实际数据库字段
            paper_dict = {
                'id': getattr(paper, 'id', None),
                'arxiv_id': getattr(paper, 'arxiv_id', ''),
                'title': getattr(paper, 'title', ''),
                'authors': getattr(paper, 'authors', ''),
                'abstract': getattr(paper, 'abstract', ''),
                'categories': getattr(paper, 'categories', ''),
                'published_date': getattr(paper, 'published_date', None),
                'pdf_url': getattr(paper, 'pdf_url', ''),
                'processing_status': getattr(paper, 'processing_status', ''),
                'created_at': paper.created_at.isoformat() if hasattr(paper, 'created_at') and paper.created_at else None,
                'updated_at': paper.updated_at.isoformat() if hasattr(paper, 'updated_at') and paper.updated_at else None,
                
                # 结构化分析字段
                'research_background': getattr(paper, 'research_background', None),
                'research_objectives': getattr(paper, 'research_objectives', None),
                'methods': getattr(paper, 'methods', None),
                'key_findings': getattr(paper, 'key_findings', None),
                'conclusions': getattr(paper, 'conclusions', None),
                'limitations': getattr(paper, 'limitations', None),
                'future_work': getattr(paper, 'future_work', None),
                'keywords': getattr(paper, 'keywords', None),
                
                # 元数据和标签
                'tags': getattr(paper, 'tags', []),
                'metadata': getattr(paper, 'metadata', {}),
                
                # 兼容性字段（为了模板兼容）
                'link': f"https://arxiv.org/abs/{getattr(paper, 'arxiv_id', '')}" if getattr(paper, 'arxiv_id', '') else '',
                'pdf_link': getattr(paper, 'pdf_url', ''),
                'abstract_is_relevant': True,  # 默认值，实际可能需要根据数据调整
                'abstract_relevance_score': 0.8,  # 默认值
            }
            
            return paper_dict
            
        except Exception as e:
            logger.error(f"转换论文数据失败: {e}")
            return {
                'arxiv_id': getattr(paper, 'arxiv_id', 'unknown'),
                'title': getattr(paper, 'title', 'Unknown Title'),
                'error': f"数据转换失败: {str(e)}"
            }
    
    def update_paper_analysis(self, arxiv_id: str, analysis_data: Dict[str, Any]) -> bool:
        """更新论文分析数据"""
        try:
            paper = self.db_ops.get_by_field(ArxivPaperModel, 'arxiv_id', arxiv_id)
            if not paper:
                logger.warning(f"论文不存在: {arxiv_id}")
                return False
            
            # 更新分析字段
            for field, value in analysis_data.items():
                if hasattr(paper, field):
                    setattr(paper, field, value)
            
            # 更新时间戳
            paper.updated_at = datetime.now()
            
            # 保存到数据库
            success = self.db_ops.update(paper)
            if success:
                logger.info(f"论文分析数据已更新: {arxiv_id}")
            else:
                logger.error(f"更新论文分析数据失败: {arxiv_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"更新论文分析数据异常: {arxiv_id}, {e}")
            return False
    
    def delete_paper(self, arxiv_id: str) -> bool:
        """删除论文"""
        try:
            paper = self.db_ops.get_by_field(ArxivPaperModel, 'arxiv_id', arxiv_id)
            if not paper:
                logger.warning(f"论文不存在: {arxiv_id}")
                return False
            
            success = self.db_ops.delete(paper)
            if success:
                logger.info(f"论文已删除: {arxiv_id}")
            else:
                logger.error(f"删除论文失败: {arxiv_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"删除论文异常: {arxiv_id}, {e}")
            return False
    
    def batch_update_papers(self, updates: List[Dict[str, Any]]) -> int:
        """批量更新论文"""
        success_count = 0
        
        for update_data in updates:
            arxiv_id = update_data.get('arxiv_id')
            if not arxiv_id:
                continue
                
            analysis_data = {k: v for k, v in update_data.items() if k != 'arxiv_id'}
            if self.update_paper_analysis(arxiv_id, analysis_data):
                success_count += 1
        
        logger.info(f"批量更新完成: {success_count}/{len(updates)}")
        return success_count


# 全局服务实例
paper_data_service = PaperDataService()