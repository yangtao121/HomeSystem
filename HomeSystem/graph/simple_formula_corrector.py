"""
简化版公式纠错工具

直接使用工具进行公式纠错，避免复杂的LangGraph工作流。
提供核心的公式提取、对比和纠错功能。
"""

import json
import os
from typing import Dict, List, Any, Optional
from loguru import logger

from .llm_factory import get_llm
from .tool.math_formula_extractor import create_math_formula_extractor_tool
from .tool.ocr_document_loader import create_ocr_document_loader_tool
from .tool.text_editor import create_text_editor_tool


class SimpleFormulaCorrector:
    """简化版公式纠错器
    
    提供直接的公式纠错功能，无需复杂的工作流。
    """
    
    def __init__(self, model_name: str = "deepseek.DeepSeek_V3"):
        self.model_name = model_name
        self.llm = get_llm(model_name)
        
        # 创建工具
        self.formula_extractor = create_math_formula_extractor_tool()
        self.ocr_loader = create_ocr_document_loader_tool()
        self.text_editor = create_text_editor_tool()
        
        logger.info(f"简化版公式纠错器初始化完成，使用模型: {model_name}")
    
    def correct_formulas(self, analysis_file: str, ocr_file: str) -> Dict[str, Any]:
        """执行公式纠错
        
        Args:
            analysis_file: 分析文档路径
            ocr_file: OCR参考文档路径
            
        Returns:
            Dict: 纠错结果
        """
        try:
            logger.info(f"开始公式纠错: {analysis_file}")
            
            # 1. 读取文档内容
            with open(analysis_file, 'r', encoding='utf-8') as f:
                analysis_content = f.read()
            
            with open(ocr_file, 'r', encoding='utf-8') as f:
                ocr_content = f.read()
            
            # 2. 提取分析文档中的公式
            logger.info("提取分析文档中的公式...")
            formula_result = self.formula_extractor._run(markdown_text=analysis_content)
            formula_data = json.loads(formula_result)
            extracted_formulas = formula_data.get("formulas", [])
            
            logger.info(f"提取到 {len(extracted_formulas)} 个公式")
            
            # 3. 加载OCR参考文档
            logger.info("加载OCR参考文档...")
            ocr_result = self.ocr_loader._run(ocr_file_path=ocr_file)
            
            # 4. 分析每个公式是否有错误
            logger.info("分析公式错误...")
            formula_analysis = self._analyze_formulas(
                extracted_formulas, analysis_content, ocr_content
            )
            
            # 5. 应用修复
            corrected_content = analysis_content
            corrections_applied = []
            
            if formula_analysis.get("has_errors"):
                logger.info("应用公式修复...")
                corrected_content, corrections_applied = self._apply_corrections(
                    analysis_content, formula_analysis.get("corrections", [])
                )
            
            result = {
                "is_complete": True,
                "analysis_file": analysis_file,
                "ocr_file": ocr_file,
                "extracted_formulas": extracted_formulas,
                "formula_analysis": formula_analysis,
                "corrected_content": corrected_content,
                "corrections_applied": corrections_applied,
                "current_step": "completed"
            }
            
            logger.info("公式纠错完成")
            return result
            
        except Exception as e:
            logger.error(f"公式纠错失败: {e}")
            import traceback
            logger.error(f"错误堆栈: {traceback.format_exc()}")
            return {
                "error": f"纠错失败: {str(e)}",
                "analysis_file": analysis_file,
                "ocr_file": ocr_file
            }
    
    def _analyze_formulas(self, formulas: List[Dict], analysis_content: str, ocr_content: str) -> Dict[str, Any]:
        """使用LLM分析公式是否有错误"""
        try:
            # 构建分析提示
            formula_list = "\n".join([
                f"第{formula['start_line']}行: {formula['formula']}"
                for formula in formulas[:10]
            ])
            
            prompt = f"""
你是一个数学公式专家。请分析以下从分析文档中提取的公式是否有语法错误。

提取的公式列表:
{formula_list}

OCR参考文档内容（前2000字符）:
{ocr_content[:2000]}

请分析每个公式是否有以下类型的错误：
1. 括号不匹配（如缺少右括号}}、]、)）
2. LaTeX语法错误（如\\frac缺少参数）
3. 数学符号错误或缺失

对于每个有错误的公式，请提供修复建议。

请以JSON格式返回结果：
{{
  "has_errors": true,
  "corrections": [
    {{
      "line_number": 行号,
      "original_formula": "原始公式",
      "corrected_formula": "修正后的公式",
      "error_description": "错误描述"
    }}
  ]
}}
"""
            
            # 调用LLM分析
            response = self.llm.invoke(prompt)
            
            # 解析响应
            try:
                # 提取JSON部分
                content = response.content if hasattr(response, 'content') else str(response)
                
                # 尝试找到JSON块
                start_idx = content.find('{')
                end_idx = content.rfind('}') + 1
                
                if start_idx >= 0 and end_idx > start_idx:
                    json_str = content[start_idx:end_idx]
                    analysis_result = json.loads(json_str)
                else:
                    # 如果没有找到JSON，创建默认结果
                    analysis_result = {
                        "has_errors": False,
                        "corrections": [],
                        "llm_raw_response": content
                    }
                
                logger.info(f"公式分析完成，发现错误: {analysis_result.get('has_errors', False)}")
                return analysis_result
                
            except json.JSONDecodeError as e:
                logger.warning(f"LLM响应JSON解析失败: {e}")
                logger.warning(f"原始响应: {content[:500]}...")
                
                # 返回默认结果
                return {
                    "has_errors": False,
                    "corrections": [],
                    "parse_error": str(e),
                    "llm_raw_response": content
                }
            
        except Exception as e:
            logger.error(f"公式分析失败: {e}")
            return {
                "has_errors": False,
                "corrections": [],
                "analysis_error": str(e)
            }
    
    def _apply_corrections(self, original_content: str, corrections: List[Dict]) -> tuple[str, List[Dict]]:
        """应用公式修复"""
        try:
            corrected_content = original_content
            applied_corrections = []
            
            # 按行号倒序排序，避免行号变化影响后续修复
            corrections_sorted = sorted(corrections, key=lambda x: x.get('line_number', 0), reverse=True)
            
            for correction in corrections_sorted:
                try:
                    line_number = correction.get('line_number')
                    original_formula = correction.get('original_formula')
                    corrected_formula = correction.get('corrected_formula')
                    
                    if not all([line_number, original_formula, corrected_formula]):
                        logger.warning(f"修复信息不完整，跳过: {correction}")
                        continue
                    
                    # 找到公式的完整范围（包括$$标记）
                    lines = corrected_content.split('\n')
                    formula_start_line = None
                    formula_end_line = None
                    
                    # 从指定行号开始向上寻找$$开始标记
                    for i in range(line_number - 1, max(0, line_number - 10), -1):
                        if i < len(lines) and '$$' in lines[i]:
                            formula_start_line = i + 1  # 转换为1-based行号
                            break
                    
                    # 从指定行号开始向下寻找$$结束标记
                    for i in range(line_number - 1, min(len(lines), line_number + 10)):
                        if i < len(lines) and '$$' in lines[i] and i != (formula_start_line - 1):
                            formula_end_line = i + 1  # 转换为1-based行号
                            break
                    
                    # 如果找不到完整的公式块，使用单行替换
                    if not formula_start_line or not formula_end_line:
                        logger.warning(f"无法找到第{line_number}行公式的完整范围，使用单行替换")
                        edit_result = self.text_editor._run(
                            content=corrected_content,
                            operation_type="replace",
                            start_line=line_number,
                            new_content=corrected_formula
                        )
                    else:
                        # 替换整个公式块
                        logger.info(f"替换第{formula_start_line}-{formula_end_line}行的完整公式块")
                        edit_result = self.text_editor._run(
                            content=corrected_content,
                            operation_type="replace",
                            start_line=formula_start_line,
                            end_line=formula_end_line,
                            new_content=f"$$\n{corrected_formula}\n$$"
                        )
                    
                    edit_data = json.loads(edit_result)
                    if edit_data.get("success"):
                        corrected_content = edit_data.get("edited_content", corrected_content)
                        applied_corrections.append({
                            "line_number": line_number,
                            "original": original_formula,
                            "corrected": corrected_formula,
                            "description": correction.get('error_description', 'Formula correction'),
                            "formula_range": f"{formula_start_line}-{formula_end_line}" if formula_start_line and formula_end_line else str(line_number)
                        })
                        logger.info(f"成功修复第{line_number}行的公式")
                    else:
                        logger.warning(f"修复第{line_number}行失败: {edit_data.get('error', 'unknown error')}")
                
                except Exception as e:
                    logger.error(f"应用单个修复时失败: {e}")
                    continue
            
            return corrected_content, applied_corrections
            
        except Exception as e:
            logger.error(f"应用修复失败: {e}")
            return original_content, []
    
    def save_corrected_document(self, result: Dict[str, Any], output_path: str) -> bool:
        """保存纠错后的文档"""
        try:
            corrected_content = result.get("corrected_content")
            if not corrected_content:
                logger.error("没有纠错内容可保存")
                return False
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(corrected_content)
            
            logger.info(f"纠错文档已保存: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"保存纠错文档失败: {e}")
            return False


# 便捷函数
def create_simple_formula_corrector(model_name: str = "deepseek.DeepSeek_V3") -> SimpleFormulaCorrector:
    """创建简化版公式纠错器"""
    return SimpleFormulaCorrector(model_name=model_name)


# 测试代码
if __name__ == "__main__":
    # 创建纠错器
    corrector = create_simple_formula_corrector()
    
    # 测试文件
    test_analysis = "data/paper_analyze/test_formula_errors.md"
    test_ocr = "data/paper_analyze/test_formula_correct.md"
    
    if os.path.exists(test_analysis) and os.path.exists(test_ocr):
        print("执行测试...")
        result = corrector.correct_formulas(test_analysis, test_ocr)
        print("结果:", json.dumps(result, ensure_ascii=False, indent=2)[:1000], "...")
    else:
        print("测试文件不存在")