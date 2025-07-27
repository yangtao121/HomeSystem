# ArXiv 工具模块
"""
ArXiv 学术论文搜索和下载工具

提供基于 ArXiv 官方 API 的论文搜索功能，支持数据库集成。

主要类:
- ArxivTool: 基础 ArXiv 搜索工具
- EnhancedArxivTool: 增强版工具，支持数据库集成
- ArxivData: 单篇论文数据容器
- ArxivResult: 搜索结果容器
- ArxivDatabaseManager: 数据库管理器

使用示例:
    from HomeSystem.utility.arxiv import ArxivTool
    
    arxiv = ArxivTool()
    results = arxiv.arxivSearch("machine learning", num_results=10)
    
    # 使用增强版本（支持数据库）
    from HomeSystem.utility.arxiv import EnhancedArxivTool
    
    enhanced_arxiv = EnhancedArxivTool(enable_database=True)
    results = enhanced_arxiv.arxivSearch("deep learning", skip_processed=True)
"""

from .arxiv import ArxivTool, ArxivData, ArxivResult

# 数据库集成相关导入（暂时禁用）
# 由于路径解析问题，暂时禁用数据库集成功能
# try:
#     from .database_integration import ArxivDatabaseManager
#     DATABASE_AVAILABLE = True
# except Exception:
#     DATABASE_AVAILABLE = False

__all__ = [
    "ArxivTool",
    "ArxivData", 
    "ArxivResult"
]

# 注意：如需数据库集成功能，请确保数据库模块路径正确配置