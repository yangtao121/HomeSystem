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
    
    # 简化的分析结果
    chinese_analysis: Optional[str]                 # 中文分析结果
    
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
        graph.add_node("chinese_analysis", self._chinese_analysis_node)
        
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
                "chinese_analysis": "chinese_analysis",  # 进入中文分析
            }
        )
        
        # 工具调用后回到分析节点
        graph.add_edge("call_tools", "analysis_with_tools")
        
        # 中文分析结束
        graph.add_edge("chinese_analysis", END)
        
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
                        logger.info(f"✅ LLM表示分析完成 → chinese_analysis")
                        return "chinese_analysis"
                    
                    # 检查内容长度，如果较长可能是完整分析
                    if len(content) > 2000:  # 内容较长，可能已经完成了分析
                        logger.info(f"📝 内容较长 ({len(content)} 字符)，可能已完成分析 → chinese_analysis")
                        return "chinese_analysis"
            
            # 如果是工具消息，让LLM继续处理工具结果
            elif isinstance(last_message, ToolMessage):
                logger.info(f"🔧 收到工具结果 → continue")
                return "continue"
        
        # 防止无限循环：检查消息数量
        if len(messages) > 15:  # 增加上限，给更多机会进行工具调用
            logger.warning(f"⚠️ 消息数量超过限制 ({len(messages)}) → chinese_analysis")
            return "chinese_analysis"
        
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
            logger.info(f"🔄 已进行 {tool_call_count} 次工具调用，考虑结束分析 → chinese_analysis")
            return "chinese_analysis"
        
        # 默认继续分析
        logger.info(f"🔄 继续分析 → continue")
        return "continue"
    
    def _chinese_analysis_node(self, state: DeepPaperAnalysisState) -> Dict[str, Any]:
        """中文分析节点 - 直接输出中文分析结果"""
        logger.info("开始生成中文分析结果...")
        
        try:
            # 准备中文分析的提示词
            chinese_prompt = self._generate_chinese_analysis_prompt(state)
            
            # 使用主分析LLM直接生成中文结果
            response = self.analysis_llm.invoke(chinese_prompt)
            chinese_content = response.content if hasattr(response, 'content') else str(response)
            
            logger.info("中文分析结果生成完成")
            
            return {
                "chinese_analysis": chinese_content,
                "is_complete": True
            }
            
        except Exception as e:
            logger.error(f"中文分析失败: {e}")
            return {"messages": [AIMessage(content=f"中文分析失败: {str(e)}")]}
    
    # 移除了翻译相关的方法
    
    # 移除了翻译节点，直接输出中文
    
    def _generate_initial_analysis_prompt(self, state: DeepPaperAnalysisState) -> str:
        """生成初始分析提示词"""
        available_images = state.get('available_images', [])
        image_list = "\n".join([f"  - {img}" for img in available_images[:10]])  # 显示前10个图片
        if len(available_images) > 10:
            image_list += f"\n  ... and {len(available_images) - 10} more images"
        
        return f"""
你是一位专业的学术论文分析专家。你有一个图片分析工具，可以帮助你理解论文中的图表、架构图和实验结果。

**可用工具:**
- `analyze_image`: 用于分析论文中的任何图片/图表/图表/示意图
  - 当你需要理解文本中引用的视觉内容时调用此工具
  - 始终分析关键图表、架构图、实验图表和重要表格
  - 提供具体的分析查询，如"分析这个架构图并识别主要组件"或"从这个实验图表中提取性能指标"

**本论文中可用的图片:**
{image_list}

**论文内容:**
{state['paper_text'][:15000]}...

**你的任务:**
对这篇学术论文进行全面分析。**重要**: 当你遇到对图表、图表、架构图或实验结果的引用时，使用图片分析工具来获得更深入的见解。

**分析指导原则:**
1. **研究目标和贡献**: 识别主要研究目标和关键贡献
2. **技术方法与创新**: 分析技术方法和新颖方面
3. **实验设计与结果**: 检查实验设置和性能结果
4. **视觉内容分析**: 对于任何提到的图表/图表/示意图，使用图片分析工具

**何时使用图片分析工具:**
- 当文本提到"图X"、"表Y"、"架构"、"示意图"等时
- 当分析可能有视觉表示的实验结果时
- 当理解系统架构或模型设计时
- 当从图表或性能比较中提取特定数据时

**如何使用工具:**
调用 `analyze_image` 时需要:
- `analysis_query`: 对你要分析内容的清晰中文描述（如"分析这个系统架构并识别主要组件"）
- `image_path`: 来自可用图片列表的相对路径（如"imgs/img_in_image_box_253_178_967_593.jpg"）

现在开始你的分析。记住，每当视觉内容可以提供额外见解时，就使用图片分析工具。

**注意**: 请用中文进行所有分析和说明。
"""
    
    def _generate_chinese_analysis_prompt(self, state: DeepPaperAnalysisState) -> str:
        """生成中文分析提示词"""
        
        # 收集所有分析信息
        paper_text = state["paper_text"]
        messages = state["messages"]
        
        # 提取图片分析结果
        image_analysis_results = []
        tool_call_count = 0
        for msg in messages:
            if isinstance(msg, ToolMessage):
                image_analysis_results.append(msg.content)
            elif isinstance(msg, AIMessage):
                tool_calls = getattr(msg, 'tool_calls', None)
                if tool_calls:
                    tool_call_count += len(tool_calls)
        
        image_insights = "\n\n".join(image_analysis_results) if image_analysis_results else "未进行图片分析"
        
        logger.info(f"中文分析: 发现 {tool_call_count} 次工具调用, {len(image_analysis_results)} 个图片分析结果")
        
        return f"""
请基于之前的分析和图片理解，用中文生成这篇论文的全面分析报告。

**论文内容:**
{paper_text[:15000]}

**图片分析结果:**
{image_insights}

**要求:**
请用中文提供详细的分析，包括以下内容：

# 论文深度分析报告

## 1. 研究目标与动机
- 论文要解决的主要问题
- 研究动机和重要性
- 与现有研究的关系

## 2. 主要贡献与创新点
- 列出3-6个关键贡献
- 每个贡献的具体描述和创新性
- 与现有方法的区别和优势

## 3. 技术方法分析
- 主要技术方法和算法
- 关键技术细节和创新点
- 方法的优势和限制

## 4. 实验设计与结果
- 实验设置和数据集
- 主要性能指标和结果
- 与基准方法的比较

## 5. 图表分析与见解
{'基于图片分析结果的深入解读' if image_analysis_results else '未提供图表分析'}

## 6. 关键发现与启示
- 3-5个最重要的发现
- 对领域的影响和意义
- 未来研究方向

## 7. 整体评价与总结
- 论文的技术质量和深度
- 实用价值和应用前景
- 不足之处和改进建议

请用专业、准确的中文进行分析，确保内容全面且深入。
"""
    
    # 移除了翻译提示词生成方法
    
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
                "chinese_analysis": None,
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