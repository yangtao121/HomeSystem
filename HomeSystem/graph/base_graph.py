from loguru import logger

from abc import ABC, abstractmethod
import os
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
                    message.pretty_print()
            
            logger.info("Task completed. Enter your next query or type 'exit' to quit")
        

