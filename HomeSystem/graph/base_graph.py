from loguru import logger

from abc import ABC, abstractmethod
import os
import re
import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any, Union
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.callbacks import UsageMetadataCallbackHandler

from .llm_factory import get_llm, get_embedding, get_vision_llm, validate_vision_input
from .vision_utils import VisionUtils, create_vision_message

# 尝试导入 MCP 管理器，如果失败则禁用 MCP 功能
try:
    from .mcp_manager import MCPManager
    MCP_MANAGER_AVAILABLE = True
except ImportError as e:
    logger.debug(f"MCP Manager not available: {e}")
    MCPManager = None
    MCP_MANAGER_AVAILABLE = False


class BaseGraph(ABC):
    def __init__(self,
                 enable_mcp: bool = False,
                 mcp_config_path: Optional[str] = None
                 ):
        
        self.agent = None
        
        # Token 使用统计相关属性
        try:
            self.token_callback = UsageMetadataCallbackHandler()
            self.session_token_callback = None  # 用于单个会话的统计
            logger.debug("Token使用统计回调初始化成功")
        except Exception as e:
            logger.warning(f"Token使用统计初始化失败，将禁用token统计功能: {e}")
            self.token_callback = None
            self.session_token_callback = None
        
        # MCP 相关属性（完全可选，不影响现有功能）
        self.mcp_enabled = enable_mcp and MCP_MANAGER_AVAILABLE
        self.mcp_manager: Optional[MCPManager] = None
        self.mcp_tools: List[Any] = []
        
        # 如果启用 MCP，初始化管理器
        if self.mcp_enabled:
            self._initialize_mcp(mcp_config_path)
        
    def export_graph_png(self,
                         file_path: str,
                         ):
        if self.agent is None:
            logger.error("Agent is not initialized. Please set the agent before exporting the graph.")
            raise ValueError("Agent is not initialized")
        
        try:
            # 创建输出目录
            if not os.path.exists(file_path):
                os.makedirs(file_path)
            
            # 生成图并保存为PNG文件
            graph_png = self.agent.get_graph().draw_mermaid_png()
            
            file_path = os.path.join(file_path, "agent_graph.png")
            # 保存到文件
            with open(file_path, "wb") as f:
                f.write(graph_png)
            
            logger.info(f"Graph saved to {file_path}")
            
        except Exception as e:
            logger.error(f"Error occurred while saving graph: {e}")

    def _format_response_content(self, content: str) -> str:
        """
        格式化AI响应内容，处理think标签显示
        
        Args:
            content: 原始响应内容
            
        Returns:
            str: 格式化后的内容
        """
        if not content:
            return content
            
        # 检查是否包含think标签
        think_pattern = r'<think>(.*?)</think>'
        match = re.search(think_pattern, content, re.DOTALL)
        
        if match:
            think_content = match.group(1).strip()
            # 移除think标签，获取实际回复内容
            actual_response = re.sub(think_pattern, '', content, flags=re.DOTALL).strip()
            
            # 如果有实际回复内容，只显示实际回复
            if actual_response:
                return actual_response
            # 如果没有实际回复内容，显示think内容但加上标识
            else:
                return f"🤔 思考过程：\n{think_content}"
        
        return content

    def process_image_input(self, image_path: Union[str, Path], text: str = "") -> List[dict]:
        """
        处理图片输入，创建多模态消息内容
        
        Args:
            image_path: 图片文件路径
            text: 附加的文本内容
            
        Returns:
            List[dict]: 多模态消息内容
            
        Raises:
            ValueError: 图片处理失败或格式不支持
            FileNotFoundError: 图片文件不存在
        """
        try:
            # 验证图片文件
            image_path = Path(image_path)
            if not image_path.exists():
                raise FileNotFoundError(f"图片文件不存在: {image_path}")
            
            # 获取图片信息
            image_info = VisionUtils.get_image_info(image_path)
            logger.info(f"处理图片: {image_info['filename']}, 格式: {image_info.get('format', 'unknown')}, "
                       f"尺寸: {image_info.get('width', 0)}x{image_info.get('height', 0)}")
            
            # 创建多模态消息内容
            content = create_vision_message(image_path, text)
            
            return content
            
        except Exception as e:
            logger.error(f"图片输入处理失败: {e}")
            raise

    def run_with_image(self, image_path: Union[str, Path], text: str = "", model_name: Optional[str] = None, thread_id: str = "1"):
        """
        使用图片输入运行agent
        
        Args:
            image_path: 图片文件路径
            text: 附加的文本提示
            model_name: 指定的模型名称（必须支持视觉）
            thread_id: 线程ID
            
        Returns:
            str: AI响应内容
            
        Raises:
            ValueError: 模型不支持视觉或为云端模型
        """
        if self.agent is None:
            logger.error("Agent is not initialized. Please set the agent before running.")
            raise ValueError("Agent is not initialized")
        
        # 验证模型视觉支持（如果指定了模型）
        if model_name:
            validate_vision_input(model_name)
            
            # 如果指定了不同的模型，需要创建一个临时的视觉代理
            from .chat_agent import ChatAgent, ChatAgentConfig
            vision_config = ChatAgentConfig(model_name=model_name)
            vision_agent = ChatAgent(config=vision_config)
            
            # 使用视觉代理处理请求
            return vision_agent.run_with_image(image_path, text, None, thread_id)
        
        try:
            # 处理图片输入
            content = self.process_image_input(image_path, text)
            
            # 创建包含图片的消息
            message = HumanMessage(content=content)
            
            # 创建用于本次运行的token回调
            callbacks = []
            run_callback = None
            
            try:
                if self.token_callback:
                    callbacks.append(self.token_callback)
                run_callback = UsageMetadataCallbackHandler()
                callbacks.append(run_callback)
                logger.debug("图片运行Token回调创建成功")
            except Exception as e:
                logger.warning(f"图片运行Token回调创建失败，继续执行但不统计token: {e}")
            
            config = {
                "configurable": {"thread_id": thread_id}, 
                "recursion_limit": 100,
                "callbacks": callbacks
            }
            input_data = {"messages": [message]}
            
            logger.info(f"使用图片运行Agent: {Path(image_path).name}")
            
            events = self.agent.stream(
                input_data,
                config,
                stream_mode="values"
            )
            
            # 收集所有非SystemMessage的内容
            result_content = ""
            for event in events:
                message = event["messages"][-1]
                if not isinstance(message, SystemMessage):
                    if hasattr(message, 'content') and message.content:
                        result_content = message.content
            
            # 记录本次运行的token使用情况
            try:
                if run_callback and run_callback.usage_metadata:
                    logger.info(f"本次图片运行Token使用: {run_callback.usage_metadata}")
            except Exception as e:
                logger.debug(f"图片运行Token使用统计记录失败: {e}")
            
            return result_content
            
        except Exception as e:
            logger.error(f"图片运行失败: {e}")
            raise

    def run(self, input_text: str, thread_id: str = "1"):
        """
        运行单次执行模式，区别于chat交互模式
        
        Args:
            input_text: 输入文本
            thread_id: 线程ID，默认为"1"
            
        Returns:
            str: 原始输出内容，不进行格式化
        """
        if self.agent is None:
            logger.error("Agent is not initialized. Please set the agent before running.")
            raise ValueError("Agent is not initialized")
        
        # 创建用于本次运行的token回调
        callbacks = []
        run_callback = None
        
        try:
            if self.token_callback:
                callbacks.append(self.token_callback)
            run_callback = UsageMetadataCallbackHandler()
            callbacks.append(run_callback)
            logger.debug("Token回调创建成功")
        except Exception as e:
            logger.warning(f"Token回调创建失败，继续执行但不统计token: {e}")
        
        config = {
            "configurable": {"thread_id": thread_id}, 
            "recursion_limit": 100,
            "callbacks": callbacks
        }
        input_data = {"messages": [{"role": "user", "content": input_text}]}
        
        logger.info(f"开始运行Agent，线程ID: {thread_id}")
        
        events = self.agent.stream(
            input_data,
            config,
            stream_mode="values"
        )
        
        # 收集所有非SystemMessage的内容
        result_content = ""
        for event in events:
            message = event["messages"][-1]
            if not isinstance(message, SystemMessage):
                if hasattr(message, 'content') and message.content:
                    result_content = message.content
        
        # 记录本次运行的token使用情况
        try:
            if run_callback and run_callback.usage_metadata:
                logger.info(f"本次运行Token使用: {run_callback.usage_metadata}")
        except Exception as e:
            logger.debug(f"Token使用统计记录失败: {e}")
        
        return result_content

    def chat_with_image(self, image_path: Union[str, Path], model_name: Optional[str] = None):
        """
        支持图片的交互式聊天模式
        
        Args:
            image_path: 图片文件路径
            model_name: 指定的模型名称（必须支持视觉）
        """
        logger.info("Starting vision chat session. Type 'exit' to quit.")
        
        if self.agent is None:
            logger.error("Agent is not initialized. Please set the agent before starting the chat.")
            raise ValueError("Agent is not initialized")

        # 验证模型视觉支持
        if model_name:
            validate_vision_input(model_name)
        
        # 显示图片信息
        try:
            image_info = VisionUtils.get_image_info(image_path)
            logger.info(f"加载图片: {image_info['filename']}, "
                       f"格式: {image_info.get('format', 'unknown')}, "
                       f"尺寸: {image_info.get('width', 0)}x{image_info.get('height', 0)}")
        except Exception as e:
            logger.error(f"无法加载图片: {e}")
            return

        # 为聊天会话创建独立的token回调
        callbacks = []
        try:
            if self.token_callback:
                callbacks.append(self.token_callback)
            self.session_token_callback = UsageMetadataCallbackHandler()
            callbacks.append(self.session_token_callback)
            logger.debug("图片聊天会话Token回调创建成功")
        except Exception as e:
            logger.warning(f"图片聊天会话Token回调创建失败，继续执行但不统计token: {e}")
            self.session_token_callback = None
        
        config = {
            "configurable": {"thread_id": "1"}, 
            "recursion_limit": 100,
            "callbacks": callbacks
        }
        
        while True:
            try:
                user_input = input("> ")
            except UnicodeDecodeError:
                import sys
                user_input = sys.stdin.buffer.readline().decode('utf-8', errors='replace').strip()
            
            if user_input.lower() in ['exit', 'quit', 'q']:
                logger.info("Exiting vision chat...")
                # 显示本次聊天会话的token使用统计
                try:
                    if self.session_token_callback and self.session_token_callback.usage_metadata:
                        logger.info(f"本次图片聊天会话Token使用: {self.session_token_callback.usage_metadata}")
                except Exception as e:
                    logger.debug(f"图片聊天会话Token使用统计记录失败: {e}")
                break
            
            try:
                logger.info("Processing your request with image...")
                
                # 处理图片输入
                content = self.process_image_input(image_path, user_input)
                message = HumanMessage(content=content)
                
                input_data = {"messages": [message]}
                events = self.agent.stream(
                    input_data,
                    config,
                    stream_mode="values"
                )
                
                # 处理响应
                for event in events:
                    message = event["messages"][-1]
                    if isinstance(message, SystemMessage):
                        continue
                    else:
                        if hasattr(message, 'content') and message.content:
                            formatted_content = self._format_response_content(message.content)
                            from langchain_core.messages import AIMessage
                            formatted_message = AIMessage(content=formatted_content)
                            formatted_message.pretty_print()
                        else:
                            message.pretty_print()
                            
            except Exception as e:
                logger.error(f"处理请求失败: {e}")
                logger.info("请重试或输入 'exit' 退出")
                continue
            
            logger.info("Task completed. Enter your next query or type 'exit' to quit")

    def chat(self,):
        logger.info("Starting chat session. Type 'exit' to quit.")
        if self.agent is None:
            logger.error("Agent is not initialized. Please set the agent before starting the chat.")
            raise ValueError("Agent is not initialized")

        # 为聊天会话创建独立的token回调
        callbacks = []
        try:
            if self.token_callback:
                callbacks.append(self.token_callback)
            self.session_token_callback = UsageMetadataCallbackHandler()
            callbacks.append(self.session_token_callback)
            logger.debug("聊天会话Token回调创建成功")
        except Exception as e:
            logger.warning(f"聊天会话Token回调创建失败，继续执行但不统计token: {e}")
            self.session_token_callback = None
        
        config = {
            "configurable": {"thread_id": "1"}, 
            "recursion_limit": 100,
            "callbacks": callbacks
        }
        while True:
            try:
                user_input = input("> ")
            except UnicodeDecodeError:
                # Handle encoding errors by reading raw bytes and decoding with errors='replace'
                import sys
                user_input = sys.stdin.buffer.readline().decode('utf-8', errors='replace').strip()
            
            if user_input.lower() in ['exit', 'quit', 'q']:
                logger.info("Exiting the program...")
                # 显示本次聊天会话的token使用统计
                try:
                    if self.session_token_callback and self.session_token_callback.usage_metadata:
                        logger.info(f"本次聊天会话Token使用: {self.session_token_callback.usage_metadata}")
                except Exception as e:
                    logger.debug(f"聊天会话Token使用统计记录失败: {e}")
                break
            
            logger.info("Processing your request...")
            input_text = {"messages": [{"role": "user", "content": user_input}]}
            events = self.agent.stream(
                input_text,
                config,
                stream_mode="values"
            )
            
            # 如果是system message，则不输出
            for event in events:
                message = event["messages"][-1]
                if isinstance(message, SystemMessage):
                    continue
                else:
                    # 格式化消息内容
                    if hasattr(message, 'content') and message.content:
                        formatted_content = self._format_response_content(message.content)
                        # 创建一个新的消息对象用于显示
                        from langchain_core.messages import AIMessage
                        formatted_message = AIMessage(content=formatted_content)
                        formatted_message.pretty_print()
                    else:
                        message.pretty_print()
            
            logger.info("Task completed. Enter your next query or type 'exit' to quit")

    # ========== MCP 相关方法（完全可选，不影响现有功能） ==========
    
    def _initialize_mcp(self, config_path: Optional[str] = None) -> None:
        """初始化 MCP 管理器（私有方法，仅在启用时调用）"""
        try:
            if not MCP_MANAGER_AVAILABLE:
                logger.warning("MCP Manager not available, MCP functionality disabled")
                self.mcp_enabled = False
                return
                
            self.mcp_manager = MCPManager(config_path)
            logger.info("MCP Manager created successfully")
            
            # 异步初始化将在子类中调用
            
        except Exception as e:
            logger.error(f"Failed to initialize MCP Manager: {e}")
            self.mcp_enabled = False
            self.mcp_manager = None
    
    async def initialize_mcp_async(self) -> bool:
        """异步初始化 MCP 连接（需要在子类中调用）"""
        if not self.mcp_enabled or not self.mcp_manager:
            return False
            
        try:
            success = await self.mcp_manager.initialize()
            if success:
                # 获取所有可用工具
                self.mcp_tools = await self.mcp_manager.get_all_tools()
                logger.info(f"MCP initialized successfully with {len(self.mcp_tools)} tools")
            return success
        except Exception as e:
            logger.error(f"Failed to initialize MCP async: {e}")
            return False
    
    def get_mcp_tools(self, transport_type: Optional[str] = None, server_name: Optional[str] = None) -> List[Any]:
        """获取 MCP 工具
        
        Args:
            transport_type: 传输类型筛选 ('stdio' 或 'sse')
            server_name: 服务器名称筛选
            
        Returns:
            List[Any]: 工具列表，如果 MCP 未启用则返回空列表
        """
        if not self.mcp_enabled or not self.mcp_manager:
            return []
            
        try:
            # 同步方法，返回已缓存的工具
            if transport_type:
                # 按传输类型筛选（需要异步调用，这里返回缓存）
                return [tool for tool in self.mcp_tools 
                       if hasattr(tool, 'transport_type') and tool.transport_type == transport_type]
            elif server_name:
                # 按服务器名称筛选（需要异步调用，这里返回缓存）
                return [tool for tool in self.mcp_tools 
                       if hasattr(tool, 'server_name') and tool.server_name == server_name]
            else:
                return self.mcp_tools.copy()
                
        except Exception as e:
            logger.error(f"Failed to get MCP tools: {e}")
            return []
    
    async def get_mcp_tools_async(self, transport_type: Optional[str] = None, server_name: Optional[str] = None) -> List[Any]:
        """异步获取 MCP 工具（实时查询）"""
        if not self.mcp_enabled or not self.mcp_manager:
            return []
            
        try:
            if transport_type:
                return await self.mcp_manager.get_tools_by_transport(transport_type)
            elif server_name:
                return await self.mcp_manager.get_tools_by_server(server_name)
            else:
                return await self.mcp_manager.get_all_tools()
                
        except Exception as e:
            logger.error(f"Failed to get MCP tools async: {e}")
            return []
    
    async def add_mcp_server(self, server_name: str, server_config: Dict[str, Any]) -> bool:
        """动态添加 MCP 服务器"""
        if not self.mcp_enabled or not self.mcp_manager:
            logger.warning("MCP not enabled, cannot add server")
            return False
            
        try:
            success = await self.mcp_manager.add_server(server_name, server_config)
            if success:
                # 刷新工具缓存
                self.mcp_tools = await self.mcp_manager.get_all_tools()
            return success
        except Exception as e:
            logger.error(f"Failed to add MCP server {server_name}: {e}")
            return False
    
    async def remove_mcp_server(self, server_name: str) -> bool:
        """动态移除 MCP 服务器"""
        if not self.mcp_enabled or not self.mcp_manager:
            logger.warning("MCP not enabled, cannot remove server")
            return False
            
        try:
            success = await self.mcp_manager.remove_server(server_name)
            if success:
                # 刷新工具缓存
                self.mcp_tools = await self.mcp_manager.get_all_tools()
            return success
        except Exception as e:
            logger.error(f"Failed to remove MCP server {server_name}: {e}")
            return False
    
    async def reload_mcp_tools(self) -> int:
        """重新加载 MCP 工具"""
        if not self.mcp_enabled or not self.mcp_manager:
            return 0
            
        try:
            self.mcp_tools = await self.mcp_manager.get_all_tools()
            logger.info(f"Reloaded {len(self.mcp_tools)} MCP tools")
            return len(self.mcp_tools)
        except Exception as e:
            logger.error(f"Failed to reload MCP tools: {e}")
            return 0
    
    async def mcp_health_check(self) -> Dict[str, bool]:
        """检查 MCP 服务器健康状态"""
        if not self.mcp_enabled or not self.mcp_manager:
            return {}
            
        try:
            return await self.mcp_manager.health_check_all()
        except Exception as e:
            logger.error(f"MCP health check failed: {e}")
            return {}
    
    def get_mcp_status(self) -> Dict[str, Any]:
        """获取 MCP 状态信息"""
        if not self.mcp_manager:
            return {
                'mcp_available': MCP_MANAGER_AVAILABLE,
                'enabled': False,
                'initialized': False,
                'tools_count': 0,
                'servers': []
            }
            
        status = self.mcp_manager.get_status()
        status['tools_count'] = len(self.mcp_tools)
        return status
    
    async def shutdown_mcp(self) -> None:
        """关闭 MCP 连接"""
        if self.mcp_enabled and self.mcp_manager:
            try:
                await self.mcp_manager.shutdown()
                logger.info("MCP Manager shutdown complete")
            except Exception as e:
                logger.error(f"Error shutting down MCP Manager: {e}")
            finally:
                self.mcp_tools.clear()

    # ========== Token 使用统计方法 ==========
    
    def _parse_usage_metadata(self, usage_metadata: Dict[str, Any]) -> tuple:
        """
        解析不同格式的token使用元数据
        
        Args:
            usage_metadata: 原始使用元数据
            
        Returns:
            tuple: (input_tokens, output_tokens, total_tokens)
        """
        if not usage_metadata:
            return 0, 0, 0
        
        # 直接格式: {'input_tokens': 10, 'output_tokens': 20, 'total_tokens': 30}
        if 'input_tokens' in usage_metadata:
            return (
                usage_metadata.get('input_tokens', 0),
                usage_metadata.get('output_tokens', 0),
                usage_metadata.get('total_tokens', 0)
            )
        
        # 按模型分组格式: {'model_name': {'input_tokens': 10, 'output_tokens': 20, 'total_tokens': 30}}
        input_total = 0
        output_total = 0
        total_total = 0
        
        for model_name, model_usage in usage_metadata.items():
            if isinstance(model_usage, dict):
                input_total += model_usage.get('input_tokens', 0)
                output_total += model_usage.get('output_tokens', 0)
                total_total += model_usage.get('total_tokens', 0)
        
        return input_total, output_total, total_total
    
    def get_token_usage(self) -> Dict[str, Any]:
        """
        获取累计的token使用统计
        
        Returns:
            Dict[str, Any]: Token使用统计信息
        """
        try:
            if not self.token_callback or not self.token_callback.usage_metadata:
                return {
                    'input_tokens': 0,
                    'output_tokens': 0,
                    'total_tokens': 0,
                    'has_data': False
                }
            
            usage = self.token_callback.usage_metadata
            
            # 处理不同的token metadata格式
            input_tokens, output_tokens, total_tokens = self._parse_usage_metadata(usage)
            
            return {
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'total_tokens': total_tokens,
                'has_data': True,
                'raw_metadata': usage
            }
        except Exception as e:
            logger.warning(f"获取token使用统计失败: {e}")
            return {
                'input_tokens': 0,
                'output_tokens': 0,
                'total_tokens': 0,
                'has_data': False,
                'error': str(e)
            }
    
    def get_session_token_usage(self) -> Dict[str, Any]:
        """
        获取当前会话的token使用统计
        
        Returns:
            Dict[str, Any]: 会话Token使用统计信息
        """
        try:
            if not self.session_token_callback or not self.session_token_callback.usage_metadata:
                return {
                    'input_tokens': 0,
                    'output_tokens': 0,
                    'total_tokens': 0,
                    'has_data': False
                }
            
            usage = self.session_token_callback.usage_metadata
            
            # 处理不同的token metadata格式
            input_tokens, output_tokens, total_tokens = self._parse_usage_metadata(usage)
            
            return {
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'total_tokens': total_tokens,
                'has_data': True,
                'raw_metadata': usage
            }
        except Exception as e:
            logger.warning(f"获取会话token使用统计失败: {e}")
            return {
                'input_tokens': 0,
                'output_tokens': 0,
                'total_tokens': 0,
                'has_data': False,
                'error': str(e)
            }
    
    def reset_token_usage(self) -> None:
        """重置累计token使用统计"""
        try:
            self.token_callback = UsageMetadataCallbackHandler()
            logger.info("Token使用统计已重置")
        except Exception as e:
            logger.error(f"重置Token使用统计失败: {e}")
            self.token_callback = None
    
    def reset_session_token_usage(self) -> None:
        """重置会话token使用统计"""
        try:
            if self.session_token_callback:
                self.session_token_callback = UsageMetadataCallbackHandler()
                logger.info("会话Token使用统计已重置")
        except Exception as e:
            logger.error(f"重置会话Token使用统计失败: {e}")
            self.session_token_callback = None
    
    def print_token_statistics(self, include_session: bool = True) -> None:
        """
        打印格式化的token使用统计
        
        Args:
            include_session: 是否包含会话统计
        """
        logger.info("=" * 60)
        logger.info("Token 使用统计")
        logger.info("=" * 60)
        
        # 累计统计
        total_usage = self.get_token_usage()
        if total_usage['has_data']:
            logger.info("📊 累计统计:")
            logger.info(f"  输入Token: {total_usage['input_tokens']:,}")
            logger.info(f"  输出Token: {total_usage['output_tokens']:,}")
            logger.info(f"  总Token: {total_usage['total_tokens']:,}")
        else:
            logger.info("📊 累计统计: 暂无数据")
        
        # 会话统计
        if include_session:
            session_usage = self.get_session_token_usage()
            if session_usage['has_data']:
                logger.info("\n🔄 当前会话统计:")
                logger.info(f"  输入Token: {session_usage['input_tokens']:,}")
                logger.info(f"  输出Token: {session_usage['output_tokens']:,}")
                logger.info(f"  总Token: {session_usage['total_tokens']:,}")
            else:
                logger.info("\n🔄 当前会话统计: 暂无数据")
        
        logger.info("=" * 60)

