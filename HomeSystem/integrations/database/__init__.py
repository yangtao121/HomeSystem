# Home System 数据库集成包
"""
Home System 数据库集成模块

提供统一的数据库访问接口，支持 PostgreSQL 和 Redis。
包含连接管理、数据模型、操作接口等核心功能。

主要组件:
- DatabaseManager: 数据库连接管理
- BaseModel: 数据模型基类  
- ArxivPaperModel: ArXiv论文数据模型
- DatabaseOperations: PostgreSQL操作接口
- CacheOperations: Redis缓存操作接口

使用示例:
    from HomeSystem.integrations.database import DatabaseOperations, ArxivPaperModel
    
    db_ops = DatabaseOperations()
    paper = ArxivPaperModel(arxiv_id="2301.12345", title="Test Paper")
    success = db_ops.create(paper)
"""

__version__ = "1.0.0"
__author__ = "Home System Team"

# 导入主要类和函数
from .connection import (
    DatabaseManager, 
    get_database_manager, 
    close_all_connections, 
    check_database_health
)

from .models import (
    BaseModel,
    ArxivPaperModel,
    UserModel
)

from .operations import (
    DatabaseOperations,
    CacheOperations
)

# 公开的API
__all__ = [
    # 连接管理
    "DatabaseManager",
    "get_database_manager", 
    "close_all_connections",
    "check_database_health",
    
    # 数据模型
    "BaseModel",
    "ArxivPaperModel", 
    "UserModel",
    
    # 操作接口
    "DatabaseOperations",
    "CacheOperations",
]