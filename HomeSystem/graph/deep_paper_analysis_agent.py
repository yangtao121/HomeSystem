"""
深度论文分析Agent

基于LangGraph的论文深度分析智能体，使用标准工具调用模式：
1. 云端LLM主导分析，自动决策何时调用图片分析工具
2. 结构化输出生成完整的分析结果
3. 支持双语分析结果输出

采用标准LangGraph工具调用架构，LLM自主决策工具使用。
"""

import json
from typing import Annotated, Any, Dict, List, Optional
from typing_extensions import TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage, BaseMessage
from loguru import logger

from .base_graph import BaseGraph
from .llm_factory import get_llm
from .tool.image_analysis_tool import create_image_analysis_tool
from .parser.paper_folder_parser import create_paper_folder_parser
from .formatter.markdown_formatter import create_markdown_formatter


class DeepPaperAnalysisState(TypedDict):
    """深度论文分析状态"""
    # 输入数据
    base_folder_path: str                           # 论文文件夹路径
    paper_text: str                                 # 论文markdown文本
    available_images: List[str]                     # 可用图片列表
    image_mappings: Dict[str, str]                  # 图片路径映射
    
    # LangGraph消息历史
    messages: Annotated[list, add_messages]         # 对话历史
    
    # 分析结果
    analysis_result: Optional[str]                  # 最终分析结果
    
    # 执行状态
    is_complete: bool                               # 是否完成分析


class DeepPaperAnalysisConfig:
    """深度论文分析配置类"""
    
    def __init__(self,
                 analysis_model: str = "deepseek.DeepSeek_V3",
                 vision_model: str = "ollama.llava", 
                 memory_enabled: bool = True,
                 custom_settings: Optional[Dict[str, Any]] = None):
        
        self.analysis_model = analysis_model          # 主分析LLM
        self.vision_model = vision_model              # 图片理解VLM
        self.memory_enabled = memory_enabled
        self.custom_settings = custom_settings or {}
    
    @classmethod
    def load_from_file(cls, config_path: str) -> "DeepPaperAnalysisConfig":
        """从配置文件加载配置"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            return cls(**config_data)
        except Exception as e:
            logger.warning(f"配置文件加载失败，使用默认配置: {e}")
            return cls()


class DeepPaperAnalysisAgent(BaseGraph):
    """深度论文分析智能体
    
    功能：
    1. 使用标准LangGraph工具调用模式
    2. 云端LLM自主决策工具使用
    3. 结构化输出和双语支持
    """
    
    def __init__(self,
                 config: Optional[DeepPaperAnalysisConfig] = None,
                 config_path: Optional[str] = None,
                 **kwargs):
        
        super().__init__(**kwargs)
        
        # 加载配置
        if config_path:
            self.config = DeepPaperAnalysisConfig.load_from_file(config_path)
        elif config:
            self.config = config
        else:
            self.config = DeepPaperAnalysisConfig()
        
        logger.info(f"初始化深度论文分析智能体")
        logger.info(f"分析模型: {self.config.analysis_model}")
        logger.info(f"视觉模型: {self.config.vision_model}")
        
        # 创建主分析LLM
        self.analysis_llm = get_llm(self.config.analysis_model)
        
        # 移除了结构化输出功能，简化为直接文本输出
        
        # 设置内存管理
        self.memory = MemorySaver() if self.config.memory_enabled else None
        
        # 图片分析工具将在运行时创建
        self.image_tool = None
        self.llm_with_tools = None
        self.tool_node = None
        
        # 构建图（将在分析时动态完成）
        self._graph_template = None
        self.agent = None
        
        logger.info("深度论文分析智能体初始化完成")
    
    def _build_graph_with_tools(self, image_tool) -> None:
        """使用工具构建简化的LangGraph工作流"""
        graph = StateGraph(DeepPaperAnalysisState)
        
        # 添加节点
        graph.add_node("initialize", self._initialize_node)
        graph.add_node("analysis_with_tools", self._analysis_with_tools_node)
        # 添加 tool_node
        self.tool_node = ToolNode([image_tool])
        graph.add_node("call_tools", self.tool_node)
        
        # 构建简化流程
        graph.add_edge(START, "initialize")
        graph.add_edge("initialize", "analysis_with_tools")
        
        # 分析工具调用的条件分支
        graph.add_conditional_edges(
            "analysis_with_tools",
            self._should_continue_analysis,
            {
                "call_tools": "call_tools",  # 调用工具
                "continue": "analysis_with_tools",  # 继续分析
                "end": END,  # 分析完成，直接结束
            }
        )
        
        # 工具调用后回到分析节点
        graph.add_edge("call_tools", "analysis_with_tools")
        
        # 编译图
        try:
            self.agent = graph.compile(checkpointer=self.memory)
            logger.info("✅ LangGraph 图编译成功")
        except Exception as e:
            logger.error(f"❌ LangGraph 图编译失败: {e}")
            raise
    
    def _initialize_node(self, state: DeepPaperAnalysisState) -> Dict[str, Any]:
        """初始化节点"""
        logger.info("✅ 工具已在分析开始前初始化")
        
        # 创建初始分析提示
        initial_prompt = self._generate_initial_analysis_prompt(state)
        
        return {
            "messages": [SystemMessage(content=initial_prompt)],
            "is_complete": False
        }
    
    def _analysis_with_tools_node(self, state: DeepPaperAnalysisState) -> Dict[str, Any]:
        """带工具调用的分析节点 - 使用标准 LangGraph 模式"""
        logger.info("开始LLM分析...")
        
        messages = state["messages"]
        
        try:
            # 确保llm_with_tools已初始化
            if self.llm_with_tools is None:
                logger.error("❌ LLM with tools not initialized")
                return {"messages": [AIMessage(content="LLM工具未初始化")]}
            
            # 显示输入消息的详细信息
            logger.info(f"📤 发送消息给 LLM:")
            logger.info(f"  - 消息数量: {len(messages)}")
            for i, msg in enumerate(messages[-3:]):  # 只显示最后3条消息
                msg_type = type(msg).__name__
                msg_preview = str(msg.content)[:100] if hasattr(msg, 'content') else str(msg)[:100]
                logger.info(f"  - 消息 {i}: {msg_type} - {msg_preview}...")
            
            # LLM自主决策并可能调用工具
            response = self.llm_with_tools.invoke(messages)
            
            # 详细检查响应
            logger.info(f"💬 LLM 响应:")
            logger.info(f"  - 响应类型: {type(response).__name__}")
            if hasattr(response, 'content'):
                content_preview = str(response.content)[:200] if response.content else "<empty>"
                logger.info(f"  - 内容预览: {content_preview}...")
            
            # 检查是否有工具调用
            tool_calls = getattr(response, 'tool_calls', None)
            if tool_calls:
                logger.info(f"🔧 LLM决定调用 {len(tool_calls)} 个工具:")
                for i, tool_call in enumerate(tool_calls):
                    try:
                        if hasattr(tool_call, 'get'):
                            tool_name = tool_call.get('name', 'unknown')
                            tool_args = tool_call.get('args', {})
                        else:
                            # 处理不同的 tool_call 对象类型
                            tool_name = getattr(tool_call, 'name', str(tool_call))
                            tool_args = getattr(tool_call, 'args', {})
                        
                        logger.info(f"  [{i+1}] 工具: {tool_name}")
                        if isinstance(tool_args, dict):
                            for key, value in tool_args.items():
                                value_preview = str(value)[:100] if len(str(value)) > 100 else str(value)
                                logger.info(f"      {key}: {value_preview}")
                        else:
                            logger.info(f"      参数: {tool_args}")
                    except Exception as e:
                        logger.warning(f"      无法解析工具调用 {i+1}: {e}")
            else:
                logger.info("🚫 LLM未调用任何工具")
                
                # 检查是否是完整的分析结果
                if hasattr(response, 'content') and response.content:
                    content = str(response.content)
                    # 如果内容较长且不是工具调用，可能是最终分析结果
                    if len(content) > 1000:
                        logger.info(f"✅ 检测到完整分析结果 ({len(content)} 字符)")
                        return {
                            "messages": [response],
                            "analysis_result": content,
                            "is_complete": True
                        }
            
            return {"messages": [response]}
            
        except Exception as e:
            logger.error(f"❌ 分析节点执行失败: {e}")
            import traceback
            logger.error(f"错误堆栈: {traceback.format_exc()}")
            error_message = AIMessage(content=f"分析过程中出现错误: {str(e)}")
            return {"messages": [error_message]}
    
    def _should_continue_analysis(self, state: DeepPaperAnalysisState) -> str:
        """判断是否继续分析或调用工具"""
        messages = state["messages"]
        
        logger.info(f"🔄 分析控制流: 检查 {len(messages)} 条消息")
        
        # 检查最后的消息
        if messages:
            last_message = messages[-1]
            last_msg_type = type(last_message).__name__
            logger.info(f"  - 最后消息类型: {last_msg_type}")
            
            # 检查是否是 AI 消息并且包含工具调用
            if isinstance(last_message, AIMessage):
                # 使用 getattr 安全检查 tool_calls 属性
                tool_calls = getattr(last_message, 'tool_calls', None)
                if tool_calls:
                    logger.info(f"🔧 检测到 {len(tool_calls)} 个工具调用 → call_tools")
                    return "call_tools"
                
                # 检查是否LLM表示分析完成
                content = last_message.content
                if isinstance(content, str):
                    content_lower = content.lower()
                    completion_keywords = [
                        "分析完成", "analysis complete", "完成分析",
                        "分析结束", "analysis finished", "结束分析",
                        "analysis is complete", "finished analyzing"
                    ]
                    if any(keyword in content_lower for keyword in completion_keywords):
                        logger.info(f"✅ LLM表示分析完成 → end")
                        return "end"
                    
                    # 检查内容长度，如果较长可能是完整分析
                    if len(content) > 2000:  # 内容较长，可能已经完成了分析
                        logger.info(f"📝 内容较长 ({len(content)} 字符)，可能已完成分析 → end")
                        return "end"
            
            # 如果是工具消息，让LLM继续处理工具结果
            elif isinstance(last_message, ToolMessage):
                logger.info(f"🔧 收到工具结果 → continue")
                return "continue"
        
        # 防止无限循环：检查消息数量
        if len(messages) > 15:  # 增加上限，给更多机会进行工具调用
            logger.warning(f"⚠️ 消息数量超过限制 ({len(messages)}) → end")
            return "end"
        
        # 统计工具调用次数
        tool_call_count = 0
        tool_message_count = 0
        for msg in messages:
            if isinstance(msg, AIMessage):
                tool_calls = getattr(msg, 'tool_calls', None)
                if tool_calls:
                    tool_call_count += len(tool_calls)
            elif isinstance(msg, ToolMessage):
                tool_message_count += 1
        
        logger.info(f"  - 工具调用次数: {tool_call_count}, 工具响应: {tool_message_count}")
        
        # 如果已经进行了足够的工具调用，考虑结束
        if tool_call_count >= 3:  # 已经进行了多次工具调用
            logger.info(f"🔄 已进行 {tool_call_count} 次工具调用，考虑结束分析 → end")
            return "end"
        
        # 默认继续分析
        logger.info(f"🔄 继续分析 → continue")
        return "continue"
    
    
    def _generate_initial_analysis_prompt(self, state: DeepPaperAnalysisState) -> str:
        """生成初始分析提示词 - 要求标准Markdown输出格式"""
        available_images = state.get('available_images', [])
        image_list = "\n".join([f"  - {img}" for img in available_images[:10]])  # 显示前10个图片
        if len(available_images) > 10:
            image_list += f"\n  ... and {len(available_images) - 10} more images"
        
        return f"""
你是一位专业的学术论文分析专家。你有一个图片分析工具，可以帮助你理解论文中的图表、架构图和实验结果。

**重要: 所有分析结果必须以标准Markdown格式输出，包含完整的结构、公式、图片引用，并尽可能提取作者信息、单位和项目地址。论文标题请直接使用原文标题，不要翻译。所有专业名词请直接保留原文，不要翻译。**

**可用工具:**
- `analyze_image`: 用于分析论文中的任何图片/图表/表格/示意图
  - 当你需要理解文本中引用的视觉内容时调用此工具
  - 始终分析关键图表、架构图、实验图表和重要表格
  - 提供具体的分析查询，如"分析这个架构图并识别主要组件"或"从这个实验图表中提取性能指标"

**论文内容:**
{state['paper_text']}...

**Markdown输出格式要求:**

1. **文档结构**: 使用标准Markdown标题层级（#, ##, ###等）
2. **作者信息**: 提取并展示作者姓名、单位（尤其是一作单位），如有项目地址或源码也要在显著位置标注（如GitHub、项目主页等）
3. **数学公式**: 
   - 行间公式使用 `$$...$$` 
   - 行内公式使用 `$...$`
   - 保留论文中的所有重要数学表达式
4. **图片引用**: 
   - 使用 `![图片描述](图片路径)` 语法
   - 在分析重要图表后，在适当位置插入图片引用
   - 图片描述应该准确反映图片内容和重要性
5. **表格**: 使用Markdown表格语法展示数据
6. **列表**: 使用`-`或数字列表组织信息
7. **代码**: 如有算法或代码，使用```代码块

**Markdown输出模板结构:**
```markdown
# 论文原文标题（请直接展示原始标题，不要翻译）

## 0. 作者与项目信息
- 作者: xxx 等
- 单位: xxx大学/研究所（请标注一作单位）
- 项目地址: [GitHub/主页/源码链接](url)（如有请标注）

## 1. 研究背景与目标

## 2. 主要贡献

## 3. 技术方法
### 3.1 核心算法
（保留重要数学公式，如：$$f(x) = \sum_{{i=1}}^n w_i x_i$$）

### 3.2 架构设计
（插入重要架构图：![系统架构图](imgs/architecture.jpg)）

## 4. 实验结果
### 4.1 数据集与设置
### 4.2 性能分析
（插入实验结果图表）

## 5. 关键发现

## 6. 总结与评价
```

**执行指南:**
1. 仔细阅读论文内容，识别关键信息
2. 优先提取作者、单位、项目地址等元信息
3. 论文标题请直接使用原文标题，不要翻译
4. 所有专业名词请直接保留原文，不要翻译
5. 对重要图表使用analyze_image工具进行深入分析
6. 将分析结果组织成标准Markdown格式
7. 确保保留原文中的重要公式和数据
8. 在适当位置引用分析过的图片

现在开始你的分析，记住输出必须是完整的、结构化的Markdown文档，包含所有重要的视觉元素、数学表达式和元信息。

**注意**: 请用中文进行所有分析和说明，但遵循标准Markdown语法格式。
"""
    
    
    def analyze_paper_folder(self, folder_path: str, thread_id: str = "1") -> Dict[str, Any]:
        """
        分析论文文件夹的主入口
        
        Args:
            folder_path: 论文文件夹路径
            thread_id: 线程ID
            
        Returns:
            Dict: 完整的分析结果状态
        """
        logger.info(f"开始分析论文文件夹: {folder_path}")
        
        try:
            # 1. 解析文件夹内容
            folder_data = self._parse_paper_folder(folder_path)
            
            # 2. 创建图片分析工具
            logger.info("创建图片分析工具...")
            self.image_tool = create_image_analysis_tool(folder_path, self.config.vision_model)
            
            # 3. 创建带工具的LLM
            self.llm_with_tools = self.analysis_llm.bind_tools([self.image_tool])
            
            # 4. 构建并编译完整的图
            logger.info("构建 LangGraph 工作流...")
            self._build_graph_with_tools(self.image_tool)
            
            logger.info(f"✅ 初始化完成:")
            logger.info(f"  - 图片分析工具: {self.image_tool.name}")
            logger.info(f"  - 可分析图片数量: {len(folder_data['available_images'])}")
            logger.info(f"  - 视觉模型: {self.config.vision_model}")
            
            # 5. 创建初始状态
            initial_state: DeepPaperAnalysisState = {
                "base_folder_path": folder_path,
                "paper_text": folder_data["paper_text"],
                "available_images": folder_data["available_images"],
                "image_mappings": folder_data["image_mappings"],
                
                "messages": [],
                "analysis_result": None,
                "is_complete": False
            }
            
            # 6. 配置LangGraph
            config = RunnableConfig(
                configurable={"thread_id": thread_id},
                recursion_limit=100
            )
            
            # 7. 执行分析
            logger.info("开始执行LangGraph工作流...")
            result = self.agent.invoke(initial_state, config)
            
            logger.info("论文分析完成")
            return result
            
        except Exception as e:
            logger.error(f"论文分析失败: {e}")
            import traceback
            logger.error(f"错误堆栈: {traceback.format_exc()}")
            return {
                "error": f"分析失败: {str(e)}",
                "folder_path": folder_path
            }
    
    def _parse_paper_folder(self, folder_path: str) -> Dict[str, Any]:
        """解析论文文件夹结构"""
        # 使用专门的解析器
        parser = create_paper_folder_parser(folder_path)
        
        # 验证文件夹完整性
        validation = parser.validate_folder_integrity()
        if not validation["is_valid"]:
            logger.warning(f"文件夹验证失败: {validation['issues']}")
        
        # 解析文件夹
        parse_result = parser.parse_folder()
        
        # 提取需要的信息
        return {
            "paper_text": parse_result["paper_text"],
            "available_images": parse_result["available_images"],
            "image_mappings": parse_result["image_mappings"],
            "latex_formulas": parse_result["latex_formulas"],
            "image_references": parse_result["image_references"],
            "content_sections": parse_result["content_sections"]
        }
    
    def get_config(self) -> DeepPaperAnalysisConfig:
        """获取当前配置"""
        return self.config
    
    def generate_markdown_report(self, analysis_result: Dict[str, Any], output_path: Optional[str] = None) -> str:
        """
        生成markdown分析报告
        
        Args:
            analysis_result: 分析结果状态
            output_path: 输出文件路径（可选）
            
        Returns:
            str: markdown报告内容
        """
        logger.info("生成markdown分析报告...")
        
        # 创建格式化器（使用中文）
        formatter = create_markdown_formatter("zh")
        
        # 生成报告
        report_content = formatter.format_analysis_report(analysis_result)
        
        # 保存文件（如果指定了路径）
        if output_path:
            success = formatter.save_report(report_content, output_path)
            if success:
                logger.info(f"报告已保存到: {output_path}")
            else:
                logger.error("报告保存失败")
        
        return report_content
    
    def analyze_and_generate_report(self, folder_path: str, output_path: Optional[str] = None, thread_id: str = "1") -> tuple[Dict[str, Any], str]:
        """
        完整的分析和报告生成流程
        
        Args:
            folder_path: 论文文件夹路径
            output_path: 报告输出路径（可选）
            thread_id: 线程ID
            
        Returns:
            tuple: (分析结果, markdown报告内容)
        """
        logger.info(f"开始完整的论文分析和报告生成流程: {folder_path}")
        
        # 执行分析
        analysis_result = self.analyze_paper_folder(folder_path, thread_id)
        
        # 生成报告
        report_content = self.generate_markdown_report(analysis_result, output_path)
        
        logger.info("完整流程执行完成")
        return analysis_result, report_content


# 便捷函数
def create_deep_paper_analysis_agent(
    analysis_model: str = "deepseek.DeepSeek_V3",
    vision_model: str = "ollama.llava",
    **kwargs
) -> DeepPaperAnalysisAgent:
    """创建深度论文分析agent的便捷函数"""
    config = DeepPaperAnalysisConfig(
        analysis_model=analysis_model,
        vision_model=vision_model,
        **kwargs
    )
    return DeepPaperAnalysisAgent(config=config)


# 测试代码
if __name__ == "__main__":
    # 测试agent创建
    agent = create_deep_paper_analysis_agent()
    print(f"深度论文分析Agent创建成功")
    print(f"配置: {agent.get_config().__dict__}")