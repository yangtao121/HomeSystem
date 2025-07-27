"""
论文分析工具模块

基于LLM的结构化论文分析工具，用于提取论文的关键信息并进行迭代优化。
"""
import json
from typing import Dict, Any, Optional
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field


class PaperAnalysisInput(BaseModel):
    """论文分析工具输入模型"""
    paper_text: str = Field(description="OCR处理后的英文论文全文")
    iteration_round: int = Field(default=1, description="当前迭代轮次")
    previous_analysis: Optional[Dict[str, Any]] = Field(default=None, description="上一轮分析结果")


class StructuredAnalysisTool(BaseTool):
    """结构化论文分析工具
    
    使用LLM提取论文的8个关键字段：
    - keywords: 关键词列表
    - research_background: 研究背景
    - research_objectives: 研究目标
    - methods: 研究方法
    - key_findings: 主要发现
    - conclusions: 结论和贡献
    - limitations: 研究局限性
    - future_work: 未来工作方向
    """
    
    name: str = "structured_analysis_tool"
    description: str = "Extract structured information from academic papers using LLM analysis"
    args_schema = PaperAnalysisInput
    
    def __init__(self, llm):
        super().__init__()
        self.llm = llm
    
    def _get_analysis_prompt(self, paper_text: str, iteration_round: int = 1) -> str:
        """获取分析提示词"""
        base_prompt = """
You are an expert academic paper analyzer. Please carefully read the following English academic paper and extract structured information according to the specified format.

**Paper Text:**
{paper_text}

**Task:** Extract the following 8 key components from this academic paper:

1. **Keywords**: Extract 3-8 most relevant keywords or key phrases that represent the main topics, methods, or concepts in this paper.

2. **Research Background**: Summarize the research background, including the problem context, motivation, and existing work that led to this research.

3. **Research Objectives**: Clearly state the main research objectives, goals, or research questions that this paper aims to address.

4. **Methods**: Describe the research methodology, experimental design, algorithms, approaches, or techniques used in this study.

5. **Key Findings**: Summarize the main experimental results, discoveries, or key findings presented in the paper.

6. **Conclusions**: Extract the conclusions drawn by the authors, including their contributions to the field and significance of the work.

7. **Limitations**: Identify any limitations, constraints, or weaknesses mentioned by the authors or that you can identify in the study.

8. **Future Work**: Extract any suggestions for future research directions or next steps mentioned by the authors.

**Output Format:** Please provide your analysis in the following exact JSON format:

```json
{{
  "keywords": ["keyword1", "keyword2", "keyword3"],
  "research_background": "研究背景描述",
  "research_objectives": "研究目标",
  "methods": "研究方法详述",
  "key_findings": "主要研究发现",
  "conclusions": "结论和学术贡献",
  "limitations": "研究局限性",
  "future_work": "未来工作方向"
}}
```

**Important Guidelines:**
- Provide comprehensive and detailed analysis for each field
- Focus on accuracy and completeness
- Use clear, professional language
- Ensure each field contains substantial content (not just brief phrases)
- Extract information directly from the paper content
- If certain information is not explicitly mentioned, indicate this appropriately
"""
        
        if iteration_round > 1:
            base_prompt += """
            
**This is iteration round {iteration_round}:** Please review and improve your previous analysis, paying special attention to:
- Completeness: Ensure all fields have comprehensive content
- Accuracy: Verify all extracted information is correct and well-supported
- Clarity: Improve the clarity and precision of descriptions
- Consistency: Ensure consistent terminology and style across all fields
"""
        
        return base_prompt.format(paper_text=paper_text, iteration_round=iteration_round)
    
    def _get_refinement_prompt(self, paper_text: str, previous_analysis: Dict[str, Any]) -> str:
        """获取细化改进提示词"""
        return f"""
You are refining a previous analysis of an academic paper. Please review the original paper text and the previous analysis, then provide an improved version.

**Original Paper Text:**
{paper_text}

**Previous Analysis:**
{json.dumps(previous_analysis, indent=2, ensure_ascii=False)}

**Task:** Please carefully review the previous analysis and improve it by:

1. **Completeness Check**: Ensure all 8 fields have comprehensive and substantial content
2. **Accuracy Verification**: Cross-check all extracted information against the original paper
3. **Content Enhancement**: Add more specific details, examples, or explanations where appropriate
4. **Clarity Improvement**: Enhance the clarity and precision of descriptions
5. **Consistency Check**: Ensure consistent terminology and style across all fields

Pay special attention to:
- Are the keywords truly representative of the paper's main concepts?
- Is the research background comprehensive and well-contextualized?
- Are the research objectives clearly and specifically stated?
- Are the methods described with sufficient technical detail?
- Do the key findings accurately reflect the paper's main results?
- Are the conclusions well-supported and clearly articulated?
- Are the limitations realistic and comprehensive?
- Are the future work directions specific and meaningful?

**Output Format:** Provide the refined analysis in the same JSON format:

```json
{{
  "keywords": ["improved_keyword1", "improved_keyword2", "improved_keyword3"],
  "research_background": "improved research background description",
  "research_objectives": "improved research objectives",
  "methods": "improved methods description",
  "key_findings": "improved key findings",
  "conclusions": "improved conclusions and contributions",
  "limitations": "improved limitations analysis",
  "future_work": "improved future work directions"
}}
```
"""
    
    def _get_quality_assessment_prompt(self, analysis_result: Dict[str, Any]) -> str:
        """获取质量评估提示词"""
        return f"""
You are a quality assessor for academic paper analysis. Please evaluate the following analysis result and provide improvement suggestions.

**Analysis to Evaluate:**
{json.dumps(analysis_result, indent=2, ensure_ascii=False)}

**Evaluation Criteria:**
1. **Completeness** (0-10): Are all 8 fields well-filled with substantial content?
2. **Accuracy** (0-10): Does the content accurately reflect the paper's information?
3. **Clarity** (0-10): Are the descriptions clear and well-articulated?
4. **Specificity** (0-10): Are the descriptions specific rather than generic?
5. **Professional Quality** (0-10): Does the analysis meet academic standards?

**Task:** Please provide:
1. A score for each criterion (0-10)
2. Overall assessment (0-10)
3. Specific improvement suggestions for each field that scores below 8
4. A recommendation: "ACCEPT" (if overall score ≥ 8) or "REFINE" (if overall score < 8)

**Output Format:**
```json
{{
  "scores": {{
    "completeness": 8,
    "accuracy": 9,
    "clarity": 7,
    "specificity": 8,
    "professional_quality": 8
  }},
  "overall_score": 8.0,
  "improvement_suggestions": {{
    "keywords": "suggestion for keywords if needed",
    "research_background": "suggestion for research_background if needed",
    "research_objectives": "suggestion for research_objectives if needed",
    "methods": "suggestion for methods if needed",
    "key_findings": "suggestion for key_findings if needed",
    "conclusions": "suggestion for conclusions if needed",
    "limitations": "suggestion for limitations if needed",
    "future_work": "suggestion for future_work if needed"
  }},
  "recommendation": "ACCEPT or REFINE",
  "overall_feedback": "General feedback and recommendations"
}}
```
"""
    
    def _run(self, paper_text: str, iteration_round: int = 1, previous_analysis: Optional[Dict[str, Any]] = None) -> str:
        """执行论文分析"""
        try:
            if iteration_round == 1 or previous_analysis is None:
                # 第一轮分析
                prompt = self._get_analysis_prompt(paper_text, iteration_round)
            else:
                # 后续轮次使用细化提示词
                prompt = self._get_refinement_prompt(paper_text, previous_analysis)
            
            # 调用LLM进行分析
            response = self.llm.invoke(prompt)
            
            # 尝试提取JSON结果
            content = response.content if hasattr(response, 'content') else str(response)
            
            # 查找JSON块
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            
            if json_start != -1 and json_end != -1:
                json_str = content[json_start:json_end]
                try:
                    result = json.loads(json_str)
                    return json.dumps(result, indent=2, ensure_ascii=False)
                except json.JSONDecodeError:
                    # 如果JSON解析失败，返回原始响应
                    return content
            else:
                return content
                
        except Exception as e:
            return f"分析过程中发生错误: {str(e)}"


class QualityAssessmentTool(BaseTool):
    """质量评估工具"""
    
    name: str = "quality_assessment_tool"
    description: str = "Assess the quality of paper analysis results and provide improvement suggestions"
    
    def __init__(self, llm):
        super().__init__()
        self.llm = llm
    
    def _run(self, analysis_result: str) -> str:
        """执行质量评估"""
        try:
            # 尝试解析分析结果
            if isinstance(analysis_result, str):
                result_dict = json.loads(analysis_result)
            else:
                result_dict = analysis_result
            
            # 构建评估提示词
            structured_tool = StructuredAnalysisTool(self.llm)
            prompt = structured_tool._get_quality_assessment_prompt(result_dict)
            
            # 调用LLM进行评估
            response = self.llm.invoke(prompt)
            content = response.content if hasattr(response, 'content') else str(response)
            
            # 尝试提取JSON结果
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            
            if json_start != -1 and json_end != -1:
                json_str = content[json_start:json_end]
                try:
                    assessment = json.loads(json_str)
                    return json.dumps(assessment, indent=2, ensure_ascii=False)
                except json.JSONDecodeError:
                    return content
            else:
                return content
                
        except Exception as e:
            return f"质量评估过程中发生错误: {str(e)}"


def create_paper_analysis_tools(llm):
    """创建论文分析工具集合"""
    return [
        StructuredAnalysisTool(llm),
        QualityAssessmentTool(llm)
    ]