"""
数学公式提取工具模块

从 Markdown 文件或文本中提取行间数学公式，并返回公式内容及其对应的行号。
支持 LaTeX 格式的数学公式（$$...$$）。
"""
import json
import re
from typing import Dict, Any, List, Optional, Union
from pathlib import Path
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field


class MathFormulaExtractorInput(BaseModel):
    """数学公式提取工具输入模型"""
    file_path: Optional[str] = Field(default=None, description="Markdown文件路径")
    markdown_text: Optional[str] = Field(default=None, description="Markdown文本内容")
    
    def validate_input(self):
        """验证输入参数"""
        if not self.file_path and not self.markdown_text:
            raise ValueError("必须提供 file_path 或 markdown_text 其中之一")
        if self.file_path and self.markdown_text:
            raise ValueError("只能提供 file_path 或 markdown_text 其中之一，不能同时提供")


class MathFormulaExtractorTool(BaseTool):
    """数学公式提取工具"""
    
    name: str = "math_formula_extractor_tool"
    description: str = "Extract mathematical formulas from Markdown files or text with line numbers"
    args_schema: type[BaseModel] = MathFormulaExtractorInput
    
    def _read_markdown_file(self, file_path: str) -> str:
        """读取 Markdown 文件内容"""
        try:
            path = Path(file_path)
            if not path.exists():
                raise FileNotFoundError(f"文件不存在: {file_path}")
            if not path.is_file():
                raise ValueError(f"路径不是文件: {file_path}")
            
            # 尝试不同编码读取文件
            encodings = ['utf-8', 'utf-8-sig', 'gbk', 'gb2312']
            for encoding in encodings:
                try:
                    with open(path, 'r', encoding=encoding) as f:
                        content = f.read()
                    return content
                except UnicodeDecodeError:
                    continue
            
            raise ValueError(f"无法使用支持的编码读取文件: {file_path}")
            
        except Exception as e:
            raise RuntimeError(f"读取文件时发生错误: {str(e)}")
    
    def _extract_formulas_with_line_numbers(self, text: str) -> List[Dict[str, Union[str, int]]]:
        """提取数学公式及其行号"""
        lines = text.split('\n')
        formulas = []
        
        i = 0
        while i < len(lines):
            line = lines[i]
            
            # 查找行间公式开始标记 $$
            if '$$' in line:
                # 处理同一行包含开始和结束的情况
                formula_match = re.search(r'\$\$(.*?)\$\$', line)
                if formula_match:
                    formula_content = formula_match.group(1).strip()
                    if formula_content:  # 非空公式
                        formulas.append({
                            "formula": formula_content,
                            "start_line": i + 1,
                            "end_line": i + 1
                        })
                    i += 1
                    continue
                
                # 处理跨行公式
                start_pos = line.find('$$')
                if start_pos != -1:
                    # 找到开始标记，收集多行公式
                    formula_lines = []
                    start_line = i + 1
                    
                    # 添加第一行（去掉开始的$$）
                    first_line = line[start_pos + 2:].strip()
                    if first_line:
                        formula_lines.append(first_line)
                    
                    i += 1
                    end_line = start_line
                    
                    # 继续查找结束标记
                    while i < len(lines):
                        current_line = lines[i]
                        end_line = i + 1
                        
                        if '$$' in current_line:
                            # 找到结束标记
                            end_pos = current_line.find('$$')
                            if end_pos != -1:
                                # 添加最后一行（去掉结束的$$）
                                last_line = current_line[:end_pos].strip()
                                if last_line:
                                    formula_lines.append(last_line)
                                break
                            else:
                                # 整行都是公式内容
                                formula_lines.append(current_line.strip())
                        else:
                            # 整行都是公式内容
                            formula_lines.append(current_line.strip())
                        
                        i += 1
                    
                    # 组合公式内容
                    if formula_lines:
                        formula_content = '\n'.join(formula_lines).strip()
                        if formula_content:
                            formulas.append({
                                "formula": formula_content,
                                "start_line": start_line,
                                "end_line": end_line
                            })
            
            i += 1
        
        return formulas
    
    def _format_result(self, formulas: List[Dict[str, Union[str, int]]]) -> str:
        """格式化结果为JSON"""
        result = {
            "formulas": formulas,
            "total_count": len(formulas)
        }
        return json.dumps(result, indent=2, ensure_ascii=False)
    
    def _run(self, file_path: Optional[str] = None, markdown_text: Optional[str] = None) -> str:
        """执行公式提取"""
        try:
            # 验证输入
            input_data = MathFormulaExtractorInput(file_path=file_path, markdown_text=markdown_text)
            input_data.validate_input()
            
            # 获取文本内容
            if file_path:
                text_content = self._read_markdown_file(file_path)
                source_info = f"文件: {file_path}"
            else:
                text_content = markdown_text
                source_info = "直接输入的文本"
            
            # 提取公式
            formulas = self._extract_formulas_with_line_numbers(text_content)
            
            # 格式化结果
            result = self._format_result(formulas)
            
            return result
            
        except Exception as e:
            error_result = {
                "error": f"数学公式提取过程中发生错误: {str(e)}",
                "formulas": [],
                "total_count": 0
            }
            return json.dumps(error_result, indent=2, ensure_ascii=False)


def create_math_formula_extractor_tool():
    """创建数学公式提取工具实例"""
    return MathFormulaExtractorTool()