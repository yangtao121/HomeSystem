"""
深度论文分析Agent

基于LangGraph的论文深度分析智能体，使用标准工具调用模式：
1. 云端LLM主导分析，自动决策何时调用图片分析工具
2. 结构化输出生成完整的分析结果
3. 支持双语分析结果输出

采用标准LangGraph工具调用架构，LLM自主决策工具使用。
"""

import json
import os
import re
import weakref
from concurrent.futures import ThreadPoolExecutor
from typing import Annotated, Any, Dict, List, Optional, Union
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
from .tool.video_resource_processor import VideoResourceProcessor
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
    
    # 用户提示词
    user_prompt: Optional[str]                      # 用户自定义提示词


class DeepPaperAnalysisConfig:
    """深度论文分析配置类"""
    
    def __init__(self,
                 analysis_model: str = "deepseek.DeepSeek_V3",
                 vision_model: str = "ollama.Qwen2_5_VL_7B", 
                 memory_enabled: bool = True,
                 # 新增视频分析相关配置
                 enable_video_analysis: bool = False,  # 默认关闭
                 video_analysis_model: str = "ollama.Qwen3_30B",  # 视频分析模型
                 # 新增用户提示词配置
                 enable_user_prompt: bool = False,  # 默认关闭
                 user_prompt: Optional[str] = None,  # 用户自定义提示词
                 user_prompt_position: str = "before_analysis",  # 提示词位置: before_analysis, after_tools, custom
                 custom_settings: Optional[Dict[str, Any]] = None):
        
        self.analysis_model = analysis_model          # 主分析LLM
        self.vision_model = vision_model              # 图片理解VLM
        self.memory_enabled = memory_enabled
        # 视频分析配置
        self.enable_video_analysis = enable_video_analysis
        self.video_analysis_model = video_analysis_model
        # 用户提示词配置
        self.enable_user_prompt = enable_user_prompt
        self.user_prompt = user_prompt
        self.user_prompt_position = user_prompt_position
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
        logger.info(f"视频分析功能: {'启用' if self.config.enable_video_analysis else '禁用'}")
        if self.config.enable_video_analysis:
            logger.info(f"视频分析模型: {self.config.video_analysis_model}")
        
        # 创建主分析LLM
        self.analysis_llm = get_llm(self.config.analysis_model)
        
        # 移除了结构化输出功能，简化为直接文本输出
        
        # 设置内存管理 - 使用独立的线程池配置
        self._custom_executor = None
        if self.config.memory_enabled:
            try:
                # 创建专用的线程池执行器，避免与系统默认执行器冲突
                self._custom_executor = ThreadPoolExecutor(
                    max_workers=2, 
                    thread_name_prefix="deep_analysis_checkpointer"
                )
                self.memory = MemorySaver()
                # 注册清理函数，确保资源释放
                weakref.finalize(self, self._cleanup_executor, self._custom_executor)
                logger.info("✅ 内存管理器初始化完成，使用独立线程池")
            except Exception as e:
                logger.warning(f"⚠️ 内存管理器初始化失败，将禁用内存功能: {e}")
                self.memory = None
                self._custom_executor = None
        else:
            self.memory = None
        
        # 分析工具将在运行时创建
        self.image_tool = None
        self.video_tool = None  # 视频分析工具
        self.llm_with_tools = None
        self.tool_node = None
        
        # 构建图（将在分析时动态完成）
        self._graph_template = None
        self.agent = None
        
        # 资源清理状态
        self._is_cleaned_up = False
        
        logger.info("深度论文分析智能体初始化完成")
    
    def _build_graph_with_tools(self, tools: List[Any]) -> None:
        """使用工具构建简化的LangGraph工作流"""
        graph = StateGraph(DeepPaperAnalysisState)
        
        # 添加节点
        graph.add_node("initialize", self._initialize_node)
        graph.add_node("analysis_with_tools", self._analysis_with_tools_node)
        # 添加 tool_node - 使用动态工具列表
        self.tool_node = ToolNode(tools)
        graph.add_node("call_tools", self.tool_node)
        # 添加图片路径修正节点
        graph.add_node("correct_image_paths", self._correct_image_paths_node)
        
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
                "end": "correct_image_paths",  # 分析完成，进行路径修正
            }
        )
        
        # 工具调用后回到分析节点
        graph.add_edge("call_tools", "analysis_with_tools")
        
        # 图片路径修正后结束
        graph.add_edge("correct_image_paths", END)
        
        # 编译图 - 添加错误恢复机制
        try:
            # 如果内存管理器不可用，使用无状态模式
            checkpointer = self.memory if self.memory else None
            if checkpointer is None:
                logger.warning("⚠️ 内存管理器不可用，将使用无状态模式")
            
            self.agent = graph.compile(checkpointer=checkpointer)
            logger.info("✅ LangGraph 图编译成功")
        except Exception as e:
            logger.error(f"❌ LangGraph 图编译失败: {e}")
            # 尝试无状态编译作为降级处理
            try:
                logger.info("尝试无状态编译作为降级处理...")
                self.agent = graph.compile(checkpointer=None)
                logger.warning("⚠️ 使用无状态模式编译成功")
            except Exception as fallback_error:
                logger.error(f"❌ 降级编译也失败: {fallback_error}")
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
    
    def _correct_image_paths_node(self, state: DeepPaperAnalysisState) -> Dict[str, Any]:
        """修正markdown中的图片路径为标准格式 imgs/xxx.jpg"""
        logger.info("📝 开始修正图片路径...")
        
        analysis_result = state.get("analysis_result")
        if not analysis_result:
            logger.warning("⚠️ 没有分析结果需要修正")
            return {}
        
        # 图片路径修正的正则表达式
        # 匹配 ![描述](路径) 格式
        image_pattern = r'!\[([^\]]*)\]\(([^)]+)\)'
        
        def correct_path(match):
            description = match.group(1)
            path = match.group(2)
            
            logger.info(f"🔍 发现图片路径: {path}")
            
            # 检查是否是视频文件，保持videos/路径不变
            if '/videos/' in path or path.startswith('videos/'):
                logger.info(f"📹 保持视频路径不变: {path}")
                return f'![{description}]({path})'
            
            # 提取文件名
            filename = os.path.basename(path)
            
            # 检查是否是图片文件
            image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg'}
            file_ext = os.path.splitext(filename)[1].lower()
            
            if file_ext in image_extensions:
                # 标准化为 imgs/filename 格式
                corrected_path = f"imgs/{filename}"
                logger.info(f"✅ 修正路径: {path} → {corrected_path}")
                return f'![{description}]({corrected_path})'
            else:
                # 非图片文件保持不变
                logger.info(f"ℹ️ 非图片文件保持不变: {path}")
                return f'![{description}]({path})'
        
        # 执行路径修正
        original_text = analysis_result
        corrected_text = re.sub(image_pattern, correct_path, original_text)
        
        # 统计修正数量
        original_matches = re.findall(image_pattern, original_text)
        corrected_matches = re.findall(image_pattern, corrected_text)
        
        corrections_made = 0
        for (orig_desc, orig_path), (corr_desc, corr_path) in zip(original_matches, corrected_matches):
            if orig_path != corr_path:
                corrections_made += 1
        
        logger.info(f"📊 图片路径修正完成:")
        logger.info(f"  - 发现图片引用: {len(original_matches)} 个")
        logger.info(f"  - 执行修正: {corrections_made} 个")
        
        return {
            "analysis_result": corrected_text
        }
    
    
    def _generate_initial_analysis_prompt(self, state: DeepPaperAnalysisState) -> str:
        """生成初始分析提示词 - 要求标准Markdown输出格式"""
        available_images = state.get('available_images', [])
        image_list = "\n".join([f"  - {img}" for img in available_images[:10]])  # 显示前10个图片
        if len(available_images) > 10:
            image_list += f"\n  ... and {len(available_images) - 10} more images"
        
        # 动态生成工具描述
        tools_description = "- `analyze_image`: 用于分析论文中的任何图片/示意图\n"
        tools_description += "  - 当你需要理解文本中引用的视觉内容时调用此工具\n"
        tools_description += "  - 始终分析关键架构图、实验图表和重要表格\n"
        tools_description += "  - 提供具体的分析查询，如\"分析这个架构图并识别主要组件\"或\"从这个实验图表中提取性能指标\"\n"
        
        if self.video_tool:
            tools_description += "- `process_video_resources`: 用于分析论文相关的演示视频或项目视频\n"
            tools_description += "  - 当论文包含项目地址、GitHub链接或开源代码时使用\n"
            tools_description += "  - 自动下载视频并进行内容分析，生成中文总结\n"
            tools_description += "  - 视频将保存到videos/文件夹，在Markdown中引用\n"
        
        # 检查是否有用户提示词
        user_prompt_section = ""
        user_prompt = state.get('user_prompt')
        if self.config.enable_user_prompt and user_prompt:
            user_prompt_section = f"""

**用户特别关注的方面:**
{user_prompt}

请在分析时特别关注以上用户提到的方面，并在相应章节中进行深入分析。
"""
        
        return f"""
你是一位专业的学术论文分析专家。你有图片分析工具{('和视频分析工具' if self.video_tool else '')}，可以帮助你理解论文中的图表、架构图、实验结果{('以及相关的演示视频' if self.video_tool else '')}。

**重要: 所有分析结果必须以标准Markdown格式输出，包含完整的结构、公式、图片引用，并尽可能提取作者信息、单位和项目地址。论文标题请直接使用原文标题，不要翻译。所有专业名词请直接保留原文，不要翻译。**
{user_prompt_section}
**可用工具:**
{tools_description}

{('**视频使用说明:**' if self.video_tool else '')}
{('- 有项目链接必须调用视频分析工具进行分析，并根据视频内容选择合适的位置插入视频，不要固定在项目信息部分' if self.video_tool else '')}
{('- 视频格式：<video controls width="100%"><source src="videos/视频文件名.mp4" type="video/mp4"></video>' if self.video_tool else '')}

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
（保留重要数学公式，如：$$f(x) = \\sum_{{i=1}}^n w_i x_i$$）

```

**总结的内容不限于以上内容，请根据论文内容灵活调整。**

**执行指南:**
1. 仔细阅读论文内容，识别关键信息
2. 优先提取作者、单位、项目地址等元信息
3. 论文标题请直接使用原文标题，不要翻译
4. 所有专业名词请直接保留原文，不要翻译
5. 对重要图表使用analyze_image工具进行深入分析
{('6. 如果论文包含项目地址或开源代码，必须考虑使用process_video_resources工具搜索相关演示视频' if self.video_tool else '')}
{('7. 将分析结果组织成标准Markdown格式' if self.video_tool else '6. 将分析结果组织成标准Markdown格式')}
{('8. 确保保留原文中的重要公式和数据' if self.video_tool else '7. 确保保留原文中的重要公式和数据')}
{('9. 在适当位置引用分析过的图片和视频' if self.video_tool else '8. 在适当位置引用分析过的图片')}

现在开始你的分析，记住输出必须是完整的、结构化的Markdown文档，包含所有重要的视觉元素、数学表达式和元信息。

**注意**: 请用中文进行所有分析和说明，但遵循标准Markdown语法格式。
"""
    
    
    def analyze_paper_folder(self, folder_path: str, thread_id: str = "1", 
                             user_prompt: Optional[str] = None) -> Dict[str, Any]:
        """
        分析论文文件夹的主入口
        
        Args:
            folder_path: 论文文件夹路径
            thread_id: 线程ID
            user_prompt: 用户自定义提示词（可选，会覆盖配置中的默认值）
            
        Returns:
            Dict: 完整的分析结果状态
        """
        logger.info(f"开始分析论文文件夹: {folder_path}")
        
        try:
            # 0. 重置 agent 实例以确保全新分析
            reset_success = self.reset_agent_for_fresh_analysis()
            if not reset_success:
                logger.warning("⚠️ Agent 重置失败，但继续分析...")
            
            # 1. 解析文件夹内容
            folder_data = self._parse_paper_folder(folder_path)
            
            # 2. 创建图片分析工具
            logger.info("创建图片分析工具...")
            self.image_tool = create_image_analysis_tool(folder_path, self.config.vision_model)
            
            # 3. 智能初始化视频分析工具（如果启用且检测到项目信息）
            logger.info("检查是否需要视频分析工具...")
            self._initialize_video_tool_if_needed(folder_path, folder_data["paper_text"])
            
            # 4. 动态创建带工具的LLM
            tools = [self.image_tool]
            if self.video_tool:
                tools.append(self.video_tool)
                logger.info(f"  - 视频分析工具: {self.video_tool.name}")
            
            self.llm_with_tools = self.analysis_llm.bind_tools(tools)
            
            # 5. 构建并编译完整的图
            logger.info("构建 LangGraph 工作流...")
            self._build_graph_with_tools(tools)
            
            logger.info(f"✅ 初始化完成:")
            logger.info(f"  - 图片分析工具: {self.image_tool.name}")
            logger.info(f"  - 可分析图片数量: {len(folder_data['available_images'])}")
            logger.info(f"  - 视觉模型: {self.config.vision_model}")
            
            # 6. 确定要使用的用户提示词
            # 优先使用运行时传入的提示词，其次使用配置中的提示词
            effective_user_prompt = None
            if user_prompt:
                effective_user_prompt = user_prompt
                logger.info("使用运行时传入的用户提示词")
            elif self.config.enable_user_prompt and self.config.user_prompt:
                effective_user_prompt = self.config.user_prompt
                logger.info("使用配置文件中的用户提示词")
            
            if effective_user_prompt:
                logger.info(f"用户提示词预览: {effective_user_prompt[:100]}...")
            
            # 7. 创建初始状态
            initial_state: DeepPaperAnalysisState = {
                "base_folder_path": folder_path,
                "paper_text": folder_data["paper_text"],
                "available_images": folder_data["available_images"],
                "image_mappings": folder_data["image_mappings"],
                
                "messages": [],
                "analysis_result": None,
                "is_complete": False,
                "user_prompt": effective_user_prompt  # 添加用户提示词到状态
            }
            
            # 8. 配置LangGraph
            config = RunnableConfig(
                configurable={"thread_id": thread_id},
                recursion_limit=100
            )
            
            # 9. 执行分析
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
        finally:
            # 确保每次分析后清理资源
            self._cleanup_analysis_resources()
    
    def cleanup(self) -> None:
        """主动清理所有资源"""
        if self._is_cleaned_up:
            return
            
        logger.info("🧹 开始清理深度论文分析智能体资源...")
        
        try:
            # 清理分析相关资源
            self._cleanup_analysis_resources()
            
            # 清理线程池执行器
            if self._custom_executor and not self._custom_executor._shutdown:
                logger.info("关闭自定义线程池执行器...")
                self._custom_executor.shutdown(wait=False)
                
            # 清理内存管理器
            if self.memory:
                logger.info("清理内存管理器...")
                self.memory = None
                
            self._is_cleaned_up = True
            logger.info("✅ 资源清理完成")
        except Exception as e:
            logger.warning(f"⚠️ 资源清理过程中出现异常: {e}")
    
    def _cleanup_analysis_resources(self) -> None:
        """清理单次分析的相关资源"""
        try:
            # 清理 LangGraph agent
            if self.agent:
                self.agent = None
                
            # 清理工具节点
            if self.tool_node:
                self.tool_node = None
                
            # 清理绑定的 LLM
            if self.llm_with_tools:
                self.llm_with_tools = None
                
            # 清理图片工具
            if self.image_tool:
                self.image_tool = None
                
        except Exception as e:
            logger.warning(f"⚠️ 分析资源清理异常: {e}")
    
    def reset_agent_for_fresh_analysis(self) -> bool:
        """重置 agent 实例以进行全新分析，防止状态累积"""
        try:
            logger.info("🔄 重置 agent 实例以进行全新分析...")
            
            # 清理现有资源
            self._cleanup_analysis_resources()
            
            # 重置内存管理器 - 创建新的实例
            if self.config.memory_enabled and self._custom_executor and not self._custom_executor._shutdown:
                try:
                    self.memory = MemorySaver()
                    logger.info("✅ 内存管理器已重置")
                except Exception as e:
                    logger.warning(f"⚠️ 内存管理器重置失败，将使用无状态模式: {e}")
                    self.memory = None
            
            logger.info("✅ Agent 重置完成，准备进行全新分析")
            return True
            
        except Exception as e:
            logger.error(f"❌ Agent 重置失败: {e}")
            return False
    
    def check_resource_health(self) -> Dict[str, Any]:
        """检查资源健康状态"""
        health_status = {
            "overall_healthy": True,
            "issues": [],
            "warnings": [],
            "custom_executor": {
                "available": False,
                "shutdown": True
            },
            "memory_manager": {
                "available": False,
                "enabled": self.config.memory_enabled
            },
            "analysis_llm": {
                "available": False
            }
        }
        
        try:
            # 检查自定义执行器状态
            if self._custom_executor:
                health_status["custom_executor"]["available"] = True
                health_status["custom_executor"]["shutdown"] = self._custom_executor._shutdown
                if self._custom_executor._shutdown:
                    health_status["issues"].append("自定义线程池执行器已关闭")
                    health_status["overall_healthy"] = False
            else:
                health_status["warnings"].append("未使用自定义线程池执行器")
            
            # 检查内存管理器状态
            if self.memory:
                health_status["memory_manager"]["available"] = True
            else:
                if self.config.memory_enabled:
                    health_status["warnings"].append("内存管理器已禁用或不可用")
            
            # 检查 LLM 状态
            if self.analysis_llm:
                health_status["analysis_llm"]["available"] = True
            else:
                health_status["issues"].append("分析 LLM 不可用")
                health_status["overall_healthy"] = False
            
            # 检查是否已清理
            if self._is_cleaned_up:
                health_status["issues"].append("Agent 已被清理，需要重新初始化")
                health_status["overall_healthy"] = False
        
        except Exception as e:
            health_status["issues"].append(f"健康检查异常: {str(e)}")
            health_status["overall_healthy"] = False
        
        return health_status
    
    def analyze_paper_folder_with_fallback(self, folder_path: str, thread_id: str = "1", 
                                           user_prompt: Optional[str] = None) -> Dict[str, Any]:
        """
        带降级处理的论文分析方法
        
        如果标准分析失败，会尝试降级处理：
        1. 禁用内存管理
        2. 重新创建 agent 实例
        3. 简化分析流程
        
        Args:
            folder_path: 论文文件夹路径
            thread_id: 线程ID
            user_prompt: 用户自定义提示词（可选）
        """
        # 首先检查资源健康状态
        health = self.check_resource_health()
        if not health["overall_healthy"]:
            logger.warning(f"⚠️ 资源健康检查发现问题: {health['issues']}")
            for warning in health["warnings"]:
                logger.warning(f"⚠️ {warning}")
        
        try:
            # 尝试标准分析
            return self.analyze_paper_folder(folder_path, thread_id, user_prompt)
            
        except Exception as primary_error:
            logger.error(f"❌ 标准分析失败: {primary_error}")
            
            # 尝试降级处理
            logger.info("🔄 尝试降级处理...")
            try:
                return self._fallback_analysis(folder_path, thread_id, primary_error, user_prompt)
            except Exception as fallback_error:
                logger.error(f"❌ 降级处理也失败: {fallback_error}")
                return {
                    "error": f"分析完全失败 - 主要错误: {str(primary_error)}, 降级错误: {str(fallback_error)}",
                    "folder_path": folder_path,
                    "health_status": health
                }
    
    def _fallback_analysis(self, folder_path: str, thread_id: str, original_error: Exception,
                          user_prompt: Optional[str] = None) -> Dict[str, Any]:
        """降级分析处理"""
        logger.info("📋 执行降级分析...")
        
        try:
            # 强制清理所有资源
            self._cleanup_analysis_resources()
            
            # 禁用内存管理
            original_memory_enabled = self.config.memory_enabled
            self.config.memory_enabled = False
            self.memory = None
            logger.info("✅ 已禁用内存管理器")
            
            # 重新解析文件夹
            folder_data = self._parse_paper_folder(folder_path)
            
            # 创建简化的图片工具
            self.image_tool = create_image_analysis_tool(folder_path, self.config.vision_model)
            self.llm_with_tools = self.analysis_llm.bind_tools([self.image_tool])
            
            # 重新构建图（无状态模式）
            self._build_graph_with_tools([self.image_tool])
            
            # 创建简化的初始状态
            initial_state: DeepPaperAnalysisState = {
                "base_folder_path": folder_path,
                "paper_text": folder_data["paper_text"],
                "available_images": folder_data["available_images"],
                "image_mappings": folder_data["image_mappings"],
                "messages": [],
                "analysis_result": None,
                "is_complete": False,
                "user_prompt": user_prompt  # 添加用户提示词
            }
            
            # 使用简化配置执行分析
            config = RunnableConfig(
                configurable={"thread_id": f"{thread_id}_fallback"},
                recursion_limit=50  # 降低递归限制
            )
            
            logger.info("🚀 开始降级分析...")
            result = self.agent.invoke(initial_state, config)
            
            # 恢复原始配置
            self.config.memory_enabled = original_memory_enabled
            
            # 添加降级标记
            result["fallback_used"] = True
            result["original_error"] = str(original_error)
            
            logger.info("✅ 降级分析完成")
            return result
            
        except Exception as e:
            # 恢复原始配置
            self.config.memory_enabled = original_memory_enabled
            raise e
    
    @staticmethod
    def _cleanup_executor(executor):
        """静态方法用于 weakref.finalize 清理执行器"""
        try:
            if executor and not executor._shutdown:
                executor.shutdown(wait=False)
        except Exception:
            pass  # 忽略清理时的异常
    
    def __del__(self):
        """析构函数确保资源释放"""
        try:
            self.cleanup()
        except Exception:
            pass  # 忽略析构时的异常
    
    def _should_trigger_video_analysis(self, paper_content: str) -> bool:
        """检测论文是否包含项目相关信息，决定是否启用视频分析"""
        video_indicators = [
            "github.com", "gitlab.com", "bitbucket.org", "项目地址", "源码链接",
            "code available", "open source", "implementation", "repository", 
            "demo video", "项目主页", "source code", "github", "code is available",
            "available at", "project page", "supplementary material"
        ]
        content_lower = paper_content.lower()
        return any(indicator.lower() in content_lower for indicator in video_indicators)
    
    def _initialize_video_tool_if_needed(self, folder_path: str, paper_content: str) -> None:
        """根据论文内容和配置智能决定是否启用视频分析"""
        if not self.config.enable_video_analysis:
            logger.info("ℹ️ 视频分析功能未启用")
            return
        
        if not self._should_trigger_video_analysis(paper_content):
            logger.info("ℹ️ 论文中未检测到项目相关信息，跳过视频分析")
            return
        
        try:
            # 创建视频目录
            video_dir = os.path.join(folder_path, "videos")
            os.makedirs(video_dir, exist_ok=True)
            
            # 创建视频分析工具
            self.video_tool = VideoResourceProcessor(
                base_folder_path=folder_path,
                summarization_model=self.config.video_analysis_model
            )
            
            logger.info("✅ 检测到项目信息，已启用视频分析功能")
            logger.info(f"   视频保存目录: {video_dir}")
            logger.info(f"   使用模型: {self.config.video_analysis_model}")
            
        except Exception as e:
            logger.error(f"❌ 视频分析工具创建失败: {e}")
            self.video_tool = None
    
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
    
    def analyze_and_generate_report(self, folder_path: str, output_path: Optional[str] = None, 
                                   thread_id: str = "1", user_prompt: Optional[str] = None) -> tuple[Dict[str, Any], str]:
        """
        完整的分析和报告生成流程
        
        Args:
            folder_path: 论文文件夹路径
            output_path: 报告输出路径（可选）
            thread_id: 线程ID
            user_prompt: 用户自定义提示词（可选）
            
        Returns:
            tuple: (分析结果, markdown报告内容)
        """
        logger.info(f"开始完整的论文分析和报告生成流程: {folder_path}")
        
        # 执行分析（传递用户提示词）
        analysis_result = self.analyze_paper_folder(folder_path, thread_id, user_prompt)
        
        # 生成报告
        report_content = self.generate_markdown_report(analysis_result, output_path)
        
        logger.info("完整流程执行完成")
        return analysis_result, report_content


# 便捷函数
def create_deep_paper_analysis_agent(
    analysis_model: str = "deepseek.DeepSeek_V3",
    vision_model: str = "ollama.Qwen2_5_VL_7B",
    **kwargs
) -> DeepPaperAnalysisAgent:
    """创建深度论文分析agent的便捷函数"""
    config = DeepPaperAnalysisConfig(
        analysis_model=analysis_model,
        vision_model=vision_model,
        **kwargs
    )
    return DeepPaperAnalysisAgent(config=config)


def create_robust_paper_analysis_agent(
    analysis_model: str = "deepseek.DeepSeek_V3",
    vision_model: str = "ollama.Qwen2_5_VL_7B",
    enable_memory: bool = True,
    **kwargs
) -> DeepPaperAnalysisAgent:
    """
    创建带健壮性处理的深度论文分析agent
    
    这个版本包含：
    - 增强的资源管理
    - 自动降级处理
    - 健康状态监控
    - 推荐用于生产环境
    """
    config = DeepPaperAnalysisConfig(
        analysis_model=analysis_model,
        vision_model=vision_model,
        memory_enabled=enable_memory,
        **kwargs
    )
    
    agent = DeepPaperAnalysisAgent(config=config)
    
    # 添加安全分析方法
    def safe_analyze(folder_path: str, thread_id: str = "1") -> Dict[str, Any]:
        """安全的分析方法，自动使用降级处理"""
        return agent.analyze_paper_folder_with_fallback(folder_path, thread_id)
    
    # 替换默认分析方法
    agent.safe_analyze_paper_folder = safe_analyze
    
    return agent


def create_video_enhanced_analysis_agent(
    analysis_model: str = "deepseek.DeepSeek_V3",
    vision_model: str = "ollama.Qwen2_5_VL_7B",
    video_analysis_model: str = "ollama.Qwen3_30B",
    **kwargs
) -> DeepPaperAnalysisAgent:
    """
    创建带视频分析功能的深度论文分析agent
    
    这个版本包含：
    - 图片分析：使用指定的视觉模型分析论文中的图表
    - 视频分析：自动检测项目信息并搜索相关演示视频
    - 智能触发：只在论文包含项目地址时启用视频功能
    - 完整输出：Markdown报告包含图片和视频展示
    
    Args:
        analysis_model: 主分析LLM模型
        vision_model: 图片理解VLM模型
        video_analysis_model: 视频分析模型
        **kwargs: 其他配置参数
    
    Returns:
        DeepPaperAnalysisAgent: 配置了视频分析功能的智能体
    
    Example:
        # 创建带视频分析的agent
        agent = create_video_enhanced_analysis_agent()
        
        # 分析包含项目信息的论文
        result = agent.analyze_paper_folder("/path/to/paper/folder")
        
        # 如果论文包含GitHub链接等项目信息，会自动搜索相关视频
        # 视频将保存到论文目录下的videos/文件夹
        # 在Markdown输出中会包含视频展示部分
    """
    config = DeepPaperAnalysisConfig(
        analysis_model=analysis_model,
        vision_model=vision_model,
        enable_video_analysis=True,  # 启用视频分析
        video_analysis_model=video_analysis_model,
        **kwargs
    )
    return DeepPaperAnalysisAgent(config=config)


# 测试代码
if __name__ == "__main__":
    # 测试基础agent创建
    agent = create_deep_paper_analysis_agent()
    print(f"深度论文分析Agent创建成功")
    print(f"配置: {agent.get_config().__dict__}")
    
    # 测试带视频分析的agent创建
    video_agent = create_video_enhanced_analysis_agent()
    print(f"\n视频增强论文分析Agent创建成功")
    print(f"视频分析功能: {video_agent.get_config().enable_video_analysis}")
    print(f"视频分析模型: {video_agent.get_config().video_analysis_model}")