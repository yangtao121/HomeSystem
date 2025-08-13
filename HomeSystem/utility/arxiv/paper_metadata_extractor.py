"""
Paper Metadata Extractor using LLM

专门用于从 OCR 文本中提取论文元数据，包括标题、作者和摘要。
使用本地 LLM 模型进行结构化输出。
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))

from pydantic import BaseModel, Field
from loguru import logger
from typing import Optional, cast
from HomeSystem.graph.llm_factory import llm_factory


class PaperMetadata(BaseModel):
    """论文元数据模型"""
    title: Optional[str] = Field(description="论文标题", default=None)
    authors: Optional[str] = Field(description="作者列表，用逗号分隔", default=None)
    abstract: Optional[str] = Field(description="论文摘要/Abstract", default=None)


class PaperMetadataLLM:
    """论文元数据提取 LLM"""
    
    def __init__(self, model_name: str = "ollama.Qwen3_30B"):
        self.model_name = model_name
        self.system_prompt = """你是一个专业的学术论文元数据提取专家，专门负责从 OCR 转换的论文文本中准确提取关键信息。

你的任务：
1. 从提供的 OCR 文本中识别和提取论文标题（Title）
2. 提取所有作者信息，用逗号分隔
3. 提取论文摘要（Abstract）部分的完整内容

提取要求：
- 标题：提取完整的论文标题，去除多余的换行和空格
- 作者：提取所有作者姓名，用英文逗号分隔，保持原始格式
- 摘要：提取 Abstract 部分的完整文本内容，保持原始语言（通常是英文）

注意事项：
- OCR 文本可能包含识别错误，请根据上下文进行合理推断
- 如果某项信息无法确定，请返回 null
- 保持提取内容的准确性和完整性
- 优先处理文档前几页的内容，因为标题、作者和摘要通常在开头部分"""
        
        # 创建 LLM 实例
        try:
            self.base_llm = llm_factory.create_llm(model_name=self.model_name)
            self.structured_llm = self.base_llm.with_structured_output(PaperMetadata)
            logger.info(f"初始化论文元数据提取 LLM: {self.model_name}")
        except Exception as e:
            logger.error(f"LLM 初始化失败: {e}")
            self.base_llm = None
            self.structured_llm = None
    
    def extract_metadata(self, ocr_text: str) -> PaperMetadata:
        """从 OCR 文本中提取论文元数据"""
        if not self.structured_llm:
            logger.error("LLM 未正确初始化，无法提取元数据")
            return PaperMetadata()
        
        # 限制输入文本长度，只使用前 8000 字符（通常足够包含标题、作者和摘要）
        truncated_text = ocr_text[:8000] if len(ocr_text) > 8000 else ocr_text
        
        prompt = f"""请从以下 OCR 转换的论文文本中提取论文的标题、作者和摘要信息：

OCR 文本：
{truncated_text}

请仔细分析文本结构，准确提取：
1. 论文标题（Title）
2. 所有作者姓名（Authors），用逗号分隔
3. 论文摘要（Abstract）的完整内容

如果某项信息在文本中不存在或无法准确识别，请返回 null。"""
        
        try:
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt}
            ]
            
            result = self.structured_llm.invoke(messages)
            extracted_metadata = cast(PaperMetadata, result)
            
            logger.info(f"成功提取论文元数据 - 标题: {extracted_metadata.title[:50] if extracted_metadata.title else 'None'}...")
            return extracted_metadata
            
        except Exception as e:
            logger.error(f"元数据提取失败: {e}")
            return PaperMetadata()
    
    def is_available(self) -> bool:
        """检查 LLM 是否可用"""
        return self.structured_llm is not None


def extract_paper_metadata(ocr_text: str, model_name: str = "ollama.Qwen3_30B") -> PaperMetadata:
    """便捷函数：直接提取论文元数据
    
    Args:
        ocr_text: OCR 识别的文本内容
        model_name: 使用的 LLM 模型名称
        
    Returns:
        PaperMetadata: 提取的元数据
    """
    extractor = PaperMetadataLLM(model_name)
    return extractor.extract_metadata(ocr_text)


if __name__ == "__main__":
    # 测试代码
    test_text = """
    Deep Learning for Computer Vision: A Comprehensive Survey
    
    Authors: John Smith, Mary Johnson, David Brown, Lisa Wilson
    
    Abstract: This paper presents a comprehensive survey of deep learning techniques 
    applied to computer vision tasks. We review recent advances in convolutional 
    neural networks, attention mechanisms, and transformer architectures. Our analysis 
    covers applications in image classification, object detection, and semantic 
    segmentation. We also discuss current challenges and future research directions 
    in this rapidly evolving field.
    """
    
    extractor = PaperMetadataLLM()
    if extractor.is_available():
        result = extractor.extract_metadata(test_text)
        print("提取结果:")
        print(f"标题: {result.title}")
        print(f"作者: {result.authors}")
        print(f"摘要: {result.abstract}")
    else:
        print("LLM 不可用，无法进行测试")