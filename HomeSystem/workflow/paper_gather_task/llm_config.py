import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))
from HomeSystem.graph.llm_factory import llm_factory
from pydantic import BaseModel, Field
from loguru import logger
from typing import cast, List


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


class TranslationResult(BaseModel):
    """Translation result"""
    original_text: str = Field(description="Original English text")
    translated_text: str = Field(description="Chinese translation")
    translation_quality: str = Field(description="Translation quality assessment (high/medium/low)")
    notes: str = Field(description="Translation notes or explanations", default="")


class AbstractAnalysisLLM:
    """Paper abstract preliminary analysis LLM"""
    
    def __init__(self, model_name: str = "ollama.Qwen3_30B"):
        self.model_name = model_name
        self.system_prompt = """You are a paper screening assistant for preliminary filtering. Your approach should be methodical and requirement-driven.

Step 1: ANALYZE USER REQUIREMENTS
First, carefully analyze the user requirements to identify:
1. CORE/ESSENTIAL elements - What are the must-have aspects that any relevant paper should address?
2. SECONDARY elements - What are the nice-to-have or related aspects?
3. DOMAIN context - What field/area is the user interested in?

Step 2: CHECK ABSTRACT AGAINST CORE REQUIREMENTS
Then evaluate the paper abstract:
1. Does it address at least ONE of the core/essential requirements?
2. Is it in the relevant domain or closely related field?

KEY PRINCIPLE: If the abstract addresses core requirements, it should get ≥ 0.50 score (pass threshold)

IMPORTANT: The relevance_score MUST be a decimal number between 0.0 and 1.0.

Scoring criteria (core requirement driven):
- 0.80-1.0 = Addresses multiple core requirements excellently + perfect domain match
- 0.65-0.80 = Addresses core requirements well + good domain match
- 0.50-0.65 = Addresses at least one core requirement + acceptable domain match
- 0.35-0.50 = Partially addresses core requirements OR wrong domain but related
- 0.20-0.35 = Minimal connection to core requirements + distant domain
- 0.0-0.20 = No connection to any core requirement + completely unrelated domain

Filtering logic (simplified):
- Addresses core requirement(s) + relevant/related domain → score ≥ 0.50 (PASS)
- Addresses core requirement(s) + unrelated domain → score 0.35-0.50 (borderline)
- No core requirement addressed → score ≤ 0.35 (FILTER OUT)

Your justification should explain:
1. What you identified as core requirements
2. Which core requirements (if any) the abstract addresses
3. Domain relevance assessment
4. Why the score is above/below 0.50

Focus on core requirement fulfillment as the primary criterion."""
        
        # Create LLM instance
        self.base_llm = llm_factory.create_llm(model_name=self.model_name)
        self.structured_llm = self.base_llm.with_structured_output(AbstractAnalysisResult)
        
        logger.info(f"Initialized abstract analysis LLM: {self.model_name}")
    
    def analyze_abstract(self, abstract: str, user_requirements: str) -> AbstractAnalysisResult:
        """Analyze a single paper abstract"""
        prompt = f"""User Requirements: {user_requirements}

Paper Abstract: {abstract}

Please analyze this abstract against the user requirements and provide your assessment."""
        
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
        self.base_llm = llm_factory.create_llm(model_name=self.model_name)
        self.structured_llm = self.base_llm.with_structured_output(FullAnalysisResult)
        
        logger.info(f"Initialized full paper analysis LLM: {self.model_name}")
    
    def analyze_full_paper(self, paper_content: str, user_requirements: str) -> FullAnalysisResult:
        """Analyze a complete paper content"""
        prompt = f"""User Requirements: {user_requirements}

Full Paper Content: {paper_content}

Please conduct a comprehensive analysis of this complete paper to determine its relevance to the user requirements."""
        
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


class TranslationLLM:
    """英文到中文翻译的LLM"""
    
    def __init__(self, model_name: str = "ollama.Qwen3_30B"):
        self.model_name = model_name
        self.system_prompt = """你是一个专业的学术翻译专家，专门负责将英文学术论文和文本翻译成中文。

你的翻译要求：
1. 保持学术准确性和术语精确性
2. 保留原文的含义和语境
3. 使用合适的中文学术写作风格
4. 保持技术术语和专有名词的一致性
5. 提供自然流畅的中文翻译

翻译质量标准：
- high（高）：准确、流畅，保持所有技术细节
- medium（中）：总体准确，有轻微问题
- low（低）：基本理解但可能有不准确之处

请将给定的英文文本翻译成中文，同时保持学术严谨性和可读性。"""
        
        # Create LLM instance
        self.base_llm = llm_factory.create_llm(model_name=self.model_name)
        self.structured_llm = self.base_llm.with_structured_output(TranslationResult)
        
        logger.info(f"初始化翻译LLM: {self.model_name}")
    
    def translate_text(self, english_text: str) -> TranslationResult:
        """将英文文本翻译为中文"""
        prompt = f"""请将以下英文文本翻译成中文：

英文文本：{english_text}"""
        
        try:
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt}
            ]
            
            result = self.structured_llm.invoke(messages)
            return cast(TranslationResult, result)
            
        except Exception as e:
            logger.error(f"翻译失败: {e}")
            return TranslationResult(
                original_text=english_text,
                translated_text=f"翻译失败: {str(e)}",
                translation_quality="low",
                notes=f"翻译错误: {str(e)}"
            )
    
    async def translate_texts_batch(self, texts_with_field_names: List[tuple]) -> List[TranslationResult]:
        """
        批量并发翻译多个文本
        
        Args:
            texts_with_field_names: [(field_name, text), ...] 的列表
            
        Returns:
            List[TranslationResult]: 翻译结果列表，与输入顺序对应
        """
        if not texts_with_field_names:
            return []
        
        try:
            # 准备消息列表
            messages_list = []
            for field_name, text in texts_with_field_names:
                prompt = f"""请将以下英文文本翻译成中文：

英文文本：{text}"""
                
                messages = [
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt}
                ]
                messages_list.append(messages)
            
            # 尝试使用LangChain的abatch方法进行并发调用
            try:
                logger.info(f"开始批量翻译 {len(texts_with_field_names)} 个字段 (模型: {self.model_name})")
                logger.info("尝试使用LangChain abatch方法...")
                
                batch_start_time = __import__('time').time()
                results = await self.structured_llm.abatch(
                    messages_list,
                    config={"max_concurrency": 3}  # 限制并发数以防止API过载
                )
                batch_time = __import__('time').time() - batch_start_time
                
                logger.info(f"abatch方法完成，耗时: {batch_time:.2f}秒，成功翻译 {len(results)} 个字段")
                return [cast(TranslationResult, result) for result in results]
                
            except Exception as batch_error:
                logger.warning(f"abatch方法失败，回退到asyncio.gather: {batch_error}")
                
                # 回退到使用asyncio.gather + ainvoke
                import asyncio
                
                async def translate_single(messages):
                    try:
                        result = await self.structured_llm.ainvoke(messages)
                        return cast(TranslationResult, result)
                    except Exception as e:
                        field_name = texts_with_field_names[messages_list.index(messages)][0]
                        logger.error(f"翻译字段 {field_name} 失败: {e}")
                        return TranslationResult(
                            original_text=texts_with_field_names[messages_list.index(messages)][1],
                            translated_text=f"翻译失败: {str(e)}",
                            translation_quality="low",
                            notes=f"翻译错误: {str(e)}"
                        )
                
                # 使用asyncio.gather进行并发调用，限制并发数
                semaphore = asyncio.Semaphore(3)  # 限制并发数为3
                
                async def translate_with_semaphore(messages):
                    async with semaphore:
                        return await translate_single(messages)
                
                results = await asyncio.gather(
                    *[translate_with_semaphore(messages) for messages in messages_list],
                    return_exceptions=True
                )
                
                # 处理异常结果
                final_results = []
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        field_name, text = texts_with_field_names[i]
                        logger.error(f"翻译字段 {field_name} 异常: {result}")
                        final_results.append(TranslationResult(
                            original_text=text,
                            translated_text=f"翻译异常: {str(result)}",
                            translation_quality="low",
                            notes=f"翻译异常: {str(result)}"
                        ))
                    else:
                        final_results.append(result)
                
                return final_results
                
        except Exception as e:
            logger.error(f"批量翻译过程中发生严重错误: {e}")
            # 返回错误结果
            return [TranslationResult(
                original_text=text,
                translated_text=f"翻译失败: {str(e)}",
                translation_quality="low",
                notes=f"批量翻译错误: {str(e)}"
            ) for field_name, text in texts_with_field_names]
    

        
if __name__ == "__main__":
    # Example usage
    analysis_llm = AbstractAnalysisLLM()
    abstract = "This paper presents a novel approach to machine learning. It discusses various applications in real-world scenarios, including image recognition and natural language processing."
    user_requirements = "I need papers related to machine learning applications."
    
    result = analysis_llm.analyze_abstract(abstract, user_requirements)
    print(result.model_dump_json(indent=2))  # Print the analysis result in JSON format
    # Output: {"is_relevant": true, "relevance_score": 0.9, "justification": "The abstract discusses machine learning, which matches the user requirements."}   