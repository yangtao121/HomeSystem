"""
论文分析工具模块

基于LLM的并行结构化论文分析工具，每个工具专门提取特定字段组。
"""
import json
from typing import Dict, Any, List, Type
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field


class PaperAnalysisInput(BaseModel):
    """论文分析工具输入模型"""
    paper_text: str = Field(description="OCR处理后的英文论文全文")


class BackgroundObjectivesTool(BaseTool):
    """研究背景和目标提取工具"""
    
    name: str = "background_objectives_tool"
    description: str = "Extract research background and objectives from academic papers"
    args_schema: Type[BaseModel] = PaperAnalysisInput
    llm: Any = Field(default=None, exclude=True)
    
    def __init__(self, llm, **kwargs):
        super().__init__(**kwargs)
        object.__setattr__(self, 'llm', llm)
    
    def _get_background_objectives_prompt(self, paper_text: str) -> str:
        """获取背景和目标提取提示词"""
        return f"""
You are an expert at analyzing academic papers. Please carefully read the following English academic paper and extract the research background and objectives.

**Paper Text:**
{paper_text}

**Task:** Extract the following 2 components:

1. **Research Background**: Summarize the research background, including:
   - The problem context and motivation
   - Existing work and current state of the field
   - Gaps or limitations in current approaches
   - Why this research is needed

2. **Research Objectives**: Clearly state the main research objectives, including:
   - Primary research goals or questions
   - What the paper aims to achieve
   - Specific problems the research addresses
   - Expected contributions or outcomes

**Guidelines:**
- Provide comprehensive and detailed analysis for each field
- Focus on accuracy and completeness
- Use clear, professional language
- Extract information directly from the paper content
- Ensure substantial content (not just brief phrases)

**Output Format:** Provide your result in the following exact JSON format:
```json
{{
  "research_background": "Comprehensive research background description including problem context, existing work, and motivation",
  "research_objectives": "Clear statement of research objectives, goals, and what the paper aims to achieve"
}}
```
"""
    
    def _run(self, paper_text: str) -> str:
        """提取背景和目标"""
        try:
            prompt = self._get_background_objectives_prompt(paper_text)
            response = self.llm.invoke(prompt)
            content = response.content if hasattr(response, 'content') else str(response)
            
            # 提取JSON结果
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            
            if json_start != -1 and json_end != -1:
                json_str = content[json_start:json_end]
                try:
                    result = json.loads(json_str)
                    return json.dumps(result, indent=2, ensure_ascii=False)
                except json.JSONDecodeError:
                    return content
            else:
                return content
                
        except Exception as e:
            return f"背景和目标提取过程中发生错误: {str(e)}"


class MethodsFindingsTool(BaseTool):
    """方法和发现提取工具"""
    
    name: str = "methods_findings_tool"
    description: str = "Extract research methods and key findings from academic papers"
    args_schema: Type[BaseModel] = PaperAnalysisInput
    llm: Any = Field(default=None, exclude=True)
    
    def __init__(self, llm, **kwargs):
        super().__init__(**kwargs)
        object.__setattr__(self, 'llm', llm)
    
    def _get_methods_findings_prompt(self, paper_text: str) -> str:
        """获取方法和发现提取提示词"""
        return f"""
You are an expert at analyzing academic research methodology and results. Please carefully read the following English academic paper and extract the research methods and key findings.

**Paper Text:**
{paper_text}

**Task:** Extract the following 2 components:

1. **Methods**: Describe the research methodology, including:
   - Experimental design and approach
   - Algorithms, techniques, or procedures used
   - Data collection and analysis methods
   - Tools, frameworks, or platforms utilized
   - Evaluation metrics and criteria

2. **Key Findings**: Summarize the main research results, including:
   - Primary experimental results and outcomes
   - Performance metrics and measurements
   - Significant discoveries or insights
   - Quantitative and qualitative results
   - Comparative analysis results

**Guidelines:**
- Provide specific technical details where available
- Include quantitative results and metrics when mentioned
- Focus on the most significant and novel findings
- Ensure methods description is comprehensive enough for understanding
- Extract information directly from the paper content

**Output Format:** Provide your result in the following exact JSON format:
```json
{{
  "methods": "Detailed description of research methodology, experimental design, algorithms, and evaluation approaches",
  "key_findings": "Comprehensive summary of main research results, performance metrics, and significant discoveries"
}}
```
"""
    
    def _run(self, paper_text: str) -> str:
        """提取方法和发现"""
        try:
            prompt = self._get_methods_findings_prompt(paper_text)
            response = self.llm.invoke(prompt)
            content = response.content if hasattr(response, 'content') else str(response)
            
            # 提取JSON结果
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            
            if json_start != -1 and json_end != -1:
                json_str = content[json_start:json_end]
                try:
                    result = json.loads(json_str)
                    return json.dumps(result, indent=2, ensure_ascii=False)
                except json.JSONDecodeError:
                    return content
            else:
                return content
                
        except Exception as e:
            return f"方法和发现提取过程中发生错误: {str(e)}"


class ConclusionsFutureTool(BaseTool):
    """结论和未来工作提取工具"""
    
    name: str = "conclusions_future_tool"
    description: str = "Extract conclusions, limitations, and future work from academic papers"
    args_schema: Type[BaseModel] = PaperAnalysisInput
    llm: Any = Field(default=None, exclude=True)
    
    def __init__(self, llm, **kwargs):
        super().__init__(**kwargs)
        object.__setattr__(self, 'llm', llm)
    
    def _get_conclusions_future_prompt(self, paper_text: str) -> str:
        """获取结论和未来工作提取提示词"""
        return f"""
You are an expert at analyzing academic conclusions and research directions. Please carefully read the following English academic paper and extract the conclusions, limitations, and future work.

**Paper Text:**
{paper_text}

**Task:** Extract the following 3 components:

1. **Conclusions**: Extract the conclusions drawn by the authors, including:
   - Main contributions to the field
   - Significance and impact of the work
   - Key insights and implications
   - Overall assessment of the research outcomes

2. **Limitations**: Identify any limitations, constraints, or weaknesses, including:
   - Methodological limitations
   - Scope constraints
   - Data limitations
   - Technical constraints
   - Acknowledged weaknesses by authors

3. **Future Work**: Extract suggestions for future research directions, including:
   - Recommended next steps
   - Areas for improvement
   - Unexplored directions
   - Potential extensions
   - Suggested follow-up research

**Guidelines:**
- Be comprehensive and specific
- Include both explicitly stated and implied limitations
- Focus on actionable future work suggestions
- Ensure professional academic language
- Extract information directly from the paper content

**Output Format:** Provide your result in the following exact JSON format:
```json
{{
  "conclusions": "Comprehensive summary of conclusions, contributions, and significance of the work",
  "limitations": "Detailed identification of research limitations and constraints",
  "future_work": "Specific suggestions for future research directions and improvements"
}}
```
"""
    
    def _run(self, paper_text: str) -> str:
        """提取结论和未来工作"""
        try:
            prompt = self._get_conclusions_future_prompt(paper_text)
            response = self.llm.invoke(prompt)
            content = response.content if hasattr(response, 'content') else str(response)
            
            # 提取JSON结果
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            
            if json_start != -1 and json_end != -1:
                json_str = content[json_start:json_end]
                try:
                    result = json.loads(json_str)
                    return json.dumps(result, indent=2, ensure_ascii=False)
                except json.JSONDecodeError:
                    return content
            else:
                return content
                
        except Exception as e:
            return f"结论和未来工作提取过程中发生错误: {str(e)}"


class KeywordsSynthesisTool(BaseTool):
    """关键词合成工具 - 从已提取的其他字段中生成关键词"""
    
    name: str = "keywords_synthesis_tool"
    description: str = "Synthesize keywords from extracted paper analysis fields"
    
    class KeywordsSynthesisInput(BaseModel):
        research_background: str = Field(description="研究背景")
        research_objectives: str = Field(description="研究目标")
        methods: str = Field(description="研究方法")
        key_findings: str = Field(description="主要发现")
        conclusions: str = Field(description="结论")
    
    args_schema: Type[BaseModel] = KeywordsSynthesisInput
    llm: Any = Field(default=None, exclude=True)
    
    def __init__(self, llm, **kwargs):
        super().__init__(**kwargs)
        object.__setattr__(self, 'llm', llm)
    
    def _get_keywords_synthesis_prompt(self, research_background: str, research_objectives: str, 
                                     methods: str, key_findings: str, conclusions: str) -> str:
        """获取关键词合成提示词"""
        return f"""
You are an expert at synthesizing keywords from academic paper analysis. Based on the following extracted information from an academic paper, generate 3-8 most relevant keywords.

**Extracted Information:**

**Research Background:**
{research_background}

**Research Objectives:**
{research_objectives}

**Methods:**
{methods}

**Key Findings:**
{key_findings}

**Conclusions:**
{conclusions}

**Task:** Based on the above information, extract 3-8 most relevant keywords or key phrases that best represent the main topics, methods, concepts, or techniques in this paper.

**Guidelines:**
- Focus on technical terms, methodologies, domain-specific concepts mentioned in the analysis
- Include both general field terms and specific technique names
- Prioritize terms that appear across multiple sections
- Avoid overly generic words like "analysis", "study", "research" unless they're part of a specific term
- Prefer noun phrases over single words when appropriate
- Ensure keywords capture the paper's core contributions and methodology

**Output Format:** Provide your result in the following exact JSON format:
```json
{{
  "keywords": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5"]
}}
```
"""
    
    def _run(self, research_background: str, research_objectives: str, methods: str, 
            key_findings: str, conclusions: str) -> str:
        """从已提取字段合成关键词"""
        try:
            prompt = self._get_keywords_synthesis_prompt(
                research_background, research_objectives, methods, key_findings, conclusions
            )
            response = self.llm.invoke(prompt)
            content = response.content if hasattr(response, 'content') else str(response)
            
            # 提取JSON结果
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            
            if json_start != -1 and json_end != -1:
                json_str = content[json_start:json_end]
                try:
                    result = json.loads(json_str)
                    return json.dumps(result, indent=2, ensure_ascii=False)
                except json.JSONDecodeError:
                    return content
            else:
                return content
                
        except Exception as e:
            return f"关键词合成过程中发生错误: {str(e)}"


def create_paper_analysis_tools(llm):
    """创建论文分析工具集合"""
    return [
        BackgroundObjectivesTool(llm),
        MethodsFindingsTool(llm),
        ConclusionsFutureTool(llm),
        KeywordsSynthesisTool(llm)
    ]