"""
论文翻译工具 - 基于LLM的结构化翻译工具

专门用于翻译学术论文分析结果，保持LaTeX公式、图片引用格式，
支持结构化内容翻译和专业术语准确性。
"""

import json
import re
from typing import Any, Dict, Optional, Type, Union
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from loguru import logger

from ..llm_factory import get_llm


class TranslationInput(BaseModel):
    """翻译工具输入模型"""
    content: Union[str, Dict[str, Any]] = Field(
        description="Content to translate - can be text string or structured JSON"
    )
    section_type: str = Field(
        description="Type of content being translated (e.g., 'contributions', 'methodology', 'results')"
    )
    target_language: str = Field(
        description="Target language code",
        default="zh"
    )


class PaperTranslationTool(BaseTool):
    """论文翻译工具 - 保持结构和格式的专业学术翻译"""
    
    name: str = "translate_paper_content"
    description: str = "Translate academic paper analysis results while preserving LaTeX formulas, image references, and JSON structure"
    args_schema: Type[BaseModel] = TranslationInput
    return_direct: bool = False
    
    # 声明工具属性
    translation_model: str = Field(default="deepseek.DeepSeek_V3", exclude=True)
    target_language: str = Field(default="zh", exclude=True)
    llm: Any = Field(default=None, exclude=True)
    academic_terms: Dict[str, Dict[str, str]] = Field(default={}, exclude=True)
    
    def __init__(self, 
                 translation_model: str = "deepseek.DeepSeek_V3",
                 target_language: str = "zh",
                 **kwargs):
        """
        初始化论文翻译工具
        
        Args:
            translation_model: 翻译使用的LLM模型
            target_language: 目标语言代码
        """
        super().__init__(**kwargs)
        
        # 使用 object.__setattr__ 来设置属性
        object.__setattr__(self, 'translation_model', translation_model)
        object.__setattr__(self, 'target_language', target_language)
        llm = get_llm(translation_model)
        object.__setattr__(self, 'llm', llm)
        
        # 学术术语词典 - 常见的学术术语对照
        academic_terms = {
            "en": {
                "methodology": "方法论",
                "contribution": "贡献", 
                "architecture": "架构",
                "framework": "框架",
                "algorithm": "算法",
                "performance": "性能",
                "evaluation": "评估",
                "experiment": "实验",
                "baseline": "基线",
                "state-of-the-art": "最先进的",
                "novel": "新颖的",
                "innovative": "创新的",
                "comprehensive": "全面的",
                "significant": "显著的",
                "robust": "鲁棒的",
                "scalable": "可扩展的"
            }
        }
        object.__setattr__(self, 'academic_terms', academic_terms)
        
        logger.info(f"PaperTranslationTool initialized with model: {translation_model}")
    
    def _preserve_formulas_and_references(self, text: str) -> tuple[str, Dict[str, str]]:
        """
        保护LaTeX公式和图片引用，替换为占位符
        
        Args:
            text: 原始文本
            
        Returns:
            tuple: (处理后的文本, 占位符映射字典)
        """
        placeholders = {}
        placeholder_counter = 0
        
        # 保护行间公式 $$...$$
        display_formula_pattern = r'\$\$([^$]+?)\$\$'
        def replace_display_formula(match):
            nonlocal placeholder_counter
            placeholder = f"__DISPLAY_FORMULA_{placeholder_counter}__"
            placeholders[placeholder] = f"$${match.group(1)}$$"
            placeholder_counter += 1
            return placeholder
        
        text = re.sub(display_formula_pattern, replace_display_formula, text)
        
        # 保护行内公式 $...$
        inline_formula_pattern = r'(?<!\$)\$([^$\n]+?)\$(?!\$)'
        def replace_inline_formula(match):
            nonlocal placeholder_counter
            placeholder = f"__INLINE_FORMULA_{placeholder_counter}__"
            placeholders[placeholder] = f"${match.group(1)}$"
            placeholder_counter += 1
            return placeholder
        
        text = re.sub(inline_formula_pattern, replace_inline_formula, text)
        
        # 保护图片引用路径
        image_ref_pattern = r'imgs/[^)\s"]+\.jpg|imgs/[^)\s"]+\.png|imgs/[^)\s"]+\.jpeg'
        def replace_image_ref(match):
            nonlocal placeholder_counter
            placeholder = f"__IMAGE_REF_{placeholder_counter}__"
            placeholders[placeholder] = match.group(0)
            placeholder_counter += 1
            return placeholder
        
        text = re.sub(image_ref_pattern, replace_image_ref, text)
        
        return text, placeholders
    
    def _restore_formulas_and_references(self, text: str, placeholders: Dict[str, str]) -> str:
        """
        恢复LaTeX公式和图片引用
        
        Args:
            text: 翻译后的文本
            placeholders: 占位符映射字典
            
        Returns:
            str: 恢复后的文本
        """
        for placeholder, original in placeholders.items():
            text = text.replace(placeholder, original)
        return text
    
    def _generate_translation_prompt(self, content: str, section_type: str, target_language: str) -> str:
        """生成专业的翻译提示词"""
        
        language_names = {
            "zh": "中文",
            "en": "English",
            "ja": "日本語",
            "ko": "한국어"
        }
        
        target_lang_name = language_names.get(target_language, target_language)
        
        return f"""
你是一位专业的学术论文翻译专家，专门翻译计算机科学和机器学习领域的论文。

**翻译任务：**
将以下{section_type}的英文分析结果翻译成{target_lang_name}。

**原文内容：**
{content}

**翻译要求：**

1. **格式保持**：
   - 保持所有LaTeX公式格式不变（$$...$$和$...$）
   - 保持图片引用路径不变（imgs/...）
   - 保持JSON结构完整（如果是结构化内容）
   - 保持markdown格式和层级结构

2. **学术准确性**：
   - 使用准确的学术术语翻译
   - 保持专业性和学术语言风格
   - 确保技术概念翻译准确
   - 保持原文的逻辑结构和表达方式

3. **术语一致性**：
   - 同一概念在全文中保持术语一致
   - 专业名词首次出现时可附英文原文
   - 保持常见学术术语的标准翻译

4. **语言质量**：
   - 确保翻译自然流畅
   - 避免直译，注重意译的准确性
   - 保持原文的专业程度和严谨性

**特别注意：**
- 所有数学公式、代码、图片路径必须保持原样
- JSON结构中的key保持英文，value翻译成中文
- 技术术语如"VLAS"、"RAG"等专有名词保持原文

请提供高质量的学术翻译，确保既准确又符合中文学术写作习惯。
"""
    
    def _translate_structured_content(self, content_dict: Dict[str, Any], section_type: str) -> Dict[str, Any]:
        """
        翻译结构化内容（JSON格式）
        
        Args:
            content_dict: 要翻译的结构化内容
            section_type: 内容类型
            
        Returns:
            Dict: 翻译后的结构化内容
        """
        try:
            # 将结构化内容转换为JSON字符串进行翻译
            json_content = json.dumps(content_dict, ensure_ascii=False, indent=2)
            
            # 保护公式和引用
            protected_content, placeholders = self._preserve_formulas_and_references(json_content)
            
            # 生成翻译提示词
            prompt = self._generate_translation_prompt(protected_content, section_type, self.target_language)
            
            # 执行翻译
            response = self.llm.invoke(prompt)
            translated_content = response.content if hasattr(response, 'content') else str(response)
            
            # 恢复公式和引用
            restored_content = self._restore_formulas_and_references(translated_content, placeholders)
            
            # 尝试解析为JSON
            try:
                # 提取JSON部分
                json_start = restored_content.find('{')
                json_end = restored_content.rfind('}') + 1
                
                if json_start != -1 and json_end != -1:
                    json_str = restored_content[json_start:json_end]
                    translated_dict = json.loads(json_str)
                    return translated_dict
                else:
                    logger.warning("No valid JSON found in translation result")
                    return {"translation_error": "Failed to parse JSON", "raw_content": restored_content}
                    
            except json.JSONDecodeError as e:
                logger.warning(f"JSON decode error in translation: {e}")
                return {"translation_error": str(e), "raw_content": restored_content}
                
        except Exception as e:
            logger.error(f"Structured content translation failed: {e}")
            return {"translation_error": str(e), "original_content": content_dict}
    
    def _translate_text_content(self, text: str, section_type: str) -> str:
        """
        翻译纯文本内容
        
        Args:
            text: 要翻译的文本
            section_type: 内容类型
            
        Returns:
            str: 翻译后的文本
        """
        try:
            # 保护公式和引用
            protected_text, placeholders = self._preserve_formulas_and_references(text)
            
            # 生成翻译提示词
            prompt = self._generate_translation_prompt(protected_text, section_type, self.target_language)
            
            # 执行翻译
            response = self.llm.invoke(prompt)
            translated_text = response.content if hasattr(response, 'content') else str(response)
            
            # 恢复公式和引用
            restored_text = self._restore_formulas_and_references(translated_text, placeholders)
            
            return restored_text.strip()
            
        except Exception as e:
            logger.error(f"Text content translation failed: {e}")
            return f"Translation error: {str(e)}\n\nOriginal content:\n{text}"
    
    def _run(self, 
             content: Union[str, Dict[str, Any]], 
             section_type: str, 
             target_language: str = None) -> str:
        """
        执行翻译
        
        Args:
            content: 要翻译的内容（字符串或字典）
            section_type: 内容类型
            target_language: 目标语言（可选，默认使用实例化时设置的语言）
            
        Returns:
            str: 翻译结果（JSON字符串格式）
        """
        if target_language is None:
            target_language = self.target_language
        
        logger.info(f"Starting translation for {section_type} content to {target_language}")
        
        try:
            if isinstance(content, dict):
                # 结构化内容翻译
                translated_dict = self._translate_structured_content(content, section_type)
                result = json.dumps(translated_dict, ensure_ascii=False, indent=2)
            else:
                # 文本内容翻译
                translated_text = self._translate_text_content(str(content), section_type)
                # 包装为统一格式
                result = json.dumps({
                    "translated_content": translated_text,
                    "section_type": section_type,
                    "target_language": target_language
                }, ensure_ascii=False, indent=2)
            
            logger.info(f"Translation completed for {section_type}")
            return result
            
        except Exception as e:
            error_msg = f"Translation failed for {section_type}: {str(e)}"
            logger.error(error_msg)
            return json.dumps({
                "translation_error": error_msg,
                "original_content": content,
                "section_type": section_type
            }, ensure_ascii=False, indent=2)
    
    def translate_contributions(self, contributions_data: Dict[str, Any]) -> Dict[str, Any]:
        """翻译主要贡献内容"""
        result = self._run(contributions_data, "主要贡献")
        return json.loads(result)
    
    def translate_methodology(self, methodology_data: Dict[str, Any]) -> Dict[str, Any]:
        """翻译方法论内容"""
        result = self._run(methodology_data, "方法论")
        return json.loads(result)
    
    def translate_results(self, results_data: Dict[str, Any]) -> Dict[str, Any]:
        """翻译实验结果内容"""
        result = self._run(results_data, "实验结果")
        return json.loads(result)
    
    def translate_background(self, background_data: Dict[str, Any]) -> Dict[str, Any]:
        """翻译背景分析内容"""
        result = self._run(background_data, "研究背景")
        return json.loads(result)


def create_translation_tool(translation_model: str = "deepseek.DeepSeek_V3", 
                          target_language: str = "zh") -> PaperTranslationTool:
    """
    创建论文翻译工具的便捷函数
    
    Args:
        translation_model: 翻译模型名称
        target_language: 目标语言代码
        
    Returns:
        PaperTranslationTool: 配置好的翻译工具实例
    """
    return PaperTranslationTool(
        translation_model=translation_model,
        target_language=target_language
    )


# 测试代码
if __name__ == "__main__":
    # 测试翻译工具
    tool = create_translation_tool()
    
    # 测试结构化内容翻译
    test_contributions = {
        "contributions": [
            {
                "id": 1,
                "title": "End-to-end speech integration",
                "description": "VLAS integrates speech recognition directly into the robot policy model without external ASR systems."
            }
        ],
        "contribution_count": 1,
        "innovation_level": "high"
    }
    
    try:
        translated = tool.translate_contributions(test_contributions)
        print("Translation test successful!")
        print(f"Result keys: {list(translated.keys())}")
    except Exception as e:
        print(f"Translation test failed: {e}")