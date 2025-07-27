"""
Paper Gather Task 模块

提供论文收集和分析功能
"""

from .paper_gather_task import PaperGatherTask
from .llm_config import AbstractAnalysisLLM, AbstractAnalysisResult

__all__ = [
    'PaperGatherTask',
    'AbstractAnalysisLLM', 
    'AbstractAnalysisResult'
]