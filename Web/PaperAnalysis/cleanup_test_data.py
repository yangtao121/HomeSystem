#!/usr/bin/env python3
"""
清理数据库中的测试Dify数据
用于修复测试数据污染问题
"""
import sys
import os

# 添加 HomeSystem 模块路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from HomeSystem.integrations.database import DatabaseOperations, ArxivPaperModel
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def cleanup_test_data():
    """清理数据库中的测试数据"""
    try:
        db_ops = DatabaseOperations()
        
        # 获取所有论文
        logger.info("正在获取所有论文数据...")
        papers = db_ops.list_all(ArxivPaperModel, limit=10000)
        
        cleaned_count = 0
        total_test_papers = 0
        
        for paper in papers:
            # 转换为ArxivPaperModel类型
            arxiv_paper = paper if isinstance(paper, ArxivPaperModel) else ArxivPaperModel.from_dict(paper.to_dict())
            
            # 检查是否为测试数据
            dataset_id = arxiv_paper.dify_dataset_id
            document_id = arxiv_paper.dify_document_id
            
            is_test_data = False
            if dataset_id or document_id:
                is_test_data = (
                    'test' in str(dataset_id or '').lower() or 
                    'test' in str(document_id or '').lower() or
                    dataset_id == 'test-dataset-id' or
                    document_id == 'test-document-id'
                )
            
            if is_test_data:
                total_test_papers += 1
                logger.info(f"发现测试数据 - 论文ID: {arxiv_paper.arxiv_id}, Dataset: {dataset_id}, Document: {document_id}")
                
                # 清理Dify信息
                arxiv_paper.clear_dify_info()
                
                # 只传递需要清除的Dify相关字段，避免updated_at重复
                clear_data = {
                    'dify_dataset_id': arxiv_paper.dify_dataset_id,
                    'dify_document_id': arxiv_paper.dify_document_id,
                    'dify_document_name': arxiv_paper.dify_document_name,
                    'dify_character_count': arxiv_paper.dify_character_count,
                    'dify_segment_count': arxiv_paper.dify_segment_count,
                    'dify_upload_time': arxiv_paper.dify_upload_time,
                    'dify_metadata': '{}' if arxiv_paper.dify_metadata else '{}'
                }
                
                success = db_ops.update(arxiv_paper, clear_data)
                if success:
                    cleaned_count += 1
                    logger.info(f"✅ 已清理论文 {arxiv_paper.arxiv_id}")
                else:
                    logger.error(f"❌ 清理失败 {arxiv_paper.arxiv_id}")
        
        logger.info(f"=== 清理完成 ===")
        logger.info(f"发现测试数据论文: {total_test_papers}")
        logger.info(f"成功清理论文: {cleaned_count}")
        logger.info(f"清理失败论文: {total_test_papers - cleaned_count}")
        
        return cleaned_count
        
    except Exception as e:
        logger.error(f"清理过程出错: {e}")
        return 0

if __name__ == "__main__":
    print("开始清理测试数据...")
    cleaned = cleanup_test_data()
    print(f"清理完成，共处理 {cleaned} 个测试数据记录")