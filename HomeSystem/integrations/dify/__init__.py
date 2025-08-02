from .dify import DifyClient

# Knowledge Base 统一模块 - 所有知识库相关功能
from .dify_knowledge import (
    # 客户端
    DifyKnowledgeBaseClient,
    
    # 配置类
    DifyKnowledgeBaseConfig, 
    get_config,
    UploadConfig,
    ProcessRule,
    IndexingTechnique,
    ProcessMode,
    DocumentType,
    
    # 数据模型
    DifyDatasetModel,
    DifyDocumentModel, 
    DifySegmentModel,
    DatasetStatus,
    DocumentStatus,
    IndexingStatus,
    
    # 异常类
    DifyKnowledgeBaseError,
    AuthenticationError,
    DatasetNotFoundError,
    DatasetCreationError,
    DocumentUploadError,
    DocumentNotFoundError,
    QueryError,
    RateLimitError,
    InvalidParameterError,
    NetworkError,
    ProcessingError,
    SegmentError
)

__all__ = [
    # 原有工作流客户端
    'DifyClient',
    
    # 知识库客户端
    'DifyKnowledgeBaseClient',
    
    # 配置类
    'DifyKnowledgeBaseConfig',
    'get_config',
    'UploadConfig',
    'ProcessRule',
    'IndexingTechnique',
    'ProcessMode', 
    'DocumentType',
    
    # 数据模型
    'DifyDatasetModel',
    'DifyDocumentModel',
    'DifySegmentModel',
    'DatasetStatus',
    'DocumentStatus',
    'IndexingStatus',
    
    # 异常类
    'DifyKnowledgeBaseError',
    'AuthenticationError',
    'DatasetNotFoundError',
    'DatasetCreationError',
    'DocumentUploadError',
    'DocumentNotFoundError',
    'QueryError',
    'RateLimitError',
    'InvalidParameterError',
    'NetworkError',
    'ProcessingError',
    'SegmentError'
]