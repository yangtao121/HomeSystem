"""
长文本编辑工具

基于LangGraph和LangChain的最佳实践，提供安全、高效的行级文本编辑功能。
支持单行和行范围编辑，具备哈希验证、冲突检测等安全特性。
专门为LLM交互优化，使用JSON格式的编辑操作。
"""

import json
import hashlib
from typing import Dict, Any, List, Type, Optional, Union
from enum import Enum
from dataclasses import dataclass, asdict
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field, validator
import logging

logger = logging.getLogger(__name__)


class OperationType(str, Enum):
    """编辑操作类型枚举"""
    REPLACE = "replace"
    INSERT_AFTER = "insert_after"
    INSERT_BEFORE = "insert_before"
    DELETE = "delete"


@dataclass
class EditOperation:
    """编辑操作数据类
    
    定义单个编辑操作的结构，包含操作类型、位置和内容信息。
    """
    operation_type: OperationType
    start_line: int
    end_line: Optional[int] = None
    new_content: Optional[str] = None
    operation_id: Optional[str] = None
    
    def __post_init__(self):
        """后处理初始化"""
        # 自动生成操作ID
        if self.operation_id is None:
            content_hash = hashlib.md5(
                f"{self.operation_type}_{self.start_line}_{self.end_line}_{self.new_content}".encode()
            ).hexdigest()[:8]
            self.operation_id = f"op_{content_hash}"
        
        # 验证操作参数
        self._validate_operation()
    
    def _validate_operation(self):
        """验证操作参数的合法性"""
        if self.start_line < 1:
            raise ValueError("起始行号必须大于等于1")
        
        if self.end_line is not None and self.end_line < self.start_line:
            raise ValueError("结束行号不能小于起始行号")
        
        if self.operation_type == OperationType.REPLACE and self.new_content is None:
            raise ValueError("替换操作必须提供新内容")
        
        if self.operation_type in [OperationType.INSERT_AFTER, OperationType.INSERT_BEFORE]:
            if self.new_content is None:
                raise ValueError("插入操作必须提供新内容")
            if self.end_line is not None:
                raise ValueError("插入操作不应指定结束行号")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return asdict(self)


class TextEditorInput(BaseModel):
    """文本编辑工具输入模型"""
    content: str = Field(description="要编辑的文本内容")
    operation_type: OperationType = Field(description="编辑操作类型")
    start_line: int = Field(description="起始行号（从1开始）", ge=1)
    end_line: Optional[int] = Field(default=None, description="结束行号（用于范围操作）")
    new_content: Optional[str] = Field(default=None, description="新内容（用于替换和插入操作）")
    validate_hash: Optional[str] = Field(default=None, description="内容哈希值（用于验证）")
    
    @validator('end_line')
    def validate_end_line(cls, v, values):
        """验证结束行号"""
        if v is not None and 'start_line' in values and v < values['start_line']:
            raise ValueError('结束行号不能小于起始行号')
        return v
    
    @validator('new_content')
    def validate_new_content(cls, v, values):
        """验证新内容"""
        if 'operation_type' in values:
            op_type = values['operation_type']
            if op_type == OperationType.REPLACE and v is None:
                raise ValueError('替换操作必须提供新内容')
            if op_type in [OperationType.INSERT_AFTER, OperationType.INSERT_BEFORE] and v is None:
                raise ValueError('插入操作必须提供新内容')
        return v


class TextEditor:
    """文本编辑器核心类
    
    提供安全、高效的文本编辑功能，支持多种编辑操作类型。
    具备完整的验证机制和错误处理能力。
    """
    
    def __init__(self):
        self.original_content = ""
        self.current_content = ""
        self.lines = []
        self.content_hash = ""
        self.edit_history = []
    
    def load_text(self, content: str) -> Dict[str, Any]:
        """加载文本内容"""
        try:
            self.original_content = content
            self.current_content = content
            self.lines = content.splitlines(keepends=True)
            self.content_hash = self._calculate_hash(content)
            self.edit_history = []
            
            return {
                "success": True,
                "total_lines": len(self.lines),
                "content_hash": self.content_hash,
                "message": "文本加载成功"
            }
        except Exception as e:
            logger.error(f"加载文本时发生错误: {str(e)}")
            return {
                "success": False,
                "error": f"加载文本失败: {str(e)}"
            }
    
    def edit_lines(self, operation: EditOperation, validate_hash: Optional[str] = None) -> Dict[str, Any]:
        """执行行编辑操作"""
        try:
            # 哈希验证
            if validate_hash and validate_hash != self.content_hash:
                return {
                    "success": False,
                    "error": "内容哈希验证失败，可能存在并发修改",
                    "expected_hash": validate_hash,
                    "actual_hash": self.content_hash
                }
            
            # 行号边界检查
            max_line = len(self.lines)
            if operation.start_line > max_line + 1:
                return {
                    "success": False,
                    "error": f"起始行号超出范围，最大行号: {max_line}"
                }
            
            if operation.end_line and operation.end_line > max_line:
                return {
                    "success": False,
                    "error": f"结束行号超出范围，最大行号: {max_line}"
                }
            
            # 备份当前状态
            backup_lines = self.lines.copy()
            backup_content = self.current_content
            
            # 执行编辑操作
            result = self._execute_operation(operation)
            
            if result["success"]:
                # 更新内容和哈希
                self.current_content = ''.join(self.lines)
                self.content_hash = self._calculate_hash(self.current_content)
                
                # 记录历史
                self.edit_history.append({
                    "operation": operation.to_dict(),
                    "timestamp": self._get_timestamp(),
                    "result": result
                })
                
                result["new_hash"] = self.content_hash
                result["total_lines"] = len(self.lines)
            else:
                # 恢复备份
                self.lines = backup_lines
                self.current_content = backup_content
            
            return result
            
        except Exception as e:
            logger.error(f"执行编辑操作时发生错误: {str(e)}")
            return {
                "success": False,
                "error": f"编辑操作失败: {str(e)}"
            }
    
    def _execute_operation(self, operation: EditOperation) -> Dict[str, Any]:
        """执行具体的编辑操作"""
        try:
            start_idx = operation.start_line - 1  # 转换为0索引
            
            if operation.operation_type == OperationType.REPLACE:
                return self._replace_lines(start_idx, operation.end_line, operation.new_content)
            elif operation.operation_type == OperationType.INSERT_AFTER:
                return self._insert_after_line(start_idx, operation.new_content)
            elif operation.operation_type == OperationType.INSERT_BEFORE:
                return self._insert_before_line(start_idx, operation.new_content)
            elif operation.operation_type == OperationType.DELETE:
                return self._delete_lines(start_idx, operation.end_line)
            else:
                return {
                    "success": False,
                    "error": f"不支持的操作类型: {operation.operation_type}"
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"执行操作时发生错误: {str(e)}"
            }
    
    def _replace_lines(self, start_idx: int, end_line: Optional[int], new_content: str) -> Dict[str, Any]:
        """替换指定行"""
        try:
            if end_line is None:
                end_idx = start_idx + 1
            else:
                end_idx = end_line
            
            # 确保新内容以换行符结尾（如果不是最后一行）
            if not new_content.endswith('\n') and end_idx < len(self.lines):
                new_content += '\n'
            
            # 记录被替换的内容
            replaced_content = ''.join(self.lines[start_idx:end_idx])
            
            # 执行替换
            new_lines = new_content.splitlines(keepends=True)
            self.lines[start_idx:end_idx] = new_lines
            
            return {
                "success": True,
                "operation": "replace",
                "affected_lines": f"{start_idx + 1}-{end_idx}",
                "lines_added": len(new_lines),
                "lines_removed": end_idx - start_idx,
                "replaced_content": replaced_content,
                "message": f"成功替换第{start_idx + 1}到{end_idx}行"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"替换操作失败: {str(e)}"
            }
    
    def _insert_after_line(self, line_idx: int, new_content: str) -> Dict[str, Any]:
        """在指定行后插入内容"""
        try:
            # 确保新内容以换行符结尾
            if not new_content.endswith('\n'):
                new_content += '\n'
            
            new_lines = new_content.splitlines(keepends=True)
            insert_pos = line_idx + 1
            
            self.lines[insert_pos:insert_pos] = new_lines
            
            return {
                "success": True,
                "operation": "insert_after",
                "insert_position": insert_pos + 1,  # 转换回1索引
                "lines_added": len(new_lines),
                "message": f"成功在第{line_idx + 1}行后插入{len(new_lines)}行"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"插入操作失败: {str(e)}"
            }
    
    def _insert_before_line(self, line_idx: int, new_content: str) -> Dict[str, Any]:
        """在指定行前插入内容"""
        try:
            # 确保新内容以换行符结尾
            if not new_content.endswith('\n'):
                new_content += '\n'
            
            new_lines = new_content.splitlines(keepends=True)
            
            self.lines[line_idx:line_idx] = new_lines
            
            return {
                "success": True,
                "operation": "insert_before",
                "insert_position": line_idx + 1,  # 转换回1索引
                "lines_added": len(new_lines),
                "message": f"成功在第{line_idx + 1}行前插入{len(new_lines)}行"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"插入操作失败: {str(e)}"
            }
    
    def _delete_lines(self, start_idx: int, end_line: Optional[int]) -> Dict[str, Any]:
        """删除指定行"""
        try:
            if end_line is None:
                end_idx = start_idx + 1
            else:
                end_idx = end_line
            
            # 记录被删除的内容
            deleted_content = ''.join(self.lines[start_idx:end_idx])
            lines_removed = end_idx - start_idx
            
            # 执行删除
            del self.lines[start_idx:end_idx]
            
            return {
                "success": True,
                "operation": "delete",
                "affected_lines": f"{start_idx + 1}-{end_idx}",
                "lines_removed": lines_removed,
                "deleted_content": deleted_content,
                "message": f"成功删除第{start_idx + 1}到{end_idx}行"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"删除操作失败: {str(e)}"
            }
    
    def get_preview(self, start_line: int = 1, end_line: Optional[int] = None, 
                   context_lines: int = 3) -> Dict[str, Any]:
        """获取文本预览"""
        try:
            max_line = len(self.lines)
            
            if end_line is None:
                end_line = max_line
            
            # 扩展上下文
            preview_start = max(1, start_line - context_lines)
            preview_end = min(max_line, end_line + context_lines)
            
            preview_lines = []
            for i in range(preview_start - 1, preview_end):
                line_content = self.lines[i].rstrip('\n') if i < len(self.lines) else ""
                line_num = i + 1
                
                # 标记目标行
                if start_line <= line_num <= end_line:
                    prefix = ">>> "
                else:
                    prefix = "    "
                
                preview_lines.append(f"{prefix}{line_num:4d}: {line_content}")
            
            return {
                "success": True,
                "preview": "\n".join(preview_lines),
                "preview_range": f"{preview_start}-{preview_end}",
                "target_range": f"{start_line}-{end_line}",
                "total_lines": max_line
            }
            
        except Exception as e:
            logger.error(f"获取预览时发生错误: {str(e)}")
            return {
                "success": False,
                "error": f"获取预览失败: {str(e)}"
            }
    
    def get_current_content(self) -> str:
        """获取当前内容"""
        return self.current_content
    
    def get_edit_history(self) -> List[Dict[str, Any]]:
        """获取编辑历史"""
        return self.edit_history.copy()
    
    def validate_content_hash(self, expected_hash: str) -> bool:
        """验证内容哈希"""
        return self.content_hash == expected_hash
    
    def _calculate_hash(self, content: str) -> str:
        """计算内容SHA-256哈希值"""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    def _get_timestamp(self) -> str:
        """获取当前时间戳"""
        from datetime import datetime
        return datetime.now().isoformat()


class TextEditorTool(BaseTool):
    """长文本编辑工具
    
    为LLM提供安全、高效的行级文本编辑功能。
    支持多种编辑操作类型和完整的验证机制。
    """
    
    name: str = "text_editor"
    description: str = "长文本行级编辑工具，支持替换、插入、删除等操作，具备哈希验证和冲突检测功能"
    args_schema: Type[BaseModel] = TextEditorInput
    editor: Any = Field(default_factory=TextEditor, exclude=True)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
    
    def _run(self, content: str, operation_type: OperationType, start_line: int,
             end_line: Optional[int] = None, new_content: Optional[str] = None,
             validate_hash: Optional[str] = None) -> str:
        """执行文本编辑操作"""
        try:
            # 加载文本内容
            load_result = self.editor.load_text(content)
            if not load_result["success"]:
                return json.dumps(load_result, ensure_ascii=False)
            
            # 创建编辑操作
            operation = EditOperation(
                operation_type=operation_type,
                start_line=start_line,
                end_line=end_line,
                new_content=new_content
            )
            
            # 执行编辑
            edit_result = self.editor.edit_lines(operation, validate_hash)
            
            # 获取预览
            if edit_result["success"]:
                preview_result = self.editor.get_preview(start_line, end_line or start_line)
                edit_result["preview"] = preview_result.get("preview", "")
                edit_result["edited_content"] = self.editor.get_current_content()
            
            return json.dumps(edit_result, indent=2, ensure_ascii=False)
            
        except Exception as e:
            logger.error(f"文本编辑工具执行时发生错误: {str(e)}")
            return json.dumps({
                "success": False,
                "error": f"工具执行失败: {str(e)}"
            }, ensure_ascii=False)


def create_text_editor_tool():
    """创建文本编辑工具实例
    
    Returns:
        TextEditorTool: 配置好的文本编辑工具实例
    """
    return TextEditorTool()