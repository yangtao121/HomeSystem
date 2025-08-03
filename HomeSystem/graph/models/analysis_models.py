"""
论文分析相关的Pydantic数据模型

定义论文分析过程中使用的结构化数据模型，支持LLM的结构化输出功能。
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional


class ContributionItem(BaseModel):
    """单个贡献项"""
    title: str = Field(description="贡献标题或概要")
    description: str = Field(description="贡献的详细描述")
    significance: str = Field(description="贡献的重要性或影响")
    novelty_score: float = Field(description="创新性评分 (0-1)", ge=0, le=1)


class MethodologySection(BaseModel):
    """方法论章节"""
    approach_name: str = Field(description="方法或技术名称")
    description: str = Field(description="方法的详细描述")
    key_techniques: List[str] = Field(description="关键技术或算法列表")
    advantages: List[str] = Field(description="方法的优势")
    limitations: Optional[List[str]] = Field(description="方法的限制", default=None)


class ExperimentalResult(BaseModel):
    """实验结果项"""
    experiment_name: str = Field(description="实验名称或类型")
    dataset_used: str = Field(description="使用的数据集")
    metrics: List[str] = Field(description="评估指标")
    performance: str = Field(description="性能表现描述")
    comparison: Optional[str] = Field(description="与其他方法的比较", default=None)


class ResearchBackground(BaseModel):
    """研究背景"""
    problem_statement: str = Field(description="研究问题陈述")
    motivation: str = Field(description="研究动机")
    related_work: str = Field(description="相关工作总结")
    research_gap: str = Field(description="研究空白或不足")


class ImageInsight(BaseModel):
    """图片分析洞察"""
    image_type: str = Field(description="图片类型 (diagram/chart/table/figure)")
    content_summary: str = Field(description="图片内容概要")
    key_information: str = Field(description="从图片中提取的关键信息")
    relevance_to_paper: str = Field(description="与论文主题的相关性")


class ComprehensiveAnalysisResult(BaseModel):
    """完整的论文分析结果 - 用于LLM结构化输出"""
    
    # 研究目标和贡献
    research_objectives: str = Field(description="研究目标概述")
    main_contributions: List[ContributionItem] = Field(
        description="主要贡献列表",
        min_items=1,
        max_items=10
    )
    
    # 研究背景
    background_analysis: ResearchBackground = Field(description="研究背景分析")
    
    # 方法论分析
    methodology_analysis: List[MethodologySection] = Field(
        description="方法论分析",
        min_items=1,
        max_items=5
    )
    
    # 实验结果
    experimental_results: List[ExperimentalResult] = Field(
        description="实验结果分析",
        min_items=0,
        max_items=10
    )
    
    # 关键发现
    key_findings: List[str] = Field(
        description="关键发现列表",
        min_items=1,
        max_items=8
    )
    
    # 图片分析结果
    image_insights: Optional[List[ImageInsight]] = Field(
        description="图片分析洞察",
        default=None
    )
    
    # 整体评估
    overall_quality: float = Field(
        description="论文整体质量评分 (0-1)",
        ge=0,
        le=1
    )
    technical_depth: float = Field(
        description="技术深度评分 (0-1)",
        ge=0,
        le=1
    )
    practical_impact: float = Field(
        description="实用价值评分 (0-1)",
        ge=0,
        le=1
    )
    
    # 总结
    summary: str = Field(description="论文整体总结", max_length=500)


class TranslatedAnalysisResult(BaseModel):
    """翻译后的分析结果"""
    
    # 翻译后的主要字段
    research_objectives_zh: str = Field(description="研究目标 (中文)")
    summary_zh: str = Field(description="论文总结 (中文)")
    key_findings_zh: List[str] = Field(description="关键发现 (中文)")
    
    # 翻译后的贡献
    main_contributions_zh: List[Dict[str, str]] = Field(
        description="主要贡献 (中文翻译)"
    )
    
    # 翻译后的背景
    background_analysis_zh: Dict[str, str] = Field(
        description="研究背景 (中文翻译)"
    )
    
    # 翻译后的方法论
    methodology_analysis_zh: List[Dict[str, Any]] = Field(
        description="方法论分析 (中文翻译)"
    )
    
    # 翻译后的实验结果
    experimental_results_zh: List[Dict[str, str]] = Field(
        description="实验结果 (中文翻译)"
    )
    
    # 翻译质量评估
    translation_quality: str = Field(
        description="翻译质量评估 (high/medium/low)"
    )
    translation_notes: Optional[str] = Field(
        description="翻译说明或注意事项",
        default=None
    )


