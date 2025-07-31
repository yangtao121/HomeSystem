import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))
from HomeSystem.graph.llm_factory import llm_factory
from pydantic import BaseModel, Field
from loguru import logger
from typing import cast


class ChineseToEnglishSearchResult(BaseModel):
    """中文到英文搜索转换结果"""
    search_keywords: str = Field(description="英文搜索关键词，用于ArXiv搜索")
    user_requirements: str = Field(description="英文用户需求描述，用于LLM论文相关性分析")
    suggested_task_name: str = Field(description="建议的英文任务名称，1-3个单词的技术术语短语")
    confidence: str = Field(description="转换质量评估 (high/medium/low)")
    notes: str = Field(description="转换说明或建议", default="")


class ChineseSearchAssistantLLM:
    """中文搜索助手LLM - 将中文研究需求转换为英文搜索关键词和需求描述"""
    
    def __init__(self, model_name: str = "ollama.Qwen3_30B"):
        self.model_name = model_name
        self.system_prompt = """你是一个专业的学术搜索助手，专门负责将中文的研究需求转换为英文的学术搜索关键词、需求描述和任务名称。

你的任务：
1. 理解用户的中文研究需求和兴趣
2. 生成适合在ArXiv等学术数据库中使用的英文搜索关键词
3. 创建清晰的英文用户需求描述，供LLM进行论文相关性分析
4. 生成简洁的英文任务名称，突出研究的核心技术特点

搜索关键词要求：
- 最多3个核心关键词或短语
- 每个关键词必须是单词或短语组合，不能是完整句子
- 使用学术标准的英文术语和技术名词
- 选择最核心、最具代表性的概念
- 避免冗词、介词和连接词
- 必须使用逗号分隔格式：keyword1, keyword2, keyword3
- 例如：deep learning, medical imaging, CT

用户需求描述要求：
- 使用清晰的英文表达研究目标和兴趣
- 包含具体的应用领域和技术方向
- 便于LLM理解和评估论文相关性
- 保持学术性和专业性

任务名称要求：
- 使用1-3个英文单词组成的技术短语
- 突出研究的核心技术特征和应用领域
- 采用学术界通用的表述方式
- 避免过于泛泛的词汇，要有针对性
- 例如：medical imaging, end2end navigation, visual SLAM, diffusion trajectory

转换质量标准：
- high（高）：关键词精准、简洁，术语准确，表达清晰
- medium（中）：基本准确，略有不足
- low（低）：需要进一步完善

关键词示例：
好的示例：
- deep learning, medical imaging, CT
- machine learning, neural networks, computer vision
- transformer, attention mechanism, NLP
不好的示例：
- applications of machine learning in medical image analysis for CT scans

请确保转换结果既专业又实用。"""
        
        # Create LLM instance
        self.base_llm = llm_factory.create_llm(model_name=self.model_name)
        self.structured_llm = self.base_llm.with_structured_output(ChineseToEnglishSearchResult)
        
        logger.info(f"Initialized Chinese search assistant LLM: {self.model_name}")
    
    def convert_chinese_to_english_search(self, chinese_input: str) -> ChineseToEnglishSearchResult:
        """将中文研究需求转换为英文搜索关键词和需求描述"""
        prompt = f"""用户的中文研究需求：{chinese_input}

请将上述中文需求精确转换为：
1. 英文搜索关键词 - 最多3个关键词/短语，每个都是单词组合（不是句子）
2. 英文用户需求描述 - 供LLM评估论文相关性使用
3. 英文任务名称 - 1-3个单词的技术术语短语，突出核心特点

关键词要求：
- 严格限制在3个以内
- 每个关键词是单词或技术短语，不是完整句子
- 选择最核心的学术术语
- 必须使用逗号分隔：keyword1, keyword2, keyword3
- 例如：deep learning, medical imaging, CT

其他要求：
- 保持研究领域的专业性和准确性
- 使用标准的学术英文术语  
- 确保搜索关键词能有效检索到相关论文
- 确保需求描述能帮助LLM准确评估论文相关性
- 任务名称要简洁有力，能立即体现研究焦点
- 对于专业领域，保留重要的技术缩写（如CT、MRI、SLAM等）

任务名称示例：
- 深度学习+医疗图像 → "medical imaging"
- 端到端自动驾驶导航 → "end2end navigation" 或 "visual navigation"
- 基于视觉的SLAM → "visual SLAM"
- 扩散模型轨迹生成 → "diffusion trajectory"

请提供专业、准确、简洁的转换结果。"""
        
        try:
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt}
            ]
            
            result = self.structured_llm.invoke(messages)
            return cast(ChineseToEnglishSearchResult, result)
            
        except Exception as e:
            logger.error(f"Chinese to English search conversion failed: {e}")
            return ChineseToEnglishSearchResult(
                search_keywords=f"Conversion error: {str(e)}",
                user_requirements=f"Conversion failed: {str(e)}",
                suggested_task_name="conversion error",
                confidence="low",
                notes=f"转换错误: {str(e)}"
            )


if __name__ == "__main__":
    # Example usage
    assistant = ChineseSearchAssistantLLM(model_name="deepseek.DeepSeek_V3")
    chinese_input = "我想找关于深度学习在医疗图像分析中应用的最新论文，特别是在CT扫描和MRI图像处理方面的研究"
    
    result = assistant.convert_chinese_to_english_search(chinese_input)
    print("转换结果:")
    print(f"英文搜索关键词: {result.search_keywords}")
    print(f"英文用户需求: {result.user_requirements}")
    print(f"建议任务名称: {result.suggested_task_name}")
    print(f"转换质量: {result.confidence}")
    print(f"说明: {result.notes}")