"""
Ollama模型管理工具模块

提供Ollama模型查询和配置更新功能：
- 查询本地Ollama服务的可用模型
- 过滤符合参数要求的模型（3B以上）
- 更新llm_providers.yaml配置文件
- 保持配置文件结构和完整性
"""

from .model_manager import OllamaModelManager
from .config_updater import ConfigUpdater

__all__ = ['OllamaModelManager', 'ConfigUpdater']