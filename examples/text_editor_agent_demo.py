#!/usr/bin/env python3
"""
文本编辑Agent集成演示

展示如何在LangGraph agent中集成和使用长文本编辑工具。
这个示例创建一个简单的agent，能够接收用户的文本编辑指令并执行相应操作。
"""

import sys
import os
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from HomeSystem.graph.tool.text_editor import (
    TextEditorTool, EditOperation, OperationType, create_text_editor_tool
)


@dataclass
class EditRequest:
    """编辑请求数据结构"""
    operation: str
    start_line: int
    end_line: Optional[int] = None
    new_content: Optional[str] = None
    description: str = ""


class SimpleTextEditAgent:
    """简单的文本编辑Agent
    
    演示如何集成文本编辑工具到agent系统中。
    在实际应用中，这可能是一个完整的LangGraph agent。
    """
    
    def __init__(self):
        self.text_editor_tool = create_text_editor_tool()
        self.current_content = ""
        self.edit_history = []
    
    def load_document(self, content: str) -> Dict[str, Any]:
        """加载文档内容"""
        self.current_content = content
        return {
            "success": True,
            "message": f"已加载文档，总行数: {len(content.splitlines())}",
            "content": content
        }
    
    def execute_edit(self, request: EditRequest) -> Dict[str, Any]:
        """执行编辑请求"""
        try:
            # 映射操作类型
            operation_map = {
                "replace": OperationType.REPLACE,
                "insert_after": OperationType.INSERT_AFTER,
                "insert_before": OperationType.INSERT_BEFORE,
                "delete": OperationType.DELETE
            }
            
            if request.operation not in operation_map:
                return {
                    "success": False,
                    "error": f"不支持的操作类型: {request.operation}"
                }
            
            operation_type = operation_map[request.operation]
            
            # 使用工具执行编辑
            result_str = self.text_editor_tool._run(
                content=self.current_content,
                operation_type=operation_type,
                start_line=request.start_line,
                end_line=request.end_line,
                new_content=request.new_content
            )
            
            result = json.loads(result_str)
            
            if result["success"]:
                # 更新当前内容
                self.current_content = result["edited_content"]
                
                # 记录编辑历史
                self.edit_history.append({
                    "request": request,
                    "result": result,
                    "timestamp": self._get_timestamp()
                })
                
                return {
                    "success": True,
                    "message": result.get("message", "编辑成功"),
                    "preview": result.get("preview", ""),
                    "operation_details": {
                        "operation": request.operation,
                        "affected_lines": result.get("affected_lines", ""),
                        "description": request.description
                    }
                }
            else:
                return result
                
        except Exception as e:
            return {
                "success": False,
                "error": f"执行编辑时发生错误: {str(e)}"
            }
    
    def get_document_preview(self, start_line: int = 1, lines_count: int = 10) -> str:
        """获取文档预览"""
        lines = self.current_content.splitlines()
        end_line = min(start_line + lines_count - 1, len(lines))
        
        preview_lines = []
        for i in range(start_line - 1, end_line):
            if i < len(lines):
                preview_lines.append(f"{i + 1:4d}: {lines[i]}")
        
        return "\n".join(preview_lines)
    
    def get_edit_history(self) -> List[Dict[str, Any]]:
        """获取编辑历史"""
        return self.edit_history.copy()
    
    def get_current_content(self) -> str:
        """获取当前内容"""
        return self.current_content
    
    def _get_timestamp(self) -> str:
        """获取时间戳"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def demo_basic_editing():
    """演示基础编辑功能"""
    print("=== 基础编辑功能演示 ===")
    
    agent = SimpleTextEditAgent()
    
    # 加载示例文档
    sample_doc = """# 项目文档

## 介绍
这是一个示例项目的文档。

## 功能列表
1. 功能A
2. 功能B
3. 功能C

## 使用方法
请参考用户手册。

## 联系方式
email: example@example.com"""
    
    load_result = agent.load_document(sample_doc)
    print(f"✅ {load_result['message']}")
    print()
    
    print("原始文档:")
    print(agent.get_document_preview(lines_count=20))
    print("\n" + "="*50 + "\n")
    
    # 1. 替换操作 - 修改标题
    print("1. 替换操作 - 修改项目标题")
    replace_request = EditRequest(
        operation="replace",
        start_line=1,
        new_content="# 高级项目文档",
        description="将标题从'项目文档'改为'高级项目文档'"
    )
    
    result = agent.execute_edit(replace_request)
    if result["success"]:
        print(f"✅ {result['message']}")
        print("预览:")
        print(result["preview"])
    else:
        print(f"❌ {result.get('error', '操作失败')}")
    print()
    
    # 2. 插入操作 - 添加新功能
    print("2. 插入操作 - 在功能列表中添加新功能")
    insert_request = EditRequest(
        operation="insert_after",
        start_line=9,
        new_content="4. 功能D - 新增功能",
        description="在功能C后添加功能D"
    )
    
    result = agent.execute_edit(insert_request)
    if result["success"]:
        print(f"✅ {result['message']}")
        print("预览:")
        print(result["preview"])
    else:
        print(f"❌ {result.get('error', '操作失败')}")
    print()
    
    # 3. 多行替换 - 更新使用方法部分
    print("3. 多行替换 - 更新使用方法部分")
    multi_replace_request = EditRequest(
        operation="replace",
        start_line=12,
        end_line=13,
        new_content="""## 使用方法
详细的使用说明如下：
1. 首先下载软件
2. 安装依赖包
3. 运行主程序""",
        description="将简单的使用方法说明替换为详细步骤"
    )
    
    result = agent.execute_edit(multi_replace_request)
    if result["success"]:
        print(f"✅ {result['message']}")
        print("预览:")
        print(result["preview"])
    else:
        print(f"❌ {result.get('error', '操作失败')}")
    print()
    
    # 显示最终文档
    print("最终文档:")
    print("="*50)
    print(agent.get_current_content())
    print("="*50)
    
    # 显示编辑历史
    print("\n编辑历史:")
    history = agent.get_edit_history()
    for i, entry in enumerate(history, 1):
        req = entry["request"]
        print(f"{i}. [{entry['timestamp']}] {req.operation}: {req.description}")


def demo_error_handling():
    """演示错误处理"""
    print("\n=== 错误处理演示 ===")
    
    agent = SimpleTextEditAgent()
    agent.load_document("第一行\n第二行\n第三行")
    
    # 测试行号越界
    print("1. 测试行号越界")
    error_request = EditRequest(
        operation="replace",
        start_line=10,
        new_content="不应该成功",
        description="尝试编辑不存在的行"
    )
    
    result = agent.execute_edit(error_request)
    if not result["success"]:
        print(f"✅ 正确处理错误: {result['error']}")
    else:
        print("❌ 应该失败但成功了")
    
    # 测试无效操作类型
    print("\n2. 测试无效操作类型")
    invalid_request = EditRequest(
        operation="invalid_operation",
        start_line=1,
        description="尝试使用无效的操作类型"
    )
    
    result = agent.execute_edit(invalid_request)
    if not result["success"]:
        print(f"✅ 正确处理错误: {result['error']}")
    else:
        print("❌ 应该失败但成功了")


def demo_agent_workflow():
    """演示Agent工作流程"""
    print("\n=== Agent工作流程演示 ===")
    
    agent = SimpleTextEditAgent()
    
    # 模拟Agent接收用户指令并执行编辑的完整流程
    print("模拟用户请求：'请帮我创建一个简单的Python脚本模板'")
    
    # 1. 创建基础模板
    template = """#!/usr/bin/env python3
\"\"\"
脚本描述
\"\"\"

def main():
    pass

if __name__ == "__main__":
    main()"""
    
    agent.load_document(template)
    print("✅ 创建了基础Python脚本模板")
    
    # 2. 根据用户需求进行定制
    print("\n用户要求：'添加日志功能和错误处理'")
    
    # 添加导入语句
    import_request = EditRequest(
        operation="insert_after",
        start_line=1,
        new_content="import logging\nimport sys",
        description="添加必要的导入语句"
    )
    agent.execute_edit(import_request)
    
    # 更新主函数
    main_function_request = EditRequest(
        operation="replace",
        start_line=8,
        end_line=9,
        new_content="""def main():
    # 配置日志
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    try:
        logger.info("脚本开始执行")
        # 在这里添加你的代码
        print("Hello, World!")
        logger.info("脚本执行完成")
    except Exception as e:
        logger.error(f"执行过程中发生错误: {e}")
        sys.exit(1)""",
        description="更新主函数，添加日志和错误处理"
    )
    agent.execute_edit(main_function_request)
    
    print("✅ 已根据用户需求定制脚本")
    
    # 显示最终结果
    print("\n最终生成的Python脚本:")
    print("="*50)
    print(agent.get_current_content())
    print("="*50)


def run_integration_demo():
    """运行完整的集成演示"""
    print("文本编辑Agent集成演示")
    print("="*60)
    
    demo_basic_editing()
    demo_error_handling()
    demo_agent_workflow()
    
    print("\n" + "="*60)
    print("集成演示完成！")
    print("\n✨ 长文本编辑工具已成功集成到Agent系统中！")
    print("📝 该工具支持：")
    print("   • 安全的行级编辑操作")
    print("   • 多种操作类型（替换、插入、删除）")
    print("   • 哈希验证和冲突检测")
    print("   • 完整的错误处理")
    print("   • 编辑预览和历史记录")


if __name__ == "__main__":
    run_integration_demo()