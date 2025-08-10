"""
Dify 知识库服务 - 为PaperAnalysis应用提供Dify集成功能
使用共享的DifyService实现
"""
import os
import sys
import logging
from typing import Dict, List, Any, Optional

# 添加 HomeSystem 模块路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

# 导入共享的DifyService
from HomeSystem.integrations.dify.service import DifyService as SharedDifyService
from HomeSystem.integrations.database import DatabaseOperations

logger = logging.getLogger(__name__)


class DifyService:
    """Dify 知识库服务 - 基于共享服务的PaperAnalysis适配器"""
    
    def __init__(self):
        self.db_ops = DatabaseOperations()
        # 使用共享的DifyService，传入DatabaseOperations实例
        self._shared_service = SharedDifyService(db_ops=self.db_ops)
    
    def is_available(self) -> bool:
        """检查 Dify 服务是否可用"""
        return self._shared_service.is_available()
    
    def get_or_create_dataset(self, task_name: str) -> Optional[str]:
        """获取或创建以 task_name 命名的知识库"""
        return self._shared_service.get_or_create_dataset(task_name)
    
    def validate_upload_preconditions(self, arxiv_id: str) -> Dict[str, Any]:
        """验证上传前置条件"""
        return self._shared_service.validate_upload_preconditions(arxiv_id)
    
    def upload_paper_to_dify(self, arxiv_id: str) -> Dict[str, Any]:
        """上传论文到 Dify 知识库"""
        return self._shared_service.upload_paper_to_dify(arxiv_id)
    
    def get_eligible_papers_for_upload(self, filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """获取符合上传条件的论文"""
        return self._shared_service.get_eligible_papers_for_upload(filters)
    
    def upload_all_eligible_papers_with_summary(self, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """上传所有符合条件的论文并生成详细总结"""
        return self._shared_service.upload_all_eligible_papers_with_summary(filters)
    
    def verify_dify_document(self, arxiv_id: str) -> Dict[str, Any]:
        """验证单个文档在Dify中的状态"""
        return self._shared_service.verify_dify_document(arxiv_id)
    
    def remove_paper_from_dify(self, arxiv_id: str) -> Dict[str, Any]:
        """从 Dify 知识库移除论文"""
        return self._shared_service.remove_paper_from_dify(arxiv_id)
    
    def batch_verify_all_documents(self) -> Dict[str, Any]:
        """批量验证所有已上传文档的状态"""
        return self._shared_service.batch_verify_all_documents()