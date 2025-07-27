from .llm_factory import llm_factory
from .base_graph import BaseGraph

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from typing import Annotated, Optional, Dict, Any
from typing_extensions import TypedDict
import operator
import json
from pathlib import Path
from loguru import logger

from langchain_core.messages import AIMessage, SystemMessage


class State(TypedDict):
    messages: Annotated[list, add_messages]
    conversation_count: Annotated[int, operator.add]


class ChatAgentConfig:
    """聊天代理配置类"""
    
    def __init__(self, 
                 model_name: str = "ollama.Qwen3_30B",
                 system_message: str = "你是一个友善且有用的私人家庭助理。你可以帮助处理日常问题、提供信息、安排计划等。请用中文回答，保持礼貌和专业。",
                 memory_enabled: bool = True,
                 conversation_context_limit: int = 50,
                 custom_settings: Optional[Dict[str, Any]] = None):
        
        self.model_name = model_name
        self.system_message = system_message
        self.memory_enabled = memory_enabled
        self.conversation_context_limit = conversation_context_limit
        self.custom_settings = custom_settings or {}
    
    @classmethod
    def load_from_file(cls, config_path: str) -> "ChatAgentConfig":
        """从配置文件加载配置"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            return cls(**config_data)
        except Exception as e:
            logger.warning(f"配置文件加载失败，使用默认配置: {e}")
            return cls()
    
    def save_to_file(self, config_path: str) -> None:
        """保存配置到文件"""
        config_data = {
            'model_name': self.model_name,
            'system_message': self.system_message,
            'memory_enabled': self.memory_enabled,
            'conversation_context_limit': self.conversation_context_limit,
            'custom_settings': self.custom_settings
        }
        
        # 创建目录
        Path(config_path).parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"配置已保存到: {config_path}")


class ChatAgent(BaseGraph):
    """基础聊天代理"""
    
    def __init__(self, 
                 config: Optional[ChatAgentConfig] = None,
                 config_path: Optional[str] = None):
        
        super().__init__()
        
        # 加载配置
        if config_path:
            self.config = ChatAgentConfig.load_from_file(config_path)
        elif config:
            self.config = config
        else:
            self.config = ChatAgentConfig()
        
        logger.info(f"初始化聊天代理，使用模型: {self.config.model_name}")
        
        # 创建LLM
        self.llm = llm_factory.create_llm(model_name=self.config.model_name)
        
        # 设置内存管理
        self.memory = MemorySaver() if self.config.memory_enabled else None
        
        # 构建图
        self._build_graph()
        
        logger.info("聊天代理初始化完成")
    
    def _build_graph(self) -> None:
        """构建对话图"""
        # 创建状态图
        graph = StateGraph(State)
        
        # 添加聊天节点
        graph.add_node("chat", self._chat_node)
        
        # 设置入口和流程
        graph.add_edge(START, "chat")
        graph.add_edge("chat", END)
        
        # 编译图
        self.agent = graph.compile(checkpointer=self.memory)
        
        logger.info("对话图构建完成")
    
    def _chat_node(self, state: State) -> Dict[str, Any]:
        """聊天节点处理逻辑"""
        messages = state["messages"]
        
        # 构建完整的消息列表（包含系统消息）
        full_messages = [SystemMessage(content=self.config.system_message)]
        
        # 如果启用记忆功能，限制对话上下文长度
        if self.config.memory_enabled and len(messages) > self.config.conversation_context_limit:
            # 保留最近的对话
            messages = messages[-self.config.conversation_context_limit:]
            logger.debug(f"对话上下文已截断至最近 {self.config.conversation_context_limit} 条消息")
        
        full_messages.extend(messages)
        
        # 调用LLM生成回复
        try:
            response = self.llm.invoke(full_messages)
            logger.debug(f"LLM响应: {response.content[:100]}...")
        except Exception as e:
            logger.error(f"LLM调用失败: {e}")
            response = AIMessage(content="抱歉，我遇到了一些技术问题，无法正常回复。请稍后再试。")
        
        return {
            "messages": [response],
            "conversation_count": 1
        }
    
    def get_config(self) -> ChatAgentConfig:
        """获取当前配置"""
        return self.config
    
    def update_config(self, **kwargs) -> None:
        """更新配置"""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
                logger.info(f"配置更新: {key} = {value}")
            else:
                logger.warning(f"未知配置项: {key}")
        
        # 如果模型相关配置更新，重新创建LLM
        if 'model_name' in kwargs:
            self.llm = llm_factory.create_llm(model_name=self.config.model_name)
            logger.info("LLM已重新创建")
    
    def get_conversation_stats(self, thread_id: str = "1") -> Dict[str, Any]:
        """获取对话统计信息"""
        return {
            "memory_enabled": self.config.memory_enabled,
            "thread_id": thread_id,
            "model_name": self.config.model_name,
            "conversation_context_limit": self.config.conversation_context_limit,
            "system_message": self.config.system_message[:100] + "..." if len(self.config.system_message) > 100 else self.config.system_message
        }
    
    def clear_memory(self, thread_id: str = "1") -> bool:
        """清除对话记忆"""
        if not self.config.memory_enabled or not self.memory:
            logger.warning("记忆功能未启用")
            return False
        
        try:
            # 由于MemorySaver没有直接的clear方法，我们创建一个新的checkpointer
            self.memory = MemorySaver()
            self.agent = self.agent.with_config(checkpointer=self.memory)
            logger.info(f"线程 {thread_id} 的对话记忆已清除")
            return True
        except Exception as e:
            logger.error(f"清除对话记忆失败: {e}")
            return False
    
    def chat_once(self, message: str, thread_id: str = "1") -> str:
        """单次对话（用于API调用）"""
        from langchain_core.messages import HumanMessage
        
        try:
            # 创建输入数据
            input_data: State = {
                "messages": [HumanMessage(content=message)],
                "conversation_count": 0
            }
            
            config_dict = {"configurable": {"thread_id": thread_id}, "recursion_limit": 100}
            result = self.agent.invoke(input_data, config_dict)  # type: ignore
            
            # 获取最后一条AI消息
            if result and "messages" in result and result["messages"]:
                last_message = result["messages"][-1]
                if hasattr(last_message, 'content'):
                    # 使用基类的格式化方法处理响应内容
                    formatted_content = self._format_response_content(last_message.content)
                    return formatted_content
                else:
                    return str(last_message)
            else:
                return "抱歉，没有获取到有效响应。"
                
        except Exception as e:
            logger.error(f"单次对话失败: {e}")
            return f"抱歉，处理您的消息时出现错误: {str(e)}"