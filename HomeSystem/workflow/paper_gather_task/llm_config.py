import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))
from HomeSystem.graph.llm_factory import llm_factory
from pydantic import BaseModel, Field
from loguru import logger
from typing import cast


class AbstractAnalysisResult(BaseModel):
    """Paper abstract preliminary analysis result"""
    is_relevant: bool = Field(description="Whether the abstract is relevant to user requirements")
    relevance_score: float = Field(description="Relevance score (0-1)", ge=0, le=1)
    justification: str = Field(description="Brief reasoning for the preliminary judgment")


class FullAnalysisResult(BaseModel):
    """Full paper analysis result"""
    is_relevant: bool = Field(description="Whether the full paper is relevant to user requirements")
    relevance_score: float = Field(description="Relevance score (0-1)", ge=0, le=1)
    justification: str = Field(description="Detailed reasoning for the full paper analysis")


class AbstractAnalysisLLM:
    """Paper abstract preliminary analysis LLM"""
    
    def __init__(self, model_name: str = "ollama.Qwen3_30B"):
        self.model_name = model_name
        self.system_prompt = """You are a paper screening assistant responsible for quickly analyzing the relevance between paper abstracts and user requirements.

This is the preliminary screening stage. Please quickly determine:
1. Whether the abstract topic matches the user requirements
2. Whether the research content is relevant
3. Provide a concise judgment reasoning

IMPORTANT: The relevance_score MUST be a decimal number between 0.0 and 1.0 (e.g., 0.85, 0.92, 0.15).
- 0.0 = completely irrelevant
- 0.5 = moderately relevant  
- 1.0 = extremely relevant

Do NOT use scores like 85, 9, or any number greater than 1.0.

Please make a quick and accurate preliminary judgment based on the abstract content."""
        
        # Create LLM instance
        self.base_llm = llm_factory.create_llm(model_name=model_name)
        self.structured_llm = self.base_llm.with_structured_output(AbstractAnalysisResult)
        
        logger.info(f"Initialized abstract analysis LLM: {model_name}")
    
    def analyze_abstract(self, abstract: str, user_requirements: str) -> AbstractAnalysisResult:
        """Analyze a single paper abstract"""
        prompt = f"""User Requirements: {user_requirements}

Paper Abstract: {abstract}

Please quickly determine whether this abstract is relevant to the user requirements.

Remember: relevance_score must be between 0.0 and 1.0 (decimal format, not percentage)."""
        
        try:
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt}
            ]
            
            result = self.structured_llm.invoke(messages)
            return cast(AbstractAnalysisResult, result)
            
        except Exception as e:
            logger.error(f"Abstract analysis failed: {e}")
            return AbstractAnalysisResult(
                is_relevant=False,
                relevance_score=0.0,
                justification=f"Analysis error: {str(e)}"
            )


class FullPaperAnalysisLLM:
    """Full paper analysis LLM for detailed analysis"""
    
    def __init__(self, model_name: str = "ollama.Qwen3_30B"):
        self.model_name = model_name
        self.system_prompt = """You are an expert paper analysis assistant responsible for conducting detailed analysis of complete academic papers against user requirements.

This is the comprehensive analysis stage. Please thoroughly evaluate:
1. Whether the paper's research objectives align with user requirements
2. Whether the methodology and approach are relevant
3. Whether the results and conclusions meet user needs
4. The overall quality and relevance of the paper

Consider the full paper content including:
- Introduction and background
- Methodology and experimental design
- Results and findings
- Discussion and conclusions
- References and related work

IMPORTANT: The relevance_score MUST be a decimal number between 0.0 and 1.0 (e.g., 0.85, 0.92, 0.15).
- 0.0 = completely irrelevant
- 0.5 = moderately relevant  
- 1.0 = extremely relevant

Do NOT use scores like 85, 9, or any number greater than 1.0.

Provide detailed justification based on the full paper analysis.
NOTE: Only analyze papers in English."""
        
        # Create LLM instance
        self.base_llm = llm_factory.create_llm(model_name=model_name)
        self.structured_llm = self.base_llm.with_structured_output(FullAnalysisResult)
        
        logger.info(f"Initialized full paper analysis LLM: {model_name}")
    
    def analyze_full_paper(self, paper_content: str, user_requirements: str) -> FullAnalysisResult:
        """Analyze a complete paper content"""
        prompt = f"""User Requirements: {user_requirements}

Full Paper Content: {paper_content}

Please conduct a comprehensive analysis of this complete paper to determine its relevance to the user requirements.

Consider all sections of the paper including methodology, results, and conclusions.

Remember: 
- Only analyze English papers
- relevance_score must be between 0.0 and 1.0 (decimal format, not percentage)
- Provide detailed justification based on the full paper content"""
        
        try:
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt}
            ]
            
            result = self.structured_llm.invoke(messages)
            return cast(FullAnalysisResult, result)
            
        except Exception as e:
            logger.error(f"Full paper analysis failed: {e}")
            return FullAnalysisResult(
                is_relevant=False,
                relevance_score=0.0,
                justification=f"Analysis error: {str(e)}"
            )
        
if __name__ == "__main__":
    # Example usage
    analysis_llm = AbstractAnalysisLLM()
    abstract = "This paper presents a novel approach to machine learning. It discusses various applications in real-world scenarios, including image recognition and natural language processing."
    user_requirements = "I need papers related to machine learning applications."
    
    result = analysis_llm.analyze_abstract(abstract, user_requirements)
    print(result.model_dump_json(indent=2))  # Print the analysis result in JSON format
    # Output: {"is_relevant": true, "relevance_score": 0.9, "justification": "The abstract discusses machine learning, which matches the user requirements."}   