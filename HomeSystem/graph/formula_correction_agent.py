"""
公式纠错智能体

基于LangGraph的论文公式纠错智能体，用于修复分析文档中的公式错误。
使用标准工具调用模式，集成数学公式提取、OCR文档查询和文本编辑功能。
"""

import json
import os
from typing import Annotated, Any, Dict, List, Optional
from typing_extensions import TypedDict
from pathlib import Path

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage, BaseMessage
from loguru import logger

from .base_graph import BaseGraph
from .llm_factory import get_llm
from .tool.math_formula_extractor import create_math_formula_extractor_tool
from .tool.ocr_document_loader import create_ocr_document_loader_tool
from .tool.text_editor import create_text_editor_tool


class FormulaCorrectionState(TypedDict):
    """公式纠错状态"""
    # 输入数据
    analysis_file_path: str                         # 分析文档路径
    ocr_file_path: str                             # OCR原文档路径
    analysis_content: str                          # 分析文档内容
    ocr_content: str                              # OCR文档内容
    
    # 提取的公式信息
    extracted_formulas: Optional[List[Dict]]       # 提取的公式列表
    
    # LangGraph消息历史
    messages: Annotated[list, add_messages]        # 对话历史
    
    # 纠错结果
    corrected_content: Optional[str]               # 纠错后的内容
    corrections_applied: Optional[List[Dict]]      # 应用的纠错记录
    
    # 执行状态
    is_complete: bool                              # 是否完成纠错
    current_step: str                              # 当前步骤


class FormulaCorrectionConfig:
    """公式纠错配置类"""
    
    def __init__(self,
                 correction_model: str = "deepseek.DeepSeek_V3",
                 memory_enabled: bool = True,
                 max_correction_rounds: int = 3,
                 custom_settings: Optional[Dict[str, Any]] = None):
        
        self.correction_model = correction_model      # 纠错LLM模型
        self.memory_enabled = memory_enabled          # 是否启用内存
        self.max_correction_rounds = max_correction_rounds  # 最大纠错轮数
        self.custom_settings = custom_settings or {}
    
    @classmethod
    def load_from_file(cls, config_path: str) -> "FormulaCorrectionConfig":
        """从配置文件加载配置"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            return cls(**config_data)
        except Exception as e:
            logger.warning(f"配置文件加载失败，使用默认配置: {e}")
            return cls()


class FormulaCorrectionAgent(BaseGraph):
    """公式纠错智能体
    
    功能：
    1. 提取分析文档中的所有独行公式
    2. 使用OCR文档作为参考，查找原始公式
    3. 通过LLM分析和纠错公式
    4. 应用纠错到分析文档
    """
    
    def __init__(self,
                 config: Optional[FormulaCorrectionConfig] = None,
                 config_path: Optional[str] = None,
                 **kwargs):
        
        super().__init__(**kwargs)
        
        # 加载配置
        if config_path:
            self.config = FormulaCorrectionConfig.load_from_file(config_path)
        elif config:
            self.config = config
        else:
            self.config = FormulaCorrectionConfig()
        
        logger.info(f"初始化公式纠错智能体")
        logger.info(f"纠错模型: {self.config.correction_model}")
        
        # 创建纠错LLM
        self.correction_llm = get_llm(self.config.correction_model)
        
        # 设置内存管理
        self.memory = MemorySaver() if self.config.memory_enabled else None
        
        # 工具将在运行时创建
        self.formula_extractor = None
        self.ocr_loader = None
        self.text_editor = None
        self.llm_with_tools = None
        self.tool_node = None
        
        # 构建图（将在纠错时动态完成）
        self.agent = None
        
        logger.info("公式纠错智能体初始化完成")
    
    def _build_graph_with_tools(self, tools: List[Any]) -> None:
        """使用工具构建LangGraph工作流"""
        graph = StateGraph(FormulaCorrectionState)
        
        # 添加节点
        graph.add_node("initialize", self._initialize_node)
        graph.add_node("extract_formulas", self._extract_formulas_node)
        graph.add_node("load_ocr_reference", self._load_ocr_reference_node)
        graph.add_node("correction_analysis", self._correction_analysis_node)
        graph.add_node("finalize", self._finalize_node)
        
        # 添加工具节点
        self.tool_node = ToolNode(tools)
        graph.add_node("call_tools", self._call_tools_node)
        
        # 构建工作流
        graph.add_edge(START, "initialize")
        graph.add_edge("initialize", "extract_formulas")
        graph.add_edge("extract_formulas", "load_ocr_reference")
        graph.add_edge("load_ocr_reference", "correction_analysis")
        
        # 纠错分析的条件分支
        graph.add_conditional_edges(
            "correction_analysis",
            self._should_continue_correction,
            {
                "call_tools": "call_tools",      # 调用工具
                "continue": "correction_analysis", # 继续分析
                "finalize": "finalize",          # 完成纠错
            }
        )
        
        # 工具调用后回到分析节点
        graph.add_edge("call_tools", "correction_analysis")
        graph.add_edge("finalize", END)
        
        # 编译图
        try:
            self.agent = graph.compile(checkpointer=self.memory)
            logger.info("✅ 公式纠错LangGraph图编译成功")
        except Exception as e:
            logger.error(f"❌ LangGraph图编译失败: {e}")
            raise
    
    def _initialize_node(self, state: FormulaCorrectionState) -> Dict[str, Any]:
        """初始化节点"""
        logger.info("🚀 开始公式纠错流程")
        logger.info(f"分析文档: {state['analysis_file_path']}")
        logger.info(f"OCR参考文档: {state['ocr_file_path']}")
        
        return {
            "current_step": "initialized",
            "is_complete": False,
            "messages": []
        }
    
    def _extract_formulas_node(self, state: FormulaCorrectionState) -> Dict[str, Any]:
        """提取公式节点"""
        logger.info("📐 开始提取分析文档中的公式")
        
        try:
            # 使用公式提取工具
            formula_result = self.formula_extractor._run(
                markdown_text=state["analysis_content"]
            )
            
            # 解析结果
            try:
                formula_data = json.loads(formula_result)
                extracted_formulas = formula_data.get("formulas", [])
                logger.info(f"✅ 提取到 {len(extracted_formulas)} 个公式")
                
            except json.JSONDecodeError:
                logger.error("公式提取结果解析失败")
                extracted_formulas = []
            
            return {
                "extracted_formulas": extracted_formulas,
                "current_step": "formulas_extracted",
                "messages": [SystemMessage(content=f"从分析文档中提取到 {len(extracted_formulas)} 个独行公式")]
            }
            
        except Exception as e:
            logger.error(f"公式提取失败: {e}")
            return {
                "extracted_formulas": [],
                "current_step": "formula_extraction_failed",
                "messages": [SystemMessage(content=f"公式提取失败: {str(e)}")]
            }
    
    def _load_ocr_reference_node(self, state: FormulaCorrectionState) -> Dict[str, Any]:
        """加载OCR参考文档节点"""
        logger.info("📖 加载OCR参考文档")
        
        try:
            # 加载OCR文档并创建索引
            ocr_result = self.ocr_loader._run(
                ocr_file_path=state["ocr_file_path"]
            )
            
            logger.info("✅ OCR参考文档加载完成")
            
            return {
                "current_step": "ocr_loaded",
                "messages": [SystemMessage(content="OCR参考文档已加载并建立索引，可以进行公式对比和纠错")]
            }
            
        except Exception as e:
            logger.error(f"OCR文档加载失败: {e}")
            return {
                "current_step": "ocr_loading_failed",
                "messages": [SystemMessage(content=f"OCR文档加载失败: {str(e)}")]
            }
    
    def _correction_analysis_node(self, state: FormulaCorrectionState) -> Dict[str, Any]:
        """纠错分析节点"""
        logger.info("🔍 开始公式纠错分析")
        
        messages = state["messages"]
        
        try:
            # 如果是第一次进入纠错分析，创建初始提示
            if state.get("current_step") == "ocr_loaded":
                correction_prompt = self._generate_correction_prompt(state)
                messages.append(SystemMessage(content=correction_prompt))
            
            # 确保llm_with_tools已初始化
            if self.llm_with_tools is None:
                logger.error("❌ LLM with tools not initialized")
                return {"messages": [AIMessage(content="LLM工具未初始化")]}
            
            # LLM分析和纠错
            response = self.llm_with_tools.invoke(messages)
            
            logger.info(f"💬 LLM纠错响应: {type(response).__name__}")
            
            # 检查工具调用
            tool_calls = getattr(response, 'tool_calls', None)
            if tool_calls:
                logger.info(f"🔧 LLM决定调用 {len(tool_calls)} 个工具")
                for i, tool_call in enumerate(tool_calls):
                    try:
                        if hasattr(tool_call, 'get'):
                            tool_name = tool_call.get('name', 'unknown')
                            tool_args = tool_call.get('args', {})
                        else:
                            tool_name = getattr(tool_call, 'name', str(type(tool_call).__name__))
                            tool_args = getattr(tool_call, 'args', {})
                        
                        logger.info(f"  [{i+1}] 工具: {tool_name}")
                        logger.info(f"      参数: {str(tool_args)[:200]}...")
                    except Exception as e:
                        logger.warning(f"      无法解析工具调用 {i+1}: {e}")
                        logger.info(f"      原始工具调用: {str(tool_call)[:200]}...")
            
            return {
                "messages": [response],
                "current_step": "correction_in_progress"
            }
            
        except Exception as e:
            logger.error(f"❌ 纠错分析失败: {e}")
            error_message = AIMessage(content=f"纠错分析过程中出现错误: {str(e)}")
            return {"messages": [error_message]}
    
    def _call_tools_node(self, state: FormulaCorrectionState) -> Dict[str, Any]:
        """工具调用节点（带日志）"""
        logger.info("🔧 执行工具调用...")
        
        messages = state["messages"]
        if messages:
            last_message = messages[-1]
            tool_calls = getattr(last_message, 'tool_calls', None)
            if tool_calls:
                logger.info(f"准备执行 {len(tool_calls)} 个工具调用")
        
        # 执行工具调用
        try:
            result = self.tool_node.invoke(state)
            new_messages = result.get("messages", [])
            
            logger.info(f"工具执行完成，返回 {len(new_messages)} 条消息")
            
            # 打印工具结果
            for i, msg in enumerate(new_messages):
                if isinstance(msg, ToolMessage):
                    tool_name = getattr(msg, 'name', 'unknown')
                    content_preview = str(msg.content)[:300] if msg.content else "<empty>"
                    logger.info(f"  工具 [{i+1}] {tool_name} 结果: {content_preview}...")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ 工具调用失败: {e}")
            import traceback
            logger.error(f"错误堆栈: {traceback.format_exc()}")
            return {"messages": []}
    
    def _finalize_node(self, state: FormulaCorrectionState) -> Dict[str, Any]:
        """完成纠错节点"""
        logger.info("✅ 完成公式纠错流程")
        
        # 从消息历史中提取最终的纠错内容
        messages = state["messages"]
        corrected_content = state["analysis_content"]  # 默认使用原内容
        corrections_applied = []
        
        # 查找文本编辑工具的使用记录
        for message in messages:
            if isinstance(message, ToolMessage):
                if "text_editor" in getattr(message, 'name', ''):
                    try:
                        tool_result = json.loads(message.content)
                        if tool_result.get("success") and tool_result.get("edited_content"):
                            corrected_content = tool_result["edited_content"]
                            corrections_applied.append({
                                "operation": tool_result.get("operation", "unknown"),
                                "affected_lines": tool_result.get("affected_lines", "unknown"),
                                "message": tool_result.get("message", "")
                            })
                    except json.JSONDecodeError:
                        pass
        
        logger.info(f"应用了 {len(corrections_applied)} 个纠错操作")
        
        return {
            "corrected_content": corrected_content,
            "corrections_applied": corrections_applied,
            "current_step": "completed",
            "is_complete": True
        }
    
    def _should_continue_correction(self, state: FormulaCorrectionState) -> str:
        """判断是否继续纠错"""
        messages = state["messages"]
        
        logger.info(f"🔄 纠错控制流: 检查 {len(messages)} 条消息")
        
        if messages:
            last_message = messages[-1]
            
            # 检查是否是AI消息并且包含工具调用
            if isinstance(last_message, AIMessage):
                tool_calls = getattr(last_message, 'tool_calls', None)
                if tool_calls:
                    logger.info(f"🔧 检测到 {len(tool_calls)} 个工具调用 → call_tools")
                    return "call_tools"
                
                # 检查是否表示纠错完成
                content = last_message.content
                if isinstance(content, str):
                    content_lower = content.lower()
                    completion_keywords = [
                        "纠错完成", "correction complete", "完成纠错",
                        "纠错结束", "correction finished", "修复完成",
                        "公式已修复", "formulas corrected", "所有错误已修复"
                    ]
                    if any(keyword in content_lower for keyword in completion_keywords):
                        logger.info(f"✅ LLM表示纠错完成 → finalize")
                        return "finalize"
            
            # 如果是工具消息，继续处理
            elif isinstance(last_message, ToolMessage):
                logger.info(f"🔧 收到工具结果 → continue")
                return "continue"
        
        # 防止无限循环
        if len(messages) > 20:
            logger.warning(f"⚠️ 消息数量超过限制 ({len(messages)}) → finalize")
            return "finalize"
        
        # 统计工具调用次数，防止无限循环
        tool_call_count = 0
        for msg in messages:
            if isinstance(msg, AIMessage):
                tool_calls = getattr(msg, 'tool_calls', None)
                if tool_calls:
                    tool_call_count += len(tool_calls)
        
        if tool_call_count >= 8:  # 限制最多8次工具调用
            logger.warning(f"⚠️ 工具调用次数超过限制 ({tool_call_count}) → finalize")
            return "finalize"
        
        # 默认继续纠错
        logger.info(f"🔄 继续纠错 → continue")
        return "continue"
    
    def _generate_correction_prompt(self, state: FormulaCorrectionState) -> str:
        """生成纠错提示词"""
        extracted_formulas = state.get("extracted_formulas", [])
        formula_count = len(extracted_formulas)
        
        # 构建公式列表
        formula_list = ""
        if extracted_formulas:
            formula_list = "\n".join([
                f"第{formula['start_line']}行: {formula['formula']}"
                for formula in extracted_formulas[:10]  # 只显示前10个
            ])
            if formula_count > 10:
                formula_list += f"\n... 还有 {formula_count - 10} 个公式"
        
        return f"""
你是一位专业的学术论文公式纠错专家。你的任务是修复分析文档中的公式错误。

**重要说明:**
- OCR参考文档路径: {state['ocr_file_path']}
- 分析文档路径: {state['analysis_file_path']}

**可用工具:**
1. `ocr_document_loader`: 查询OCR原文档中的原始公式内容
   - 参数: ocr_file_path="{state['ocr_file_path']}", query="你的查询内容"
   - 当需要查找原始公式时使用，提供具体的查询关键词
   - 例如: 查询"mathcal"或"formula"或具体的公式符号

2. `text_editor`: 编辑分析文档内容
   - 参数: content=完整的文档内容, operation_type="replace", start_line=行号, new_content="新内容"
   - 使用replace操作修复错误的公式
   - 确保公式格式正确（使用$$...$$包围独行公式）
   - 注意: content参数需要传入完整的文档内容字符串，不是文件路径

3. `math_formula_extractor_tool`: 提取文档中的数学公式
   - 参数: file_path="文件路径" 或 markdown_text="文档内容"

**当前任务:**
- 分析文档: {state['analysis_file_path']}
- OCR参考文档: {state['ocr_file_path']}
- 已提取公式数量: {formula_count}

**提取的公式列表:**
{formula_list}

**工作流程:**
1. 首先检查提取的公式是否有明显错误（如格式问题、符号错误等）
2. 对于可疑的公式，使用ocr_document_loader查询OCR原文档中的对应内容
   - 使用正确的OCR文件路径: {state['ocr_file_path']}
3. 对比原文档和分析文档中的公式，识别错误
4. 如果发现错误，使用text_editor修复（传入完整文档内容）
5. 完成所有修复后，报告"纠错完成"

**注意事项:**
- 只修复明确的公式错误，不要做不必要的修改
- 保持公式的数学含义不变
- 确保修复后的公式格式正确
- text_editor的content参数必须是完整的文档内容字符串，不是文件路径
- 使用正确的OCR文件路径进行查询

现在开始分析和修复公式错误。如果没有发现明显错误，可以直接报告"纠错完成"。
"""
    
    def correct_formulas(self, analysis_file_path: str, ocr_file_path: str, 
                        thread_id: str = "1") -> Dict[str, Any]:
        """
        执行公式纠错的主入口
        
        Args:
            analysis_file_path: 分析文档路径
            ocr_file_path: OCR原文档路径
            thread_id: 线程ID
            
        Returns:
            Dict: 完整的纠错结果
        """
        logger.info(f"开始公式纠错: {analysis_file_path}")
        
        try:
            # 1. 读取文档内容
            analysis_content = self._read_file(analysis_file_path)
            ocr_content = self._read_file(ocr_file_path)
            
            # 2. 创建工具
            logger.info("创建纠错工具...")
            self.formula_extractor = create_math_formula_extractor_tool()
            self.ocr_loader = create_ocr_document_loader_tool()
            self.text_editor = create_text_editor_tool()
            
            tools = [self.formula_extractor, self.ocr_loader, self.text_editor]
            
            # 3. 创建带工具的LLM
            self.llm_with_tools = self.correction_llm.bind_tools(tools)
            
            # 4. 构建并编译图
            logger.info("构建纠错工作流...")
            self._build_graph_with_tools(tools)
            
            # 5. 创建初始状态
            initial_state: FormulaCorrectionState = {
                "analysis_file_path": analysis_file_path,
                "ocr_file_path": ocr_file_path,
                "analysis_content": analysis_content,
                "ocr_content": ocr_content,
                
                "extracted_formulas": None,
                "messages": [],
                "corrected_content": None,
                "corrections_applied": None,
                
                "is_complete": False,
                "current_step": "starting"
            }
            
            # 6. 配置LangGraph
            config = RunnableConfig(
                configurable={"thread_id": thread_id},
                recursion_limit=50
            )
            
            # 7. 执行纠错
            logger.info("开始执行纠错工作流...")
            result = self.agent.invoke(initial_state, config)
            
            logger.info("公式纠错完成")
            return result
            
        except Exception as e:
            logger.error(f"公式纠错失败: {e}")
            import traceback
            logger.error(f"错误堆栈: {traceback.format_exc()}")
            return {
                "error": f"纠错失败: {str(e)}",
                "analysis_file_path": analysis_file_path,
                "ocr_file_path": ocr_file_path
            }
    
    def _read_file(self, file_path: str) -> str:
        """读取文件内容"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"读取文件失败 {file_path}: {e}")
            raise
    
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
    
    def get_config(self) -> FormulaCorrectionConfig:
        """获取当前配置"""
        return self.config


# 便捷函数
def create_formula_correction_agent(
    correction_model: str = "deepseek.DeepSeek_V3",
    **kwargs
) -> FormulaCorrectionAgent:
    """创建公式纠错agent的便捷函数"""
    config = FormulaCorrectionConfig(
        correction_model=correction_model,
        **kwargs
    )
    return FormulaCorrectionAgent(config=config)


# 测试代码
if __name__ == "__main__":
    # 创建纠错agent
    agent = create_formula_correction_agent()
    print(f"公式纠错Agent创建成功")
    print(f"配置: {agent.get_config().__dict__}")
    
    # 测试路径
    analysis_file = "/mnt/nfs_share/code/homesystem/data/paper_analyze/2412.03572/2412.03572_analysis.md"
    ocr_file = "/mnt/nfs_share/code/homesystem/data/paper_analyze/2412.03572/2412.03572_paddleocr.md"
    
    if os.path.exists(analysis_file) and os.path.exists(ocr_file):
        print(f"可以执行测试: {analysis_file}")
    else:
        print("测试文件不存在")