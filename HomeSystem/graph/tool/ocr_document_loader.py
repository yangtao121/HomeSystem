"""
OCR文档加载工具

专门用于加载和索引OCR转换后的Markdown文档，提供语义搜索功能。
基于现有的TextChunkIndexerTool进行包装，专门优化OCR文档的处理和查询。
"""

import json
import os
from typing import Dict, Any, Optional
from pathlib import Path
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
import logging

from .text_chunk_indexer import create_text_chunk_indexer_tool

logger = logging.getLogger(__name__)


class OCRDocumentLoaderInput(BaseModel):
    """OCR文档加载工具输入模型"""
    ocr_file_path: str = Field(description="OCR Markdown文件路径")
    query: Optional[str] = Field(default=None, description="查询内容，用于搜索相关的原始OCR内容")


class OCRDocumentLoaderTool(BaseTool):
    """OCR文档加载和查询工具
    
    专门用于处理OCR转换的论文文档，提供语义搜索能力来查找原始公式内容。
    基于TextChunkIndexerTool的功能，针对OCR文档进行了优化。
    """
    
    name: str = "ocr_document_loader"
    description: str = "加载OCR Markdown文档并提供语义搜索功能，用于查找原始公式和内容"
    args_schema: type[BaseModel] = OCRDocumentLoaderInput
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 创建底层的文本分块索引工具（使用object.__setattr__来避免Pydantic验证）
        object.__setattr__(self, 'indexer_tool', create_text_chunk_indexer_tool(auto_embedding=True))
        object.__setattr__(self, 'current_document', None)
        object.__setattr__(self, 'current_file_path', None)
    
    def _read_ocr_file(self, file_path: str) -> str:
        """读取OCR Markdown文件"""
        try:
            path = Path(file_path)
            if not path.exists():
                raise FileNotFoundError(f"OCR文件不存在: {file_path}")
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
            
            raise ValueError(f"无法使用支持的编码读取OCR文件: {file_path}")
            
        except Exception as e:
            raise RuntimeError(f"读取OCR文件时发生错误: {str(e)}")
    
    def _format_result(self, indexer_result: str, file_path: str, query: Optional[str] = None) -> str:
        """格式化结果，添加OCR文档上下文信息"""
        try:
            result_data = json.loads(indexer_result)
            
            # 添加OCR文档的元信息
            result_data["document_type"] = "OCR论文文档"
            result_data["source_file"] = file_path
            result_data["document_description"] = "这是通过OCR技术从PDF论文转换而来的原始Markdown文档，包含论文的完整文本和公式信息"
            
            if query:
                result_data["query_context"] = f"用户查询: {query}"
                result_data["search_purpose"] = "查找与分析文档中错误公式对应的原始OCR公式内容"
            
            # 如果有搜索结果，添加使用指导
            if result_data.get("search_results"):
                result_data["usage_note"] = "以下搜索结果来自原始OCR论文，可用于对比和修正分析文档中的公式错误"
            
            return json.dumps(result_data, indent=2, ensure_ascii=False)
            
        except json.JSONDecodeError:
            # 如果原始结果不是有效JSON，包装成JSON格式
            return json.dumps({
                "error": "索引工具返回格式错误",
                "raw_result": indexer_result,
                "document_type": "OCR论文文档",
                "source_file": file_path
            }, ensure_ascii=False)
    
    def _run(self, ocr_file_path: str, query: Optional[str] = None) -> str:
        """执行OCR文档加载和查询"""
        try:
            # 验证文件路径
            if not ocr_file_path:
                return json.dumps({
                    "error": "OCR文件路径不能为空",
                    "document_type": "OCR论文文档"
                }, ensure_ascii=False)
            
            # 读取OCR文档内容
            try:
                ocr_content = self._read_ocr_file(ocr_file_path)
            except Exception as e:
                return json.dumps({
                    "error": f"读取OCR文件失败: {str(e)}",
                    "file_path": ocr_file_path,
                    "document_type": "OCR论文文档"
                }, ensure_ascii=False)
            
            # 验证文档内容
            if not ocr_content.strip():
                return json.dumps({
                    "error": "OCR文件内容为空",
                    "file_path": ocr_file_path,
                    "document_type": "OCR论文文档"
                }, ensure_ascii=False)
            
            # 缓存当前文档信息
            object.__setattr__(self, 'current_document', ocr_content)
            object.__setattr__(self, 'current_file_path', ocr_file_path)
            
            # 使用底层索引工具处理文档
            indexer_tool = getattr(self, 'indexer_tool')
            indexer_result = indexer_tool._run(
                text_content=ocr_content,
                query=query
            )
            
            # 格式化并返回结果
            formatted_result = self._format_result(indexer_result, ocr_file_path, query)
            
            logger.info(f"OCR文档加载完成: {ocr_file_path}")
            if query:
                logger.info(f"查询执行完成: {query}")
            
            return formatted_result
            
        except Exception as e:
            logger.error(f"OCR文档加载工具执行时发生错误: {str(e)}")
            return json.dumps({
                "error": f"OCR文档加载失败: {str(e)}",
                "file_path": ocr_file_path,
                "document_type": "OCR论文文档"
            }, ensure_ascii=False)
    
    def get_current_document_info(self) -> Dict[str, Any]:
        """获取当前已加载文档的信息"""
        current_document = getattr(self, 'current_document', None)
        current_file_path = getattr(self, 'current_file_path', None)
        
        if not current_document:
            return {"status": "no_document_loaded"}
        
        return {
            "status": "document_loaded",
            "file_path": current_file_path,
            "content_length": len(current_document),
            "document_type": "OCR论文文档"
        }
    
    def clear_cache(self):
        """清除缓存的文档数据"""
        object.__setattr__(self, 'current_document', None)
        object.__setattr__(self, 'current_file_path', None)
        indexer_tool = getattr(self, 'indexer_tool', None)
        if indexer_tool and hasattr(indexer_tool, 'clear_cache'):
            indexer_tool.clear_cache()
        logger.info("OCR文档缓存已清除")


def create_ocr_document_loader_tool():
    """创建OCR文档加载工具实例
    
    Returns:
        OCRDocumentLoaderTool: 配置好的OCR文档加载工具实例
    """
    return OCRDocumentLoaderTool()


# 便捷函数，用于直接加载OCR文档
def load_ocr_document(ocr_file_path: str, query: Optional[str] = None) -> Dict[str, Any]:
    """便捷函数：直接加载OCR文档并返回解析结果
    
    Args:
        ocr_file_path: OCR文件路径
        query: 可选的查询字符串
        
    Returns:
        Dict: 包含文档内容和搜索结果的字典
    """
    tool = create_ocr_document_loader_tool()
    result_json = tool._run(ocr_file_path, query)
    
    try:
        return json.loads(result_json)
    except json.JSONDecodeError:
        return {"error": "结果解析失败", "raw_result": result_json}


# 测试代码
if __name__ == "__main__":
    # 创建工具实例
    tool = create_ocr_document_loader_tool()
    
    # 测试文件路径
    test_file = "/mnt/nfs_share/code/homesystem/data/paper_analyze/2412.03572/2412.03572_paddleocr.md"
    
    if os.path.exists(test_file):
        print("测试OCR文档加载...")
        result = tool._run(test_file)
        print("结果:", result[:500], "...")
        
        print("\n测试查询功能...")
        query_result = tool._run(test_file, "Navigation World Model")
        print("查询结果:", query_result[:500], "...")
    else:
        print(f"测试文件不存在: {test_file}")