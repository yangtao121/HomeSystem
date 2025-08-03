"""
Dify知识库完整集成模块
提供完整的知识库和文档管理API封装，包含配置、异常处理、数据模型和客户端功能
"""

import os
import json
import time
import hashlib
import uuid
from typing import Dict, Any, Optional, List, Union, Tuple
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import aiohttp
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from loguru import logger
import json

# 导入基础模型类
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'database'))
from models import BaseModel


# ============= 枚举定义 =============

class IndexingTechnique(Enum):
    """索引技术类型"""
    HIGH_QUALITY = "high_quality"  # 高质量索引
    ECONOMY = "economy"           # 经济型索引


class ProcessMode(Enum):
    """文档处理模式"""
    AUTOMATIC = "automatic"  # 自动处理
    CUSTOM = "custom"        # 自定义处理


class DocumentType(Enum):
    """支持的文档类型"""
    TXT = "TXT"
    PDF = "PDF"
    DOC = "DOC"
    DOCX = "DOCX"
    MD = "MD"
    HTML = "HTML"
    JSON = "JSON"
    CSV = "CSV"
    XLSX = "XLSX"


class DatasetStatus(Enum):
    """知识库状态"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    SYNCING = "syncing"


class DocumentStatus(Enum):
    """文档状态"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    ARCHIVED = "archived"


class IndexingStatus(Enum):
    """索引状态"""
    WAITING = "waiting"
    INDEXING = "indexing"
    COMPLETED = "completed"
    ERROR = "error"


# ============= 异常类定义 =============

class DifyKnowledgeBaseError(Exception):
    """Dify知识库操作基础异常类"""
    
    def __init__(
        self, 
        message: str, 
        error_code: Optional[str] = None,
        response: Optional[requests.Response] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.response = response
        self.details = details or {}
        
        # 从响应中提取额外信息
        if response is not None:
            self.status_code = response.status_code
            try:
                self.response_data = response.json()
            except Exception:
                self.response_data = response.text
        else:
            self.status_code = None
            self.response_data = None
    
    def __str__(self):
        base_msg = f"DifyKnowledgeBaseError: {self.message}"
        if self.error_code:
            base_msg += f" (Code: {self.error_code})"
        if self.status_code:
            base_msg += f" (HTTP: {self.status_code})"
        return base_msg
    
    def get_error_category(self) -> str:
        """获取错误类别"""
        error_categories = {
            "AUTH_FAILED": "authentication",
            "DATASET_NOT_FOUND": "configuration", 
            "DATASET_CREATION_FAILED": "configuration",
            "DOCUMENT_UPLOAD_FAILED": "upload",
            "DOCUMENT_NOT_FOUND": "data",
            "QUERY_FAILED": "operation",
            "RATE_LIMIT_EXCEEDED": "rate_limit",
            "INVALID_PARAMETER": "validation",
            "NETWORK_ERROR": "network",
            "PROCESSING_FAILED": "processing",
            "SEGMENT_FAILED": "processing"
        }
        return error_categories.get(self.error_code, "unknown")
    
    def get_user_friendly_message(self) -> str:
        """获取用户友好的错误消息"""
        return self.message
    
    def get_suggested_actions(self) -> List[str]:
        """获取建议的解决方案"""
        return ["请联系管理员或查看详细错误信息"]
    
    def is_retryable(self) -> bool:
        """判断是否可以重试"""
        retryable_codes = ["RATE_LIMIT_EXCEEDED", "NETWORK_ERROR", "PROCESSING_FAILED"]
        return self.error_code in retryable_codes
    
    def get_retry_delay(self) -> int:
        """获取建议的重试延迟（秒）"""
        if self.error_code == "RATE_LIMIT_EXCEEDED":
            return getattr(self, 'retry_after', 60)
        elif self.error_code == "NETWORK_ERROR":
            return 5
        elif self.error_code == "PROCESSING_FAILED":
            return 10
        return 0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式，用于API响应"""
        return {
            "error": True,
            "error_code": self.error_code,
            "message": self.message,
            "user_friendly_message": self.get_user_friendly_message(),
            "category": self.get_error_category(),
            "suggested_actions": self.get_suggested_actions(),
            "is_retryable": self.is_retryable(),
            "retry_delay": self.get_retry_delay(),
            "status_code": self.status_code,
            "details": self.details
        }


class AuthenticationError(DifyKnowledgeBaseError):
    """认证错误 - API密钥无效或过期"""
    
    def __init__(self, message: str = "Authentication failed", **kwargs):
        super().__init__(message, error_code="AUTH_FAILED", **kwargs)
    
    def get_user_friendly_message(self) -> str:
        return "API密钥认证失败，请检查您的Dify API密钥配置"
    
    def get_suggested_actions(self) -> List[str]:
        return [
            "检查Dify API密钥是否正确",
            "确认API密钥是否已过期",
            "验证API密钥的权限范围",
            "联系管理员更新API密钥配置"
        ]


class DatasetNotFoundError(DifyKnowledgeBaseError):
    """知识库不存在错误"""
    
    def __init__(self, dataset_id: str, **kwargs):
        message = f"Dataset not found: {dataset_id}"
        super().__init__(message, error_code="DATASET_NOT_FOUND", **kwargs)
        self.dataset_id = dataset_id
    
    def get_user_friendly_message(self) -> str:
        return f"知识库 '{self.dataset_id}' 不存在或无法访问"
    
    def get_suggested_actions(self) -> List[str]:
        return [
            "检查知识库ID是否正确",
            "确认知识库是否已创建",
            "验证您是否有该知识库的访问权限",
            "可能需要创建新的知识库"
        ]


class DatasetCreationError(DifyKnowledgeBaseError):
    """知识库创建失败错误"""
    
    def __init__(self, dataset_name: str, reason: str = "", **kwargs):
        message = f"Failed to create dataset '{dataset_name}'"
        if reason:
            message += f": {reason}"
        super().__init__(message, error_code="DATASET_CREATION_FAILED", **kwargs)
        self.dataset_name = dataset_name


class DocumentUploadError(DifyKnowledgeBaseError):
    """文档上传失败错误"""
    
    def __init__(self, document_name: str, reason: str = "", **kwargs):
        message = f"Failed to upload document '{document_name}'"
        if reason:
            message += f": {reason}"
        super().__init__(message, error_code="DOCUMENT_UPLOAD_FAILED", **kwargs)
        self.document_name = document_name
        self.reason = reason
    
    def get_user_friendly_message(self) -> str:
        base_msg = f"文档 '{self.document_name}' 上传失败"
        if self.reason:
            base_msg += f"：{self.reason}"
        return base_msg
    
    def get_suggested_actions(self) -> List[str]:
        actions = ["重试上传操作"]
        
        if "size" in (self.reason or "").lower():
            actions.extend([
                "检查文档大小是否超过限制",
                "尝试压缩文档内容",
                "分割大文档为较小部分"
            ])
        elif "format" in (self.reason or "").lower():
            actions.extend([
                "检查文档格式是否支持",
                "转换为支持的文档格式",
                "检查文档是否损坏"
            ])
        elif "network" in (self.reason or "").lower():
            actions.extend([
                "检查网络连接",
                "稍后重试",
                "尝试较小的批量上传"
            ])
        else:
            actions.extend([
                "检查文档内容是否完整",
                "验证网络连接稳定性",
                "确认知识库存储空间充足"
            ])
        
        return actions


class DocumentNotFoundError(DifyKnowledgeBaseError):
    """文档不存在错误"""
    
    def __init__(self, document_id: str, dataset_id: Optional[str] = None, **kwargs):
        message = f"Document not found: {document_id}"
        if dataset_id:
            message += f" in dataset {dataset_id}"
        super().__init__(message, error_code="DOCUMENT_NOT_FOUND", **kwargs)
        self.document_id = document_id
        self.dataset_id = dataset_id


class QueryError(DifyKnowledgeBaseError):
    """知识库查询错误"""
    
    def __init__(self, query: str, reason: str = "", **kwargs):
        message = f"Query failed for: '{query}'"
        if reason:
            message += f": {reason}"
        super().__init__(message, error_code="QUERY_FAILED", **kwargs)
        self.query = query


class RateLimitError(DifyKnowledgeBaseError):
    """API限流错误"""
    
    def __init__(self, retry_after: Optional[int] = None, **kwargs):
        message = "Rate limit exceeded"
        if retry_after:
            message += f". Retry after {retry_after} seconds"
        super().__init__(message, error_code="RATE_LIMIT_EXCEEDED", **kwargs)
        self.retry_after = retry_after
    
    def get_user_friendly_message(self) -> str:
        if self.retry_after:
            return f"API调用频率超限，请等待 {self.retry_after} 秒后重试"
        return "API调用频率超限，请稍后重试"
    
    def get_suggested_actions(self) -> List[str]:
        actions = [
            "等待一段时间后重试",
            "减少并发请求数量",
            "使用批量操作减少API调用频率"
        ]
        if self.retry_after:
            actions.insert(0, f"等待 {self.retry_after} 秒后自动重试")
        return actions


class InvalidParameterError(DifyKnowledgeBaseError):
    """参数错误"""
    
    def __init__(self, parameter: str, reason: str = "", **kwargs):
        message = f"Invalid parameter '{parameter}'"
        if reason:
            message += f": {reason}"
        super().__init__(message, error_code="INVALID_PARAMETER", **kwargs)
        self.parameter = parameter


class NetworkError(DifyKnowledgeBaseError):
    """网络连接错误"""
    
    def __init__(self, message: str = "Network connection failed", **kwargs):
        super().__init__(message, error_code="NETWORK_ERROR", **kwargs)
    
    def get_user_friendly_message(self) -> str:
        return "网络连接失败，无法连接到Dify服务"
    
    def get_suggested_actions(self) -> List[str]:
        return [
            "检查网络连接是否正常",
            "确认Dify服务是否可访问",
            "尝试使用VPN或更换网络",
            "稍后重试操作",
            "联系网络管理员检查防火墙设置"
        ]


class ProcessingError(DifyKnowledgeBaseError):
    """文档处理错误"""
    
    def __init__(self, document_name: str, reason: str = "", **kwargs):
        message = f"Failed to process document '{document_name}'"
        if reason:
            message += f": {reason}"
        super().__init__(message, error_code="PROCESSING_FAILED", **kwargs)
        self.document_name = document_name
        self.reason = reason
    
    def get_user_friendly_message(self) -> str:
        base_msg = f"文档 '{self.document_name}' 处理失败"
        if self.reason:
            base_msg += f"：{self.reason}"
        return base_msg
    
    def get_suggested_actions(self) -> List[str]:
        return [
            "稍后重试处理",
            "检查文档内容是否完整",
            "确认文档格式是否正确",
            "尝试重新上传文档",
            "联系技术支持获取帮助"
        ]


class SegmentError(DifyKnowledgeBaseError):
    """文档分片操作错误"""
    
    def __init__(self, segment_id: str, operation: str, reason: str = "", **kwargs):
        message = f"Failed to {operation} segment '{segment_id}'"
        if reason:
            message += f": {reason}"
        super().__init__(message, error_code="SEGMENT_OPERATION_FAILED", **kwargs)
        self.segment_id = segment_id
        self.operation = operation


def handle_api_error(response: requests.Response) -> DifyKnowledgeBaseError:
    """
    根据API响应创建相应的异常对象
    
    Args:
        response: HTTP响应对象
        
    Returns:
        相应的异常对象
    """
    status_code = response.status_code
    
    try:
        error_data = response.json()
        error_message = error_data.get('message', 'Unknown error')
        error_code = error_data.get('code', str(status_code))
    except Exception:
        error_message = response.text or f"HTTP {status_code} error"
        error_code = str(status_code)
    
    # 根据状态码返回相应的异常
    if status_code == 401:
        return AuthenticationError(error_message, response=response)
    elif status_code == 404:
        return DatasetNotFoundError("unknown", response=response)
    elif status_code == 429:
        retry_after = None
        if 'Retry-After' in response.headers:
            try:
                retry_after = int(response.headers['Retry-After'])
            except ValueError:
                pass
        return RateLimitError(retry_after=retry_after, response=response)
    elif status_code == 400:
        return InvalidParameterError("unknown", error_message, response=response)
    elif status_code >= 500:
        return NetworkError(f"Server error: {error_message}", response=response)
    else:
        return DifyKnowledgeBaseError(
            error_message, 
            error_code=error_code, 
            response=response
        )


# ============= 配置数据类 =============

@dataclass
class ProcessRule:
    """文档处理规则配置"""
    mode: ProcessMode = ProcessMode.AUTOMATIC
    pre_processing_rules: List[Dict[str, Any]] = field(default_factory=list)
    segmentation: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        # 根据Dify API要求，需要包装在rules字段中
        rules = {}
        
        if self.pre_processing_rules:
            rules["pre_processing_rules"] = self.pre_processing_rules
            
        if self.segmentation:
            rules["segmentation"] = self.segmentation
        
        result = {
            "rules": rules,
            "mode": self.mode.value
        }
            
        return result


@dataclass
class UploadConfig:
    """文档上传配置"""
    indexing_technique: IndexingTechnique = IndexingTechnique.HIGH_QUALITY
    process_rule: ProcessRule = field(default_factory=ProcessRule)
    original_document_id: Optional[str] = None
    duplicate_check: bool = True
    retrieval_model: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        result = {
            "indexing_technique": self.indexing_technique.value,
            "process_rule": self.process_rule.to_dict()
        }
        
        if self.original_document_id:
            result["original_document_id"] = self.original_document_id
            
        if not self.duplicate_check:
            result["duplicate_check"] = False
            
        if self.retrieval_model:
            result["retrieval_model"] = self.retrieval_model
            
        return result


@dataclass
class RetryConfig:
    """重试配置"""
    max_retries: int = 3
    backoff_factor: float = 0.3
    retry_on_status: List[int] = field(default_factory=lambda: [500, 502, 503, 504])
    retry_on_timeout: bool = True
    
    
@dataclass
class TimeoutConfig:
    """超时配置"""
    connect_timeout: int = 30
    read_timeout: int = 60
    upload_timeout: int = 300  # 文件上传超时


@dataclass
class DifyKnowledgeBaseConfig:
    """Dify知识库完整配置"""
    
    # 基础连接配置
    base_url: str = "http://localhost:80/v1"  # 默认值，应通过环境变量配置
    api_key: Optional[str] = None  # 必须通过环境变量配置
    user_id: str = "homesystem-default-user"  # 用户ID，用于API调用标识
    
    # 超时和重试配置
    timeout_config: TimeoutConfig = field(default_factory=TimeoutConfig)
    retry_config: RetryConfig = field(default_factory=RetryConfig)
    
    # 默认上传配置
    default_upload_config: UploadConfig = field(default_factory=UploadConfig)
    
    # 支持的文件类型和大小限制
    max_file_size_mb: int = 100
    supported_file_types: List[DocumentType] = field(default_factory=lambda: [
        DocumentType.TXT, DocumentType.PDF, DocumentType.DOC, 
        DocumentType.DOCX, DocumentType.MD, DocumentType.HTML
    ])
    
    # 批量操作配置
    batch_size: int = 10
    concurrent_uploads: int = 3
    
    # 缓存配置
    enable_local_cache: bool = True
    cache_ttl_seconds: int = 3600
    
    # 日志配置
    enable_detailed_logging: bool = True
    log_api_requests: bool = False  # 敏感信息，默认关闭
    
    @classmethod
    def from_environment(cls) -> 'DifyKnowledgeBaseConfig':
        """从环境变量创建配置"""
        config = cls()
        
        # 基础配置
        config.base_url = os.getenv('DIFY_BASE_URL', config.base_url)
        config.api_key = os.getenv('DIFY_KB_API_KEY', config.api_key)
        config.user_id = os.getenv('DIFY_KB_USER_ID', config.user_id)
        
        # 超时配置
        if os.getenv('DIFY_KB_CONNECT_TIMEOUT'):
            config.timeout_config.connect_timeout = int(os.getenv('DIFY_KB_CONNECT_TIMEOUT'))
        if os.getenv('DIFY_KB_READ_TIMEOUT'):
            config.timeout_config.read_timeout = int(os.getenv('DIFY_KB_READ_TIMEOUT'))
        if os.getenv('DIFY_KB_UPLOAD_TIMEOUT'):
            config.timeout_config.upload_timeout = int(os.getenv('DIFY_KB_UPLOAD_TIMEOUT'))
            
        # 重试配置
        if os.getenv('DIFY_KB_MAX_RETRIES'):
            config.retry_config.max_retries = int(os.getenv('DIFY_KB_MAX_RETRIES'))
        if os.getenv('DIFY_KB_BACKOFF_FACTOR'):
            config.retry_config.backoff_factor = float(os.getenv('DIFY_KB_BACKOFF_FACTOR'))
            
        # 文件上传配置
        if os.getenv('DIFY_KB_MAX_FILE_SIZE_MB'):
            config.max_file_size_mb = int(os.getenv('DIFY_KB_MAX_FILE_SIZE_MB'))
        if os.getenv('DIFY_KB_BATCH_SIZE'):
            config.batch_size = int(os.getenv('DIFY_KB_BATCH_SIZE'))
        if os.getenv('DIFY_KB_CONCURRENT_UPLOADS'):
            config.concurrent_uploads = int(os.getenv('DIFY_KB_CONCURRENT_UPLOADS'))
            
        # 缓存配置
        if os.getenv('DIFY_KB_ENABLE_CACHE'):
            config.enable_local_cache = os.getenv('DIFY_KB_ENABLE_CACHE').lower() == 'true'
        if os.getenv('DIFY_KB_CACHE_TTL'):
            config.cache_ttl_seconds = int(os.getenv('DIFY_KB_CACHE_TTL'))
            
        # 日志配置
        if os.getenv('DIFY_KB_DETAILED_LOGGING'):
            config.enable_detailed_logging = os.getenv('DIFY_KB_DETAILED_LOGGING').lower() == 'true'
        if os.getenv('DIFY_KB_LOG_API_REQUESTS'):
            config.log_api_requests = os.getenv('DIFY_KB_LOG_API_REQUESTS').lower() == 'true'
            
        return config
    
    def validate(self) -> bool:
        """验证配置是否有效"""
        if not self.base_url:
            raise ValueError("Base URL is required")
            
        if not self.api_key:
            raise ValueError("API key is required")
            
        if self.timeout_config.connect_timeout <= 0:
            raise ValueError("Connect timeout must be positive")
            
        if self.timeout_config.read_timeout <= 0:
            raise ValueError("Read timeout must be positive")
            
        if self.retry_config.max_retries < 0:
            raise ValueError("Max retries cannot be negative")
            
        if self.max_file_size_mb <= 0:
            raise ValueError("Max file size must be positive")
            
        if self.batch_size <= 0:
            raise ValueError("Batch size must be positive")
            
        if self.concurrent_uploads <= 0:
            raise ValueError("Concurrent uploads must be positive")
            
        return True
    
    def get_file_mime_type(self, file_extension: str) -> str:
        """根据文件扩展名获取MIME类型"""
        mime_types = {
            '.txt': 'text/plain',
            '.pdf': 'application/pdf',
            '.doc': 'application/msword',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.md': 'text/markdown',
            '.html': 'text/html',
            '.json': 'application/json',
            '.csv': 'text/csv',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        }
        return mime_types.get(file_extension.lower(), 'application/octet-stream')
    
    def is_supported_file_type(self, file_extension: str) -> bool:
        """检查文件类型是否支持"""
        supported_extensions = {
            DocumentType.TXT: ['.txt'],
            DocumentType.PDF: ['.pdf'],
            DocumentType.DOC: ['.doc'],
            DocumentType.DOCX: ['.docx'],
            DocumentType.MD: ['.md'],
            DocumentType.HTML: ['.html', '.htm'],
            DocumentType.JSON: ['.json'],
            DocumentType.CSV: ['.csv'],
            DocumentType.XLSX: ['.xlsx']
        }
        
        file_ext = file_extension.lower()
        for doc_type in self.supported_file_types:
            if file_ext in supported_extensions.get(doc_type, []):
                return True
        return False


# 默认配置实例
DEFAULT_CONFIG = DifyKnowledgeBaseConfig()


def get_config() -> DifyKnowledgeBaseConfig:
    """获取配置实例（优先从环境变量加载）"""
    try:
        return DifyKnowledgeBaseConfig.from_environment()
    except Exception:
        return DEFAULT_CONFIG


# ============= 数据模型类 =============

class DifyDatasetModel(BaseModel):
    """Dify知识库数据模型"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # 基础信息
        self.dify_dataset_id = kwargs.get('dify_dataset_id', '')  # Dify系统中的数据集ID
        self.name = kwargs.get('name', '')
        self.description = kwargs.get('description', '')
        
        # 权限和访问控制
        self.permission = kwargs.get('permission', 'only_me')  # only_me, all_team_members, partial_members
        
        # 状态信息
        self.status = kwargs.get('status', DatasetStatus.ACTIVE.value)
        self.document_count = kwargs.get('document_count', 0)
        self.character_count = kwargs.get('character_count', 0)
        
        # 配置信息
        self.indexing_technique = kwargs.get('indexing_technique', 'high_quality')
        self.embedding_model = kwargs.get('embedding_model', '')
        self.embedding_model_provider = kwargs.get('embedding_model_provider', '')
        
        # 元数据
        self.tags = kwargs.get('tags', [])
        self.metadata = kwargs.get('metadata', {})
        
        # 同步信息
        self.last_sync_time = kwargs.get('last_sync_time', None)
        self.sync_status = kwargs.get('sync_status', 'completed')
        self.sync_error = kwargs.get('sync_error', None)
        
        # API访问信息
        self.api_key = kwargs.get('api_key', '')
        self.api_base_url = kwargs.get('api_base_url', '')
    
    @property
    def table_name(self) -> str:
        return 'dify_datasets'
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'id': self.id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'dify_dataset_id': self.dify_dataset_id,
            'name': self.name,
            'description': self.description,
            'permission': self.permission,
            'status': self.status,
            'document_count': self.document_count,
            'character_count': self.character_count,
            'indexing_technique': self.indexing_technique,
            'embedding_model': self.embedding_model,
            'embedding_model_provider': self.embedding_model_provider,
            'tags': json.dumps(self.tags) if self.tags else '[]',
            'metadata': json.dumps(self.metadata) if self.metadata else '{}',
            'last_sync_time': self.last_sync_time.isoformat() if self.last_sync_time else None,
            'sync_status': self.sync_status,
            'sync_error': self.sync_error,
            'api_key': self.api_key,
            'api_base_url': self.api_base_url
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DifyDatasetModel':
        """从字典创建实例"""
        # 处理时间字段
        if isinstance(data.get('created_at'), str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if isinstance(data.get('updated_at'), str):
            data['updated_at'] = datetime.fromisoformat(data['updated_at'])
        if isinstance(data.get('last_sync_time'), str):
            data['last_sync_time'] = datetime.fromisoformat(data['last_sync_time'])
        
        # 处理JSON字段
        if isinstance(data.get('tags'), str):
            data['tags'] = json.loads(data['tags'])
        if isinstance(data.get('metadata'), str):
            data['metadata'] = json.loads(data['metadata'])
            
        return cls(**data)
    
    def get_create_table_sql(self) -> str:
        """获取创建表的SQL语句"""
        return """
        CREATE TABLE IF NOT EXISTS dify_datasets (
            id VARCHAR(255) PRIMARY KEY,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            dify_dataset_id VARCHAR(255) UNIQUE NOT NULL,
            name VARCHAR(255) NOT NULL,
            description TEXT,
            permission VARCHAR(50) DEFAULT 'only_me',
            status VARCHAR(50) DEFAULT 'active',
            document_count INTEGER DEFAULT 0,
            character_count BIGINT DEFAULT 0,
            indexing_technique VARCHAR(100),
            embedding_model VARCHAR(255),
            embedding_model_provider VARCHAR(255),
            tags TEXT DEFAULT '[]',
            metadata TEXT DEFAULT '{}',
            last_sync_time TIMESTAMP,
            sync_status VARCHAR(50) DEFAULT 'completed',
            sync_error TEXT,
            api_key VARCHAR(255),
            api_base_url VARCHAR(255),
            INDEX idx_dify_dataset_id (dify_dataset_id),
            INDEX idx_name (name),
            INDEX idx_status (status),
            INDEX idx_sync_status (sync_status)
        )
        """


class DifyDocumentModel(BaseModel):
    """Dify文档数据模型"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # 基础信息
        self.dify_document_id = kwargs.get('dify_document_id', '')  # Dify系统中的文档ID
        self.dify_dataset_id = kwargs.get('dify_dataset_id', '')   # 所属数据集ID
        self.local_dataset_id = kwargs.get('local_dataset_id', '') # 本地数据集ID
        
        # 文档信息
        self.name = kwargs.get('name', '')
        self.data_source_type = kwargs.get('data_source_type', 'upload_file')  # upload_file, notion_import, etc.
        self.data_source_info = kwargs.get('data_source_info', {})
        
        # 内容信息
        self.character_count = kwargs.get('character_count', 0)
        self.word_count = kwargs.get('word_count', 0)
        self.tokens = kwargs.get('tokens', 0)
        
        # 处理状态
        self.status = kwargs.get('status', DocumentStatus.PENDING.value)
        self.indexing_status = kwargs.get('indexing_status', IndexingStatus.WAITING.value)
        self.processing_started_at = kwargs.get('processing_started_at', None)
        self.processing_completed_at = kwargs.get('processing_completed_at', None)
        self.error = kwargs.get('error', None)
        
        # 索引配置
        self.indexing_technique = kwargs.get('indexing_technique', 'high_quality')
        self.process_rule = kwargs.get('process_rule', {})
        
        # 文件信息（如果是文件上传）
        self.file_id = kwargs.get('file_id', '')
        self.file_name = kwargs.get('file_name', '')
        self.file_type = kwargs.get('file_type', '')
        self.file_size = kwargs.get('file_size', 0)
        self.file_url = kwargs.get('file_url', '')
        self.mime_type = kwargs.get('mime_type', '')
        
        # 本地文件路径（备份）
        self.local_file_path = kwargs.get('local_file_path', '')
        
        # 元数据
        self.tags = kwargs.get('tags', [])
        self.metadata = kwargs.get('metadata', {})
        
        # 分片信息
        self.segment_count = kwargs.get('segment_count', 0)
        self.hit_count = kwargs.get('hit_count', 0)
        
        # 关联信息
        self.source_paper_id = kwargs.get('source_paper_id', None)  # 关联的ArXiv论文ID
        self.source_note_id = kwargs.get('source_note_id', None)    # 关联的SiYuan笔记ID
    
    @property
    def table_name(self) -> str:
        return 'dify_documents'
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'id': self.id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'dify_document_id': self.dify_document_id,
            'dify_dataset_id': self.dify_dataset_id,
            'local_dataset_id': self.local_dataset_id,
            'name': self.name,
            'data_source_type': self.data_source_type,
            'data_source_info': json.dumps(self.data_source_info) if self.data_source_info else '{}',
            'character_count': self.character_count,
            'word_count': self.word_count,
            'tokens': self.tokens,
            'status': self.status,
            'indexing_status': self.indexing_status,
            'processing_started_at': self.processing_started_at.isoformat() if self.processing_started_at else None,
            'processing_completed_at': self.processing_completed_at.isoformat() if self.processing_completed_at else None,
            'error': self.error,
            'indexing_technique': self.indexing_technique,
            'process_rule': json.dumps(self.process_rule) if self.process_rule else '{}',
            'file_id': self.file_id,
            'file_name': self.file_name,
            'file_type': self.file_type,
            'file_size': self.file_size,
            'file_url': self.file_url,
            'mime_type': self.mime_type,
            'local_file_path': self.local_file_path,
            'tags': json.dumps(self.tags) if self.tags else '[]',
            'metadata': json.dumps(self.metadata) if self.metadata else '{}',
            'segment_count': self.segment_count,
            'hit_count': self.hit_count,
            'source_paper_id': self.source_paper_id,
            'source_note_id': self.source_note_id
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DifyDocumentModel':
        """从字典创建实例"""
        # 处理时间字段
        for time_field in ['created_at', 'updated_at', 'processing_started_at', 'processing_completed_at']:
            if isinstance(data.get(time_field), str):
                data[time_field] = datetime.fromisoformat(data[time_field])
        
        # 处理JSON字段
        for json_field in ['data_source_info', 'process_rule', 'tags', 'metadata']:
            if isinstance(data.get(json_field), str):
                data[json_field] = json.loads(data[json_field])
                
        return cls(**data)
    
    def get_create_table_sql(self) -> str:
        """获取创建表的SQL语句"""
        return """
        CREATE TABLE IF NOT EXISTS dify_documents (
            id VARCHAR(255) PRIMARY KEY,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            dify_document_id VARCHAR(255) UNIQUE NOT NULL,
            dify_dataset_id VARCHAR(255) NOT NULL,
            local_dataset_id VARCHAR(255),
            name VARCHAR(500) NOT NULL,
            data_source_type VARCHAR(100),
            data_source_info TEXT DEFAULT '{}',
            character_count INTEGER DEFAULT 0,
            word_count INTEGER DEFAULT 0,
            tokens INTEGER DEFAULT 0,
            status VARCHAR(50) DEFAULT 'pending',
            indexing_status VARCHAR(50) DEFAULT 'waiting',
            processing_started_at TIMESTAMP,
            processing_completed_at TIMESTAMP,
            error TEXT,
            indexing_technique VARCHAR(100),
            process_rule TEXT DEFAULT '{}',
            file_id VARCHAR(255),
            file_name VARCHAR(500),
            file_type VARCHAR(100),
            file_size BIGINT DEFAULT 0,
            file_url VARCHAR(1000),
            mime_type VARCHAR(100),
            local_file_path VARCHAR(1000),
            tags TEXT DEFAULT '[]',
            metadata TEXT DEFAULT '{}',
            segment_count INTEGER DEFAULT 0,
            hit_count INTEGER DEFAULT 0,
            source_paper_id VARCHAR(255),
            source_note_id VARCHAR(255),
            INDEX idx_dify_document_id (dify_document_id),
            INDEX idx_dify_dataset_id (dify_dataset_id),
            INDEX idx_local_dataset_id (local_dataset_id),
            INDEX idx_name (name),
            INDEX idx_status (status),
            INDEX idx_indexing_status (indexing_status),
            INDEX idx_source_paper_id (source_paper_id),
            INDEX idx_source_note_id (source_note_id),
            FOREIGN KEY (local_dataset_id) REFERENCES dify_datasets(id) ON DELETE CASCADE
        )
        """


class DifySegmentModel(BaseModel):
    """Dify文档分片数据模型"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # 基础信息
        self.dify_segment_id = kwargs.get('dify_segment_id', '')
        self.dify_document_id = kwargs.get('dify_document_id', '')
        self.local_document_id = kwargs.get('local_document_id', '')
        
        # 分片内容
        self.content = kwargs.get('content', '')
        self.answer = kwargs.get('answer', '')  # 问答对中的答案
        self.word_count = kwargs.get('word_count', 0)
        self.tokens = kwargs.get('tokens', 0)
        
        # 位置信息
        self.position = kwargs.get('position', 0)
        self.hash = kwargs.get('hash', '')
        
        # 状态信息
        self.status = kwargs.get('status', 'completed')
        self.enabled = kwargs.get('enabled', True)
        self.disabled_at = kwargs.get('disabled_at', None)
        self.disabled_by = kwargs.get('disabled_by', None)
        
        # 索引信息
        self.indexing_at = kwargs.get('indexing_at', None)
        self.completed_at = kwargs.get('completed_at', None)
        self.error = kwargs.get('error', None)
        self.stopped_at = kwargs.get('stopped_at', None)
        
        # 使用统计
        self.hit_count = kwargs.get('hit_count', 0)
        self.last_hit_at = kwargs.get('last_hit_at', None)
        
        # 关键词
        self.keywords = kwargs.get('keywords', [])
    
    @property
    def table_name(self) -> str:
        return 'dify_segments'
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'id': self.id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'dify_segment_id': self.dify_segment_id,
            'dify_document_id': self.dify_document_id,
            'local_document_id': self.local_document_id,
            'content': self.content,
            'answer': self.answer,
            'word_count': self.word_count,
            'tokens': self.tokens,
            'position': self.position,
            'hash': self.hash,
            'status': self.status,
            'enabled': self.enabled,
            'disabled_at': self.disabled_at.isoformat() if self.disabled_at else None,
            'disabled_by': self.disabled_by,
            'indexing_at': self.indexing_at.isoformat() if self.indexing_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'error': self.error,
            'stopped_at': self.stopped_at.isoformat() if self.stopped_at else None,
            'hit_count': self.hit_count,
            'last_hit_at': self.last_hit_at.isoformat() if self.last_hit_at else None,
            'keywords': json.dumps(self.keywords) if self.keywords else '[]'
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DifySegmentModel':
        """从字典创建实例"""
        # 处理时间字段
        time_fields = ['created_at', 'updated_at', 'disabled_at', 'indexing_at', 
                      'completed_at', 'stopped_at', 'last_hit_at']
        for time_field in time_fields:
            if isinstance(data.get(time_field), str):
                data[time_field] = datetime.fromisoformat(data[time_field])
        
        # 处理JSON字段
        if isinstance(data.get('keywords'), str):
            data['keywords'] = json.loads(data['keywords'])
                
        return cls(**data)
    
    def get_create_table_sql(self) -> str:
        """获取创建表的SQL语句"""
        return """
        CREATE TABLE IF NOT EXISTS dify_segments (
            id VARCHAR(255) PRIMARY KEY,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            dify_segment_id VARCHAR(255) UNIQUE NOT NULL,
            dify_document_id VARCHAR(255) NOT NULL,
            local_document_id VARCHAR(255),
            content TEXT NOT NULL,
            answer TEXT,
            word_count INTEGER DEFAULT 0,
            tokens INTEGER DEFAULT 0,
            position INTEGER DEFAULT 0,
            hash VARCHAR(255),
            status VARCHAR(50) DEFAULT 'completed',
            enabled BOOLEAN DEFAULT TRUE,
            disabled_at TIMESTAMP,
            disabled_by VARCHAR(255),
            indexing_at TIMESTAMP,
            completed_at TIMESTAMP,
            error TEXT,
            stopped_at TIMESTAMP,
            hit_count INTEGER DEFAULT 0,
            last_hit_at TIMESTAMP,
            keywords TEXT DEFAULT '[]',
            INDEX idx_dify_segment_id (dify_segment_id),
            INDEX idx_dify_document_id (dify_document_id),
            INDEX idx_local_document_id (local_document_id),
            INDEX idx_position (position),
            INDEX idx_status (status),
            INDEX idx_enabled (enabled),
            INDEX idx_hit_count (hit_count),
            FOREIGN KEY (local_document_id) REFERENCES dify_documents(id) ON DELETE CASCADE,
            FULLTEXT(content, answer)
        )
        """


# ============= 主客户端类 =============

class DifyKnowledgeBaseClient:
    """Dify知识库管理客户端"""
    
    def __init__(self, config: Optional[DifyKnowledgeBaseConfig] = None):
        """
        初始化客户端
        
        Args:
            config: 配置对象，如果为None则使用默认配置
        """
        self.config = config or get_config()
        self.config.validate()
        
        # 设置会话
        self.session = requests.Session()
        self._setup_session()
        
        # 缓存
        self._dataset_cache = {}
        self._cache_timestamps = {}
        
        logger.info(f"Dify Knowledge Base Client initialized with base URL: {self.config.base_url}")
    
    def _setup_session(self):
        """设置HTTP会话配置"""
        # 重试策略
        retry_strategy = Retry(
            total=self.config.retry_config.max_retries,
            backoff_factor=self.config.retry_config.backoff_factor,
            status_forcelist=self.config.retry_config.retry_on_status,
            allowed_methods=['GET', 'POST', 'PUT', 'DELETE']
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
        
        # 设置默认头
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.config.api_key}',
            'User-Agent': 'HomeSystem-DifyKB-Client/1.0'
        })
    
    def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        data: Optional[Union[Dict, str]] = None,
        files: Optional[Dict] = None,
        timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        发送HTTP请求
        
        Args:
            method: HTTP方法
            endpoint: API端点
            data: 请求数据
            files: 文件数据
            timeout: 超时时间
            
        Returns:
            响应数据
            
        Raises:
            DifyKnowledgeBaseError: API请求失败
        """
        # 构造URL，避免路径重复
        base_url = self.config.base_url.rstrip('/')
        endpoint = endpoint.lstrip('/')
        # Dify API需要/v1前缀
        if not base_url.endswith('/v1'):
            url = f"{base_url}/v1/{endpoint}"
        else:
            url = f"{base_url}/{endpoint}"
        
        # 设置超时
        if timeout is None:
            if files:
                timeout = self.config.timeout_config.upload_timeout
            else:
                timeout = self.config.timeout_config.read_timeout
        
        # 日志记录
        if self.config.log_api_requests:
            logger.debug(f"Making {method} request to {url}")
            if data and self.config.enable_detailed_logging:
                logger.debug(f"Request data: {json.dumps(data, indent=2)}")
        
        # 总是记录请求URL，以便调试
        logger.info(f"API请求: {method} {url}")
        if 'datasets/' in url:
            logger.info(f"知识库操作URL: {url}")
        
        try:
            # 发送请求
            headers = self.session.headers.copy()
            if files:
                # 文件上传时移除Content-Type，让requests自动设置
                headers.pop('Content-Type', None)
            logger.debug(f"Request headers: {headers}")
            logger.debug(f"data: {data}") 

            # 对于文件上传，不应该转换data为JSON字符串
            if files:
                # 文件上传时，data应该保持为dict格式或None
                response = self.session.request(
                    method=method,
                    url=url,
                    data=data,  # 对于multipart，保持原始格式
                    files=files,
                    headers=headers,
                    timeout=timeout
                )
            else:
                # 普通API调用
                if data is not None and isinstance(data, dict):
                    # 使用json参数让requests自动处理JSON编码和Content-Type
                    response = self.session.request(
                        method=method,
                        url=url,
                        json=data,
                        headers=headers,
                        timeout=timeout
                    )
                else:
                    # 无数据或字符串数据
                    response = self.session.request(
                        method=method,
                        url=url,
                        data=data,
                        headers=headers,
                        timeout=timeout
                    )
            
            # 检查响应状态
            if not response.ok:
                raise handle_api_error(response)
            
            # 解析响应
            try:
                result = response.json()
                if self.config.enable_detailed_logging:
                    logger.debug(f"Response: {json.dumps(result, indent=2)}")
                return result
            except json.JSONDecodeError:
                raise DifyKnowledgeBaseError(
                    f"Invalid JSON response: {response.text}",
                    response=response
                )
                
        except requests.exceptions.Timeout:
            raise NetworkError(f"Request timeout after {timeout} seconds")
        except requests.exceptions.ConnectionError as e:
            raise NetworkError(f"Connection error: {str(e)}")
        except requests.exceptions.RequestException as e:
            raise DifyKnowledgeBaseError(f"Request failed: {str(e)}")
    
    # ============= 知识库管理 API =============
    
    def create_dataset(
        self, 
        name: str, 
        description: str = "",
        permission: str = "only_me"
    ) -> DifyDatasetModel:
        """
        创建知识库
        
        Args:
            name: 知识库名称
            description: 描述
            permission: 权限设置
            
        Returns:
            创建的知识库模型
        """
        try:
            data = {
                "name": name,
                "permission": permission
            }
            if description:
                data["description"] = description
            
            response = self._make_request('POST', 'datasets', data=data)
            
            # 创建本地模型
            dataset = DifyDatasetModel(
                dify_dataset_id=response['id'],
                name=name,
                description=description,
                permission=permission,
                status=DatasetStatus.ACTIVE.value,
                api_key=self.config.api_key,
                api_base_url=self.config.base_url
            )
            
            # 更新缓存
            self._update_cache(dataset.dify_dataset_id, dataset)
            
            logger.info(f"Created dataset: {name} (ID: {dataset.dify_dataset_id})")
            return dataset
            
        except Exception as e:
            if isinstance(e, DifyKnowledgeBaseError):
                raise
            raise DatasetCreationError(name, str(e))
    
    def get_dataset(self, dataset_id: str, use_cache: bool = True) -> DifyDatasetModel:
        """
        获取知识库信息
        
        Args:
            dataset_id: 知识库ID
            use_cache: 是否使用缓存
            
        Returns:
            知识库模型
        """
        # 检查缓存
        if use_cache and self._is_cache_valid(dataset_id):
            return self._dataset_cache[dataset_id]
        
        try:
            response = self._make_request('GET', f'datasets/{dataset_id}')
            
            # 创建模型
            dataset = DifyDatasetModel(
                dify_dataset_id=response['id'],
                name=response['name'],
                description=response.get('description', ''),
                permission=response.get('permission', 'only_me'),
                document_count=response.get('document_count', 0),
                character_count=response.get('character_count', 0),
                indexing_technique=response.get('indexing_technique', ''),
                embedding_model=response.get('embedding_model', ''),
                embedding_model_provider=response.get('embedding_model_provider', ''),
                api_key=self.config.api_key,
                api_base_url=self.config.base_url
            )
            
            # 更新缓存
            self._update_cache(dataset_id, dataset)
            return dataset
            
        except Exception as e:
            if isinstance(e, DifyKnowledgeBaseError):
                raise
            raise DatasetNotFoundError(dataset_id)
    
    def list_datasets(self, page: int = 1, limit: int = 20) -> List[DifyDatasetModel]:
        """
        列出知识库
        
        Args:
            page: 页码
            limit: 每页数量
            
        Returns:
            知识库列表
        """
        try:
            response = self._make_request('GET', f'datasets?page={page}&limit={limit}')
            
            datasets = []
            for item in response.get('data', []):
                dataset = DifyDatasetModel(
                    dify_dataset_id=item['id'],
                    name=item['name'],
                    description=item.get('description', ''),
                    permission=item.get('permission', 'only_me'),
                    document_count=item.get('document_count', 0),
                    character_count=item.get('character_count', 0),
                    indexing_technique=item.get('indexing_technique', ''),
                    api_key=self.config.api_key,
                    api_base_url=self.config.base_url
                )
                datasets.append(dataset)
                
                # 更新缓存
                self._update_cache(dataset.dify_dataset_id, dataset)
            
            return datasets
            
        except Exception as e:
            if isinstance(e, DifyKnowledgeBaseError):
                raise
            raise DifyKnowledgeBaseError(f"Failed to list datasets: {str(e)}")
    
    def delete_dataset(self, dataset_id: str) -> bool:
        """
        删除知识库
        
        Args:
            dataset_id: 知识库ID
            
        Returns:
            是否成功删除
        """
        try:
            self._make_request('DELETE', f'datasets/{dataset_id}')
            
            # 清除缓存
            self._dataset_cache.pop(dataset_id, None)
            self._cache_timestamps.pop(dataset_id, None)
            
            logger.info(f"Deleted dataset: {dataset_id}")
            return True
            
        except Exception as e:
            if isinstance(e, DifyKnowledgeBaseError):
                raise
            raise DifyKnowledgeBaseError(f"Failed to delete dataset {dataset_id}: {str(e)}")
    
    # ============= 文档管理 API =============
    
    def upload_document_text(
        self,
        dataset_id: str,
        name: str,
        text: str,
        upload_config: Optional[UploadConfig] = None
    ) -> DifyDocumentModel:
        """
        通过文本创建文档
        
        Args:
            dataset_id: 知识库ID
            name: 文档名称
            text: 文档内容
            upload_config: 上传配置
            
        Returns:
            创建的文档模型
        """
        try:
            config = upload_config or self.config.default_upload_config
            
            data = {
                "name": name,
                "text": text,
                **config.to_dict()
            }
            
            response = self._make_request(
                'POST', 
                f'datasets/{dataset_id}/document/create_by_text',
                data=data
            )
            
            # 创建文档模型
            document = DifyDocumentModel(
                dify_document_id=response['document']['id'],
                dify_dataset_id=dataset_id,
                name=name,
                data_source_type='upload_text',
                character_count=len(text),
                word_count=len(text.split()),
                status=DocumentStatus.PROCESSING.value,
                indexing_technique=config.indexing_technique.value,
                process_rule=config.process_rule.to_dict()
            )
            
            logger.info(f"Uploaded text document: {name} to dataset {dataset_id}")
            return document
            
        except Exception as e:
            if isinstance(e, DifyKnowledgeBaseError):
                raise
            raise DocumentUploadError(name, str(e))
    
    def upload_document_file(
        self,
        dataset_id: str,
        file_path: Union[str, Path],
        name: Optional[str] = None,
        upload_config: Optional[UploadConfig] = None
    ) -> DifyDocumentModel:
        """
        通过文件创建文档
        
        Args:
            dataset_id: 知识库ID
            file_path: 文件路径
            name: 文档名称（如果为None则使用文件名）
            upload_config: 上传配置
            
        Returns:
            创建的文档模型
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise DocumentUploadError(str(file_path), "File not found")
        
        # 检查文件大小
        file_size = file_path.stat().st_size
        max_size = self.config.max_file_size_mb * 1024 * 1024
        if file_size > max_size:
            raise DocumentUploadError(
                str(file_path), 
                f"File size {file_size} exceeds limit {max_size}"
            )
        
        # 检查文件类型
        if not self.config.is_supported_file_type(file_path.suffix):
            raise DocumentUploadError(
                str(file_path),
                f"Unsupported file type: {file_path.suffix}"
            )
        
        try:
            # 验证上传前的配置和权限
            validation_result = self._validate_upload_requirements(dataset_id)
            if validation_result['has_issues']:
                logger.warning("发现配置问题:")
                for issue in validation_result['issues']:
                    logger.warning(f"  - {issue}")
                logger.warning("建议:")
                for suggestion in validation_result['suggestions']:
                    logger.warning(f"  - {suggestion}")
            
            config = upload_config or self.config.default_upload_config
            
            # 清理文档名称，避免特殊字符导致上传失败
            if name:
                doc_name = self._sanitize_document_name(name)
            else:
                doc_name = self._sanitize_document_name(file_path.stem)
            
            logger.info(f"清理后的文档名称: {doc_name}")
            
            # 准备文件上传
            mime_type = self.config.get_file_mime_type(file_path.suffix)
            
            # 根据Dify API文档，构造正确的multipart/form-data格式
            upload_config_data = {
                'indexing_technique': config.indexing_technique.value,
                'process_rule': config.process_rule.to_dict()
            }
            
            # 调试信息：打印实际发送的数据
            logger.info(f"文件上传配置数据: {upload_config_data}")
            logger.info(f"文件路径: {file_path}, MIME类型: {mime_type}")
            
            # 使用requests直接发送multipart/form-data请求
            # 不能使用_make_request方法，因为它会错误处理multipart数据
            url = f"{self.config.base_url.rstrip('/')}/v1/datasets/{dataset_id}/document/create-by-file"
            
            headers = {
                'Authorization': f'Bearer {self.config.api_key}',
                'User-Agent': 'HomeSystem-DifyKB-Client/1.0'
            }
            
            # 获取用户ID
            user_id = self.config.user_id
            
            # 尝试多种格式，以兼容不同版本的API
            upload_attempts = [
                {
                    'name': '标准格式(data+user分离)',
                    'files_func': lambda f: {'file': (file_path.name, f, mime_type)},
                    'data_func': lambda: {'data': json.dumps(upload_config_data), 'user': user_id}
                },
                {
                    'name': '旧格式(全部在files中)',
                    'files_func': lambda f: {
                        'file': (file_path.name, f, mime_type),
                        'data': (None, json.dumps(upload_config_data)),
                        'user': (None, user_id)
                    },
                    'data_func': lambda: None
                },
                {
                    'name': '无user字段格式',
                    'files_func': lambda f: {'file': (file_path.name, f, mime_type)},
                    'data_func': lambda: {'data': json.dumps(upload_config_data)}
                }
            ]
            
            # 尝试不同的上传格式，直到成功或全部失败
            last_exception = None
            response_data = None
            
            for attempt_idx, attempt in enumerate(upload_attempts, 1):
                logger.info(f"第 {attempt_idx} 次尝试上传: {attempt['name']}")
                
                try:
                    with open(file_path, 'rb') as f:
                        files = attempt['files_func'](f)
                        data = attempt['data_func']()
                        
                        logger.info(f"发送文件上传请求到: {url}")
                        logger.info(f"用户ID: {user_id}")
                        logger.info(f"文件信息: 名称={file_path.name}, 大小={file_path.stat().st_size}, MIME={mime_type}")
                        logger.info(f"尝试格式: {attempt['name']}")
                        if data:
                            logger.info(f"表单数据: {data}")
                        logger.debug(f"上传配置详情: {upload_config_data}")
                        
                        response = requests.post(
                            url=url,
                            headers=headers,
                            files=files,
                            data=data,
                            timeout=self.config.timeout_config.upload_timeout
                        )
                        
                        # 检查响应状态
                        if response.ok:
                            # 成功上传，解析响应
                            try:
                                response_data = response.json()
                                logger.info(f"文件上传成功，使用格式: {attempt['name']}")
                                logger.info(f"响应: {response_data}")
                                break  # 成功，跳出尝试循环
                            except json.JSONDecodeError:
                                raise DifyKnowledgeBaseError(
                                    f"Invalid JSON response: {response.text}",
                                    response=response
                                )
                        else:
                            # 上传失败，记录错误并尝试下一种格式
                            logger.warning(f"尝试 {attempt['name']} 失败，状态码: {response.status_code}")
                            logger.warning(f"响应内容: {response.text}")
                            
                            # 尝试解析错误响应以获取更详细的信息
                            try:
                                error_detail = response.json()
                                logger.warning(f"API错误详情: {error_detail}")
                            except Exception:
                                logger.warning("无法解析错误响应详情")
                            
                            # 保存异常以备最后抛出
                            last_exception = handle_api_error(response)
                            
                            # 如果不是最后一次尝试，继续下一种格式
                            if attempt_idx < len(upload_attempts):
                                logger.info(f"将尝试下一种格式...")
                                continue
                            else:
                                # 所有格式都失败了，详细记录最后的错误
                                logger.error("所有上传格式都失败了，详细错误信息:")
                                logger.error(f"文件信息: 名称={file_path.name}, 大小={file_path.stat().st_size}, MIME={mime_type}")
                                if data:
                                    logger.error(f"最后尝试的表单数据: {data}")
                                logger.error(f"上传配置详情: {upload_config_data}")
                                logger.error(f"用户ID: {user_id}")
                                logger.error("可能的问题:")
                                logger.error("1. 用户ID不存在或无权限")
                                logger.error("2. 数据集ID无效")
                                logger.error("3. 文件格式不支持")
                                logger.error("4. 配置参数格式错误")
                                logger.error("5. API密钥权限不足")
                                raise last_exception
                
                except Exception as e:
                    if isinstance(e, DifyKnowledgeBaseError):
                        # 如果不是最后一次尝试，记录错误并继续
                        if attempt_idx < len(upload_attempts):
                            logger.warning(f"尝试 {attempt['name']} 出现异常: {e}")
                            last_exception = e
                            continue
                        else:
                            raise e
                    else:
                        # 非预期错误，立即抛出
                        raise e
            
            # 如果到这里还没有response_data，说明所有尝试都失败了
            if response_data is None:
                if last_exception:
                    raise last_exception
                else:
                    raise DocumentUploadError(str(file_path), "所有上传格式都失败了")
            
            # 创建文档模型
            document = DifyDocumentModel(
                dify_document_id=response_data['document']['id'],
                dify_dataset_id=dataset_id,
                name=doc_name,
                data_source_type='upload_file',
                file_name=file_path.name,
                file_type=file_path.suffix,
                file_size=file_size,
                mime_type=mime_type,
                local_file_path=str(file_path),
                status=DocumentStatus.PROCESSING.value,
                indexing_technique=config.indexing_technique.value,
                process_rule=config.process_rule.to_dict()
            )
            
            logger.info(f"Uploaded file document: {doc_name} to dataset {dataset_id}")
            return document
            
        except Exception as e:
            if isinstance(e, DifyKnowledgeBaseError):
                raise
            raise DocumentUploadError(str(file_path), str(e))
    
    def get_document(self, dataset_id: str, document_id: str) -> DifyDocumentModel:
        """
        获取文档信息
        
        Args:
            dataset_id: 知识库ID
            document_id: 文档ID
            
        Returns:
            文档模型
        """
        try:
            logger.debug(f"获取文档信息: dataset_id={dataset_id}, document_id={document_id}")
            response = self._make_request(
                'GET', 
                f'datasets/{dataset_id}/documents/{document_id}'
            )
            
            logger.debug(f"文档信息响应: {response}")
            
            # 检查响应结构 - API 直接返回文档数据，不嵌套在 document 字段下
            if 'id' not in response:
                logger.error(f"响应中缺少id字段: {response}")
                raise DifyKnowledgeBaseError(f"Invalid response format: missing 'id' field")
            
            doc_data = response
            document = DifyDocumentModel(
                dify_document_id=doc_data['id'],
                dify_dataset_id=dataset_id,
                name=doc_data['name'],
                data_source_type=doc_data.get('data_source_type', ''),
                character_count=doc_data.get('character_count', 0),
                word_count=doc_data.get('word_count', 0),
                tokens=doc_data.get('tokens', 0),
                status=doc_data.get('display_status', ''),  # 使用 display_status 字段
                indexing_status=doc_data.get('indexing_status', ''),
                segment_count=doc_data.get('segment_count', 0),
                hit_count=doc_data.get('hit_count', 0),
                processing_started_at=self._parse_timestamp(doc_data.get('created_at')),  # 使用 created_at
                processing_completed_at=self._parse_timestamp(doc_data.get('completed_at'))  # 使用 completed_at
            )
            
            logger.info(f"成功获取文档信息: {document.name}")
            return document
            
        except DifyKnowledgeBaseError as e:
            logger.error(f"获取文档失败 - Dify错误: {e}")
            raise
        except Exception as e:
            logger.error(f"获取文档失败 - 未知错误: {e}")
            raise DocumentNotFoundError(document_id, dataset_id)
    
    def list_documents(
        self, 
        dataset_id: str, 
        page: int = 1, 
        limit: int = 20
    ) -> List[DifyDocumentModel]:
        """
        列出文档
        
        Args:
            dataset_id: 知识库ID
            page: 页码
            limit: 每页数量
            
        Returns:
            文档列表
        """
        try:
            response = self._make_request(
                'GET', 
                f'datasets/{dataset_id}/documents?page={page}&limit={limit}'
            )
            
            documents = []
            for item in response.get('data', []):
                document = DifyDocumentModel(
                    dify_document_id=item['id'],
                    dify_dataset_id=dataset_id,
                    name=item['name'],
                    data_source_type=item.get('data_source_type', ''),
                    character_count=item.get('character_count', 0),
                    word_count=item.get('word_count', 0),
                    tokens=item.get('tokens', 0),
                    status=item.get('status', ''),
                    indexing_status=item.get('indexing_status', ''),
                    segment_count=item.get('segment_count', 0),
                    hit_count=item.get('hit_count', 0)
                )
                documents.append(document)
            
            return documents
            
        except Exception as e:
            if isinstance(e, DifyKnowledgeBaseError):
                raise
            raise DifyKnowledgeBaseError(f"Failed to list documents: {str(e)}")
    
    def delete_document(self, dataset_id: str, document_id: str) -> bool:
        """
        删除文档
        
        Args:
            dataset_id: 知识库ID
            document_id: 文档ID
            
        Returns:
            是否成功删除
        """
        try:
            self._make_request('DELETE', f'datasets/{dataset_id}/documents/{document_id}')
            logger.info(f"Deleted document: {document_id} from dataset {dataset_id}")
            return True
            
        except Exception as e:
            if isinstance(e, DifyKnowledgeBaseError):
                raise
            raise DifyKnowledgeBaseError(f"Failed to delete document {document_id}: {str(e)}")
    
    # ============= 分片管理 API =============
    
    def get_document_segments(
        self, 
        dataset_id: str, 
        document_id: str
    ) -> List[DifySegmentModel]:
        """
        获取文档分片
        
        Args:
            dataset_id: 知识库ID
            document_id: 文档ID
            
        Returns:
            分片列表
        """
        try:
            response = self._make_request(
                'GET', 
                f'datasets/{dataset_id}/documents/{document_id}/segments'
            )
            
            segments = []
            for item in response.get('data', []):
                segment = DifySegmentModel(
                    dify_segment_id=item['id'],
                    dify_document_id=document_id,
                    content=item.get('content', ''),
                    answer=item.get('answer', ''),
                    word_count=item.get('word_count', 0),
                    tokens=item.get('tokens', 0),
                    position=item.get('position', 0),
                    status=item.get('status', ''),
                    enabled=item.get('enabled', True),
                    hit_count=item.get('hit_count', 0),
                    keywords=item.get('keywords', [])
                )
                segments.append(segment)
            
            return segments
            
        except Exception as e:
            if isinstance(e, DifyKnowledgeBaseError):
                raise
            raise DifyKnowledgeBaseError(f"Failed to get document segments: {str(e)}")
    
    def add_segment(
        self,
        dataset_id: str,
        document_id: str,
        content: str,
        answer: str = "",
        keywords: Optional[List[str]] = None
    ) -> DifySegmentModel:
        """
        添加文档分片
        
        Args:
            dataset_id: 知识库ID
            document_id: 文档ID
            content: 分片内容
            answer: 答案内容
            keywords: 关键词
            
        Returns:
            创建的分片模型
        """
        try:
            data = {
                "content": content,
                "answer": answer,
                "keywords": keywords or []
            }
            
            response = self._make_request(
                'POST',
                f'datasets/{dataset_id}/documents/{document_id}/segments',
                data=data
            )
            
            segment = DifySegmentModel(
                dify_segment_id=response['segment']['id'],
                dify_document_id=document_id,
                content=content,
                answer=answer,
                keywords=keywords or [],
                status='completed',
                enabled=True
            )
            
            logger.info(f"Added segment to document {document_id}")
            return segment
            
        except Exception as e:
            if isinstance(e, DifyKnowledgeBaseError):
                raise
            raise SegmentError("new", "add", str(e))
    
    # ============= 查询功能 =============
    
    def query_dataset(
        self,
        dataset_id: str,
        query: str,
        retrieval_model: Optional[Dict] = None,
        top_k: int = 5
    ) -> Dict[str, Any]:
        """
        查询知识库
        
        Args:
            dataset_id: 知识库ID
            query: 查询内容
            retrieval_model: 检索模型配置
            top_k: 返回结果数量
            
        Returns:
            查询结果
        """
        try:
            # 注意：这个API端点可能需要根据实际Dify版本调整
            data = {
                "query": query,
                "retrieval_model": retrieval_model or {},
                "top_k": top_k
            }
            
            response = self._make_request(
                'POST',
                f'datasets/{dataset_id}/query',
                data=data
            )
            
            return response
            
        except Exception as e:
            if isinstance(e, DifyKnowledgeBaseError):
                raise
            raise QueryError(query, str(e))
    
    # ============= 批量操作 =============
    
    def batch_upload_texts(
        self,
        dataset_id: str,
        documents: List[Tuple[str, str]],  # (name, content)
        upload_config: Optional[UploadConfig] = None
    ) -> List[DifyDocumentModel]:
        """
        批量上传文本文档
        
        Args:
            dataset_id: 知识库ID
            documents: 文档列表 (名称, 内容)
            upload_config: 上传配置
            
        Returns:
            上传的文档列表
        """
        results = []
        errors = []
        
        for name, content in documents:
            try:
                doc = self.upload_document_text(dataset_id, name, content, upload_config)
                results.append(doc)
                
                # 批量间隔
                time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Failed to upload document {name}: {str(e)}")
                errors.append((name, str(e)))
        
        if errors and not results:
            raise DocumentUploadError(
                "batch", 
                f"All uploads failed. Errors: {errors}"
            )
        
        return results
    
    def batch_upload_files(
        self,
        dataset_id: str,
        file_paths: List[str],
        upload_config: Optional[UploadConfig] = None
    ) -> List[DifyDocumentModel]:
        """
        批量上传文件
        
        Args:
            dataset_id: 知识库ID
            file_paths: 文件路径列表
            upload_config: 上传配置
            
        Returns:
            上传的文档列表
        """
        results = []
        errors = []
        
        for file_path in file_paths:
            try:
                doc = self.upload_document_file(dataset_id, file_path, upload_config=upload_config)
                results.append(doc)
                
                # 批量间隔
                time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Failed to upload file {file_path}: {str(e)}")
                errors.append((file_path, str(e)))
        
        if errors and not results:
            raise DocumentUploadError(
                "batch", 
                f"All uploads failed. Errors: {errors}"
            )
        
        return results
    
    # ============= 辅助方法 =============
    
    def _update_cache(self, dataset_id: str, dataset: DifyDatasetModel):
        """更新缓存"""
        if self.config.enable_local_cache:
            self._dataset_cache[dataset_id] = dataset
            self._cache_timestamps[dataset_id] = time.time()
    
    def _is_cache_valid(self, dataset_id: str) -> bool:
        """检查缓存是否有效"""
        if not self.config.enable_local_cache:
            return False
        
        if dataset_id not in self._dataset_cache:
            return False
        
        timestamp = self._cache_timestamps.get(dataset_id, 0)
        return (time.time() - timestamp) < self.config.cache_ttl_seconds
    
    def _parse_timestamp(self, timestamp_str: Optional[str]) -> Optional[datetime]:
        """解析时间戳字符串"""
        if not timestamp_str:
            return None
        
        try:
            return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        except Exception:
            return None
    
    def _validate_upload_requirements(self, dataset_id: str) -> Dict[str, Any]:
        """
        验证上传所需的参数和权限
        
        Args:
            dataset_id: 数据集ID
            
        Returns:
            验证结果和建议
        """
        issues = []
        suggestions = []
        
        # 检查API密钥
        if not self.config.api_key:
            issues.append("API密钥未设置")
            suggestions.append("设置环境变量 DIFY_KB_API_KEY")
        
        # 检查数据集ID格式
        if not dataset_id or len(dataset_id) < 10:
            issues.append("数据集ID格式可能不正确")
            suggestions.append("确认数据集ID是有效的UUID格式")
        
        # 检查用户ID
        if not self.config.user_id or self.config.user_id == "homesystem-default-user":
            issues.append("使用默认用户ID，可能导致权限问题")
            suggestions.append("设置环境变量 DIFY_KB_USER_ID 为有效的用户ID")
        
        # 检查基础URL
        if 'localhost' in self.config.base_url or '127.0.0.1' in self.config.base_url:
            suggestions.append("使用本地URL，确保Dify服务正在运行")
        
        return {
            'has_issues': len(issues) > 0,
            'issues': issues,
            'suggestions': suggestions
        }
    
    def _sanitize_document_name(self, name: str) -> str:
        """
        清理文档名称，移除可能导致API调用失败的特殊字符
        
        Args:
            name: 原始文档名称
            
        Returns:
            清理后的文档名称
        """
        if not name:
            return 'document'
        
        import re
        
        # 确保name是字符串并移除换行符和控制字符
        name = str(name).strip()
        name = re.sub(r'[\r\n\t\v\f]', ' ', name)  # 替换换行符和控制字符为空格
        name = re.sub(r'\s+', ' ', name)  # 压缩多个空格为单个空格
        
        # 移除或替换可能导致问题的字符
        # 保留中文字符、英文字符、数字、常见标点符号
        unsafe_chars = r'[/\\:*?"<>|\x00-\x1f\x7f-\x9f]'
        clean_name = re.sub(unsafe_chars, '_', name)
        
        # 移除开头和结尾的空格、点号和下划线
        clean_name = clean_name.strip('. _')
        
        # 移除连续的下划线并替换为单个下划线
        clean_name = re.sub(r'_+', '_', clean_name)
        
        # 如果清理后为空，使用默认名称
        if not clean_name or clean_name == '_':
            clean_name = 'document'
        
        # 限制长度（Dify通常限制在255字符内）
        max_length = 200
        if len(clean_name.encode('utf-8')) > max_length:
            # 按字节长度截断，确保不破坏UTF-8字符
            encoded = clean_name.encode('utf-8')[:max_length]
            while len(encoded) > 0:
                try:
                    clean_name = encoded.decode('utf-8')
                    break
                except UnicodeDecodeError:
                    encoded = encoded[:-1]
            
            # 移除末尾的空格、点号和下划线
            clean_name = clean_name.rstrip('. _')
        
        # 最终检查
        if not clean_name:
            clean_name = 'document'
        
        return clean_name
    
    def get_client_info(self) -> Dict[str, Any]:
        """获取客户端信息"""
        return {
            "base_url": self.config.base_url,
            "cache_enabled": self.config.enable_local_cache,
            "cached_datasets": len(self._dataset_cache),
            "supported_file_types": [ft.value for ft in self.config.supported_file_types],
            "max_file_size_mb": self.config.max_file_size_mb,
            "batch_size": self.config.batch_size
        }
    
    def health_check(self) -> bool:
        """健康检查"""
        try:
            self.list_datasets(limit=1)
            return True
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return False