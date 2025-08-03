"""
深度分析工具集 - 专门用于学术论文的深度内容分析

包含主要贡献分析、方法论分析、实验结果分析等专业工具，
支持结构化输出和英文专业分析。
"""

import json
from typing import Any, Dict, List, Optional, Type
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from loguru import logger

from ..llm_factory import get_llm


class ContributionAnalysisInput(BaseModel):
    """主要贡献分析输入模型"""
    paper_text: str = Field(description="Complete paper text content in markdown format")
    image_insights: Dict[str, Any] = Field(
        description="Insights from image analysis that might relate to contributions",
        default={}
    )


class MethodologyAnalysisInput(BaseModel):
    """方法论分析输入模型"""
    paper_text: str = Field(description="Complete paper text content in markdown format")
    image_insights: Dict[str, Any] = Field(
        description="Architecture diagrams and technical insights from images",
        default={}
    )


class ExperimentalResultsAnalysisInput(BaseModel):
    """实验结果分析输入模型"""
    paper_text: str = Field(description="Complete paper text content in markdown format")
    chart_insights: Dict[str, Any] = Field(
        description="Experimental charts and tables analysis from images",
        default={}
    )


class ContributionAnalysisTool(BaseTool):
    """主要贡献分析工具 - 提取并分析论文的核心贡献"""
    
    name: str = "analyze_contributions"
    description: str = "Extract and analyze the main contributions of an academic paper with detailed breakdown"
    args_schema: Type[BaseModel] = ContributionAnalysisInput
    return_direct: bool = False
    
    # 声明工具属性
    llm: Any = Field(default=None, exclude=True)
    
    def __init__(self, llm_model: str = "deepseek.DeepSeek_V3", **kwargs):
        super().__init__(**kwargs)
        llm = get_llm(llm_model)
        object.__setattr__(self, 'llm', llm)
        logger.info(f"ContributionAnalysisTool initialized with model: {llm_model}")
    
    def _generate_contribution_prompt(self, paper_text: str, image_insights: Dict) -> str:
        """生成贡献分析的专业提示词"""
        return f"""
You are an expert academic reviewer analyzing the main contributions of a research paper. 

**Paper Content:**
{paper_text[:15000]}  # Limit text length for token efficiency

**Image Analysis Insights:**
{json.dumps(image_insights, indent=2) if image_insights else "No image insights available"}

**Task:** Identify and analyze the main contributions of this paper with the following requirements:

1. **Extract Core Contributions**: Identify the primary novel contributions that advance the field
2. **Evaluate Significance**: Assess the importance and impact of each contribution
3. **Technical Innovation**: Highlight specific technical innovations and breakthroughs
4. **Practical Applications**: Identify real-world applications and use cases

**Analysis Requirements:**
- Each contribution should be clearly stated and numbered
- Provide detailed description of what makes each contribution novel
- Assess the technical depth and innovation level
- Consider both theoretical and practical significance
- Use insights from diagrams/charts if available to enhance understanding

**Output Format:** Return a structured JSON response:
```json
{{
    "contributions": [
        {{
            "id": 1,
            "title": "Clear contribution title",
            "description": "Detailed description of the contribution",
            "novelty_aspect": "What makes this contribution novel",
            "significance": "high/medium/low",
            "technical_details": "Specific technical innovations",
            "supporting_evidence": "Evidence from paper/experiments"
        }}
    ],
    "contribution_count": "number of contributions",
    "overall_innovation_level": "high/medium/low",
    "primary_research_area": "main field/domain",
    "impact_assessment": "Overall assessment of potential impact"
}}
```

Provide comprehensive analysis based on the paper content and any architectural insights from images.
"""
    
    def _run(self, paper_text: str, image_insights: Dict[str, Any] = None) -> str:
        """执行贡献分析"""
        try:
            if image_insights is None:
                image_insights = {}
            
            # 生成分析提示词
            prompt = self._generate_contribution_prompt(paper_text, image_insights)
            
            # 调用LLM进行分析
            logger.info("Starting contribution analysis...")
            response = self.llm.invoke(prompt)
            content = response.content if hasattr(response, 'content') else str(response)
            
            # 尝试提取和验证JSON结果
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            
            if json_start != -1 and json_end != -1:
                json_str = content[json_start:json_end]
                try:
                    result = json.loads(json_str)
                    logger.info(f"Contribution analysis completed, found {result.get('contribution_count', 0)} contributions")
                    return json.dumps(result, indent=2, ensure_ascii=False)
                except json.JSONDecodeError as e:
                    logger.warning(f"JSON decode error in contribution analysis: {e}")
                    return content
            else:
                logger.warning("No valid JSON found in contribution analysis response")
                return content
                
        except Exception as e:
            error_msg = f"Contribution analysis failed: {str(e)}"
            logger.error(error_msg)
            return json.dumps({"error": error_msg, "raw_response": ""})


class MethodologyAnalysisTool(BaseTool):
    """方法论分析工具 - 深度分析论文的技术方法和实现"""
    
    name: str = "analyze_methodology"
    description: str = "Perform deep analysis of research methodology with hierarchical structure and technical details"
    args_schema: Type[BaseModel] = MethodologyAnalysisInput
    return_direct: bool = False
    
    # 声明工具属性
    llm: Any = Field(default=None, exclude=True)
    
    def __init__(self, llm_model: str = "deepseek.DeepSeek_V3", **kwargs):
        super().__init__(**kwargs)
        llm = get_llm(llm_model)
        object.__setattr__(self, 'llm', llm)
        logger.info(f"MethodologyAnalysisTool initialized with model: {llm_model}")
    
    def _generate_methodology_prompt(self, paper_text: str, image_insights: Dict) -> str:
        """生成方法论分析的专业提示词"""
        return f"""
You are an expert technical reviewer analyzing the methodology section of a research paper.

**Paper Content:**
{paper_text[:15000]}  # Limit text length for token efficiency

**Architecture/Technical Insights from Images:**
{json.dumps(image_insights, indent=2) if image_insights else "No image insights available"}

**Task:** Perform comprehensive methodology analysis with hierarchical structure:

1. **Overall Approach**: High-level research approach and framework
2. **Technical Methods**: Detailed technical methodologies with subsections
3. **Implementation Details**: Specific implementation approaches and techniques
4. **Evaluation Methodology**: How the approach is evaluated and validated

**Analysis Requirements:**
- Create hierarchical structure with main sections and subsections
- Include technical details and algorithmic approaches
- Integrate insights from architecture diagrams if available
- Explain the reasoning behind methodological choices
- Identify novel methodological contributions
- Assess methodological rigor and validity

**Output Format:** Return a structured JSON response:
```json
{{
    "overall_approach": {{
        "framework": "Description of overall research framework",
        "key_innovations": ["List of methodological innovations"],
        "research_paradigm": "Experimental/theoretical/applied research approach"
    }},
    "technical_methods": {{
        "subsections": [
            {{
                "title": "Subsection title (e.g., 'Model Architecture')",
                "content": "Detailed technical content",
                "key_techniques": ["List of specific techniques used"],
                "novel_aspects": "What is novel in this approach"
            }}
        ]
    }},
    "implementation_details": {{
        "platforms_tools": ["Software/hardware platforms used"],
        "algorithms": ["Key algorithms implemented"],
        "technical_specifications": "Specific technical details",
        "complexity_analysis": "Computational complexity if mentioned"
    }},
    "evaluation_methodology": {{
        "evaluation_approach": "How the method is evaluated",
        "metrics_used": ["Performance metrics and evaluation criteria"],
        "experimental_setup": "Description of experimental configuration",
        "baseline_comparisons": "What baselines are compared against"
    }},
    "methodological_rigor": "high/medium/low",
    "reproducibility_assessment": "Assessment of reproducibility based on provided details"
}}
```

Provide thorough technical analysis integrating both textual content and architectural insights.
"""
    
    def _run(self, paper_text: str, image_insights: Dict[str, Any] = None) -> str:
        """执行方法论分析"""
        try:
            if image_insights is None:
                image_insights = {}
            
            # 生成分析提示词
            prompt = self._generate_methodology_prompt(paper_text, image_insights)
            
            # 调用LLM进行分析
            logger.info("Starting methodology analysis...")
            response = self.llm.invoke(prompt)
            content = response.content if hasattr(response, 'content') else str(response)
            
            # 尝试提取和验证JSON结果
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            
            if json_start != -1 and json_end != -1:
                json_str = content[json_start:json_end]
                try:
                    result = json.loads(json_str)
                    logger.info("Methodology analysis completed successfully")
                    return json.dumps(result, indent=2, ensure_ascii=False)
                except json.JSONDecodeError as e:
                    logger.warning(f"JSON decode error in methodology analysis: {e}")
                    return content
            else:
                logger.warning("No valid JSON found in methodology analysis response")
                return content
                
        except Exception as e:
            error_msg = f"Methodology analysis failed: {str(e)}"
            logger.error(error_msg)
            return json.dumps({"error": error_msg, "raw_response": ""})


class ExperimentalResultsAnalysisTool(BaseTool):
    """实验结果分析工具 - 深度分析实验设计和结果"""
    
    name: str = "analyze_experimental_results"
    description: str = "Analyze experimental design, results, and performance evaluation with quantitative insights"
    args_schema: Type[BaseModel] = ExperimentalResultsAnalysisInput
    return_direct: bool = False
    
    # 声明工具属性
    llm: Any = Field(default=None, exclude=True)
    
    def __init__(self, llm_model: str = "deepseek.DeepSeek_V3", **kwargs):
        super().__init__(**kwargs)
        llm = get_llm(llm_model)
        object.__setattr__(self, 'llm', llm)
        logger.info(f"ExperimentalResultsAnalysisTool initialized with model: {llm_model}")
    
    def _generate_results_prompt(self, paper_text: str, chart_insights: Dict) -> str:
        """生成实验结果分析的专业提示词"""
        return f"""
You are an expert researcher analyzing experimental results and performance evaluation in an academic paper.

**Paper Content:**
{paper_text[:15000]}  # Limit text length for token efficiency

**Chart/Table Analysis from Images:**
{json.dumps(chart_insights, indent=2) if chart_insights else "No chart insights available"}

**Task:** Comprehensive analysis of experimental design and results:

1. **Experimental Design**: Analyze the experimental setup and methodology
2. **Performance Metrics**: Identify and analyze performance measurements
3. **Results Analysis**: Detailed analysis of experimental outcomes
4. **Comparative Analysis**: Compare results with baselines and state-of-the-art

**Analysis Requirements:**
- Extract specific numerical results and performance metrics
- Analyze trends and patterns in the results
- Identify key findings and significant improvements
- Assess the validity and significance of results
- Integrate quantitative data from charts/tables if available
- Evaluate experimental rigor and statistical significance

**Output Format:** Return a structured JSON response:
```json
{{
    "experimental_design": {{
        "datasets_used": ["List of datasets"],
        "experimental_setup": "Description of experimental configuration",
        "evaluation_protocol": "How experiments were conducted",
        "control_measures": "Controls and validation measures used"
    }},
    "performance_metrics": {{
        "primary_metrics": ["Main evaluation metrics"],
        "secondary_metrics": ["Additional metrics measured"],
        "measurement_methodology": "How metrics were calculated"
    }},
    "key_results": {{
        "quantitative_results": [
            {{
                "metric": "Performance metric name",
                "value": "Numerical result",
                "comparison": "Comparison with baseline/SOTA",
                "improvement": "Improvement percentage if available"
            }}
        ],
        "qualitative_findings": ["Key qualitative observations"],
        "significant_achievements": ["Most important results"]
    }},
    "comparative_analysis": {{
        "baselines_compared": ["Baseline methods compared against"],
        "performance_ranking": "How this method ranks against others",
        "statistical_significance": "Whether improvements are statistically significant"
    }},
    "result_validity": {{
        "experimental_rigor": "high/medium/low",
        "reproducibility_indicators": "Evidence for reproducibility",
        "limitations_acknowledged": ["Limitations mentioned by authors"]
    }}
}}
```

Provide detailed quantitative analysis integrating both textual results and visual data from charts/tables.
"""
    
    def _run(self, paper_text: str, chart_insights: Dict[str, Any] = None) -> str:
        """执行实验结果分析"""
        try:
            if chart_insights is None:
                chart_insights = {}
            
            # 生成分析提示词
            prompt = self._generate_results_prompt(paper_text, chart_insights)
            
            # 调用LLM进行分析
            logger.info("Starting experimental results analysis...")
            response = self.llm.invoke(prompt)
            content = response.content if hasattr(response, 'content') else str(response)
            
            # 尝试提取和验证JSON结果
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            
            if json_start != -1 and json_end != -1:
                json_str = content[json_start:json_end]
                try:
                    result = json.loads(json_str)
                    logger.info("Experimental results analysis completed successfully")
                    return json.dumps(result, indent=2, ensure_ascii=False)
                except json.JSONDecodeError as e:
                    logger.warning(f"JSON decode error in results analysis: {e}")
                    return content
            else:
                logger.warning("No valid JSON found in results analysis response")
                return content
                
        except Exception as e:
            error_msg = f"Experimental results analysis failed: {str(e)}"
            logger.error(error_msg)
            return json.dumps({"error": error_msg, "raw_response": ""})


class BackgroundAnalysisTool(BaseTool):
    """背景分析工具 - 分析研究背景和相关工作"""
    
    name: str = "analyze_background"
    description: str = "Analyze research background, motivation, and related work"
    args_schema: Type[BaseModel] = ContributionAnalysisInput  # 复用相同的输入格式
    return_direct: bool = False
    
    # 声明工具属性
    llm: Any = Field(default=None, exclude=True)
    
    def __init__(self, llm_model: str = "deepseek.DeepSeek_V3", **kwargs):
        super().__init__(**kwargs)
        llm = get_llm(llm_model)
        object.__setattr__(self, 'llm', llm)
        logger.info(f"BackgroundAnalysisTool initialized with model: {llm_model}")
    
    def _generate_background_prompt(self, paper_text: str, image_insights: Dict) -> str:
        """生成背景分析的专业提示词"""
        return f"""
You are an expert academic reviewer analyzing the research background and motivation of a paper.

**Paper Content:**
{paper_text[:15000]}

**Image Insights:**
{json.dumps(image_insights, indent=2) if image_insights else "No image insights available"}

**Task:** Analyze research background, motivation, and positioning:

1. **Problem Context**: What problem does this research address?
2. **Research Motivation**: Why is this research important and timely?
3. **Related Work**: How does this work relate to existing research?
4. **Research Gap**: What gaps in current knowledge does this address?

**Output Format:**
```json
{{
    "problem_context": {{
        "domain": "Research domain/field",
        "problem_statement": "Clear statement of the problem being addressed",
        "problem_significance": "Why this problem is important"
    }},
    "research_motivation": {{
        "driving_factors": ["Key factors motivating this research"],
        "current_limitations": ["Limitations in existing approaches"],
        "opportunity_identified": "Research opportunity identified"
    }},
    "related_work": {{
        "key_prior_work": ["Important previous research mentioned"],
        "research_evolution": "How the field has evolved",
        "positioning": "How this work positions itself relative to others"
    }},
    "research_gap": {{
        "identified_gaps": ["Specific gaps in current knowledge/technology"],
        "novel_aspects": ["What makes this research novel"],
        "research_questions": ["Key research questions being addressed"]
    }}
}}
```
"""
    
    def _run(self, paper_text: str, image_insights: Dict[str, Any] = None) -> str:
        """执行背景分析"""
        try:
            if image_insights is None:
                image_insights = {}
            
            prompt = self._generate_background_prompt(paper_text, image_insights)
            
            logger.info("Starting background analysis...")
            response = self.llm.invoke(prompt)
            content = response.content if hasattr(response, 'content') else str(response)
            
            # 提取JSON结果
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            
            if json_start != -1 and json_end != -1:
                json_str = content[json_start:json_end]
                try:
                    result = json.loads(json_str)
                    logger.info("Background analysis completed successfully")
                    return json.dumps(result, indent=2, ensure_ascii=False)
                except json.JSONDecodeError as e:
                    logger.warning(f"JSON decode error in background analysis: {e}")
                    return content
            else:
                return content
                
        except Exception as e:
            error_msg = f"Background analysis failed: {str(e)}"
            logger.error(error_msg)
            return json.dumps({"error": error_msg})


def create_analysis_tools(llm_model: str = "deepseek.DeepSeek_V3") -> List[BaseTool]:
    """
    创建完整的深度分析工具集
    
    Args:
        llm_model: 使用的LLM模型名称
        
    Returns:
        List[BaseTool]: 分析工具列表
    """
    return [
        ContributionAnalysisTool(llm_model),
        MethodologyAnalysisTool(llm_model),
        ExperimentalResultsAnalysisTool(llm_model),
        BackgroundAnalysisTool(llm_model)
    ]


# 测试代码
if __name__ == "__main__":
    # 测试工具创建
    tools = create_analysis_tools()
    print(f"Created {len(tools)} analysis tools:")
    for tool in tools:
        print(f"  - {tool.name}: {tool.description}")