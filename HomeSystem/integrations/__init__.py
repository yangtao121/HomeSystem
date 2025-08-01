# Home System 集成模块
"""
Home System 集成模块

提供各种外部系统的集成支持:
- database: 数据库集成 (PostgreSQL + Redis)
- dify: Dify AI 平台集成
- paperless: Paperless 文档管理集成
- siyuan: SiYuan 笔记系统集成
"""

__version__ = "1.0.0"

# 导入数据库模块
from . import database

# 公开的模块
__all__ = [
    "database",
]