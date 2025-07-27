from loguru import logger

from abc import ABC, abstractmethod
import os
import re
from langchain_core.messages import SystemMessage

from .llm_factory import get_llm, get_embedding


class BaseGraph(ABC):
    def __init__(self,
                 ):
        
        self.agent = None
        
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

    def chat(self,):
        logger.info("Starting chat session. Type 'exit' to quit.")
        if self.agent is None:
            logger.error("Agent is not initialized. Please set the agent before starting the chat.")
            raise ValueError("Agent is not initialized")

        
        config = {"configurable": {"thread_id": "1"}, "recursion_limit": 100}
        while True:
            try:
                user_input = input("> ")
            except UnicodeDecodeError:
                # Handle encoding errors by reading raw bytes and decoding with errors='replace'
                import sys
                user_input = sys.stdin.buffer.readline().decode('utf-8', errors='replace').strip()
            
            if user_input.lower() in ['exit', 'quit', 'q']:
                logger.info("Exiting the program...")
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

        

