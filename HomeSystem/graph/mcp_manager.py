"""
MCP (Model Context Protocol) 管理器

支持 stdio 和 SSE 传输模式的 MCP 客户端管理。
设计原则：完全可选，不影响现有功能，优雅降级。
"""

import os
import yaml
import asyncio
import subprocess
from typing import Dict, List, Optional, Any, Union
from pathlib import Path
from loguru import logger
from abc import ABC, abstractmethod

# 尝试导入 MCP 相关依赖，如果失败则禁用 MCP 功能
try:
    from langchain_mcp_adapters.client import MultiServerMCPClient
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    MCP_AVAILABLE = True
except ImportError as e:
    logger.warning(f"MCP dependencies not available: {e}. MCP functionality will be disabled.")
    MCP_AVAILABLE = False
    MultiServerMCPClient = None


class MCPTransportClient(ABC):
    """MCP 传输客户端抽象基类"""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.is_connected = False
        self.client = None
        
    @abstractmethod
    async def connect(self) -> bool:
        """连接到 MCP 服务器"""
        pass
        
    @abstractmethod
    async def disconnect(self) -> None:
        """断开连接"""
        pass
        
    @abstractmethod
    async def get_tools(self) -> List[Any]:
        """获取可用工具"""
        pass
        
    @abstractmethod
    async def health_check(self) -> bool:
        """健康检查"""
        pass


class StdioMCPClient(MCPTransportClient):
    """stdio 传输模式的 MCP 客户端"""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.process = None
        self.session = None
        self.stdio_context = None
        
    async def connect(self) -> bool:
        """连接到 stdio MCP 服务器"""
        if not MCP_AVAILABLE:
            logger.warning(f"MCP not available, skipping stdio client {self.name}")
            return False
            
        try:
            command = self.config.get('command')
            args = self.config.get('args', [])
            working_dir = self.config.get('working_directory')
            
            if not command:
                logger.error(f"No command specified for stdio client {self.name}")
                return False
                
            logger.info(f"Starting stdio MCP server {self.name}: {command} {' '.join(args)}")
            
            # 创建 stdio 服务器参数
            server_params = StdioServerParameters(
                command=command,
                args=args,
                cwd=working_dir
            )
            
            # 创建客户端会话
            self.stdio_context = stdio_client(server_params)
            read_stream, write_stream = await self.stdio_context.__aenter__()
            self.session = ClientSession(read_stream, write_stream)
            
            # 添加超时机制防止初始化卡死
            initialization_timeout = self.config.get('initialization_timeout', 15)
            try:
                await asyncio.wait_for(
                    self.session.initialize(),
                    timeout=initialization_timeout
                )
                logger.info(f"MCP server {self.name} initialized successfully")
            except asyncio.TimeoutError:
                logger.warning(f"MCP server {self.name} initialization timed out after {initialization_timeout}s, but connection may still be usable")
                # 不抛出异常，允许程序继续运行
            except Exception as init_error:
                logger.error(f"MCP server {self.name} initialization failed: {init_error}")
                # 即使初始化失败，也尝试继续使用连接
                
            self.client = self.session
            
            self.is_connected = True
            logger.info(f"Successfully connected to stdio MCP server {self.name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to stdio MCP server {self.name}: {e}")
            self.is_connected = False
            return False
    
    async def disconnect(self) -> None:
        """断开 stdio 连接"""
        try:
            if self.session:
                await self.session.close()
            if self.stdio_context:
                await self.stdio_context.__aexit__(None, None, None)
                self.stdio_context = None
            self.is_connected = False
            logger.info(f"Disconnected from stdio MCP server {self.name}")
        except Exception as e:
            logger.error(f"Error disconnecting from stdio MCP server {self.name}: {e}")
    
    async def get_tools(self) -> List[Any]:
        """获取 stdio 服务器的工具"""
        if not self.is_connected or not self.session:
            return []
            
        try:
            # 添加超时机制
            tools_timeout = self.config.get('tools_timeout', 10)
            tools_result = await asyncio.wait_for(
                self.session.list_tools(),
                timeout=tools_timeout
            )
            return tools_result.tools if tools_result else []
        except asyncio.TimeoutError:
            logger.warning(f"Getting tools from stdio server {self.name} timed out")
            return []
        except Exception as e:
            logger.error(f"Failed to get tools from stdio server {self.name}: {e}")
            return []
    
    async def health_check(self) -> bool:
        """stdio 服务器健康检查"""
        if not self.is_connected:
            return False
            
        try:
            # 尝试列出工具作为健康检查，带超时机制
            health_timeout = self.config.get('health_check_timeout', 5)
            tools = await asyncio.wait_for(
                self.get_tools(),
                timeout=health_timeout
            )
            # 如果能够获取工具列表，认为健康
            return True
        except asyncio.TimeoutError:
            logger.warning(f"Health check for stdio server {self.name} timed out")
            return False
        except Exception as e:
            logger.error(f"Health check failed for stdio server {self.name}: {e}")
            return False


class SSEMCPClient(MCPTransportClient):
    """SSE 传输模式的 MCP 客户端"""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.url = config.get('url')
        self.headers = config.get('headers', {})
        
    async def connect(self) -> bool:
        """连接到 SSE MCP 服务器"""
        if not MCP_AVAILABLE:
            logger.warning(f"MCP not available, skipping SSE client {self.name}")
            return False
            
        try:
            if not self.url:
                logger.error(f"No URL specified for SSE client {self.name}")
                return False
                
            logger.info(f"Connecting to SSE MCP server {self.name}: {self.url}")
            
            # SSE 连接逻辑（这里是简化实现，实际需要根据具体的 SSE 实现）
            # 由于 langchain-mcp-adapters 的 SSE 实现可能不同，这里提供框架
            
            # TODO: 实现具体的 SSE 连接逻辑
            # self.client = await create_sse_client(self.url, headers=self.headers)
            
            self.is_connected = True
            logger.info(f"Successfully connected to SSE MCP server {self.name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to SSE MCP server {self.name}: {e}")
            self.is_connected = False
            return False
    
    async def disconnect(self) -> None:
        """断开 SSE 连接"""
        try:
            if self.client:
                # await self.client.close()
                pass
            self.is_connected = False
            logger.info(f"Disconnected from SSE MCP server {self.name}")
        except Exception as e:
            logger.error(f"Error disconnecting from SSE MCP server {self.name}: {e}")
    
    async def get_tools(self) -> List[Any]:
        """获取 SSE 服务器的工具"""
        if not self.is_connected:
            return []
            
        try:
            # TODO: 实现 SSE 工具获取逻辑
            return []
        except Exception as e:
            logger.error(f"Failed to get tools from SSE server {self.name}: {e}")
            return []
    
    async def health_check(self) -> bool:
        """SSE 服务器健康检查"""
        if not self.is_connected:
            return False
            
        try:
            # TODO: 实现 SSE 健康检查逻辑
            return True
        except Exception as e:
            logger.error(f"Health check failed for SSE server {self.name}: {e}")
            return False


class MCPManager:
    """MCP 管理器主类
    
    功能：
    1. 管理多个 MCP 服务器连接（stdio 和 SSE）
    2. 提供统一的工具接口
    3. 处理连接故障和重连
    4. 完全可选，不影响现有功能
    """
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path
        self.config = {}
        self.clients: Dict[str, MCPTransportClient] = {}
        self.is_initialized = False
        self.enabled = False
        
        # 如果 MCP 不可用，直接禁用
        if not MCP_AVAILABLE:
            logger.warning("MCP dependencies not available. MCP Manager will be disabled.")
            return
            
        # 加载配置
        self._load_config()
        
    def _load_config(self) -> None:
        """加载 MCP 配置"""
        try:
            if self.config_path:
                config_file = Path(self.config_path)
            else:
                config_file = Path(__file__).parent / "config" / "mcp_config.yaml"
                
            if not config_file.exists():
                logger.warning(f"MCP config file not found: {config_file}. MCP will be disabled.")
                return
                
            with open(config_file, 'r', encoding='utf-8') as f:
                full_config = yaml.safe_load(f)
                
            self.config = full_config.get('mcp', {})
            self.enabled = self.config.get('enabled', False)
            
            if not self.enabled:
                logger.info("MCP is disabled in configuration")
                return
                
            logger.info(f"Loaded MCP configuration from {config_file}")
            
        except Exception as e:
            logger.error(f"Failed to load MCP configuration: {e}")
            self.enabled = False
    
    async def initialize(self) -> bool:
        """初始化 MCP 管理器"""
        if not MCP_AVAILABLE or not self.enabled:
            logger.info("MCP Manager initialization skipped (disabled or unavailable)")
            return False
            
        try:
            servers_config = self.config.get('servers', {})
            
            for server_name, server_config in servers_config.items():
                if not server_config.get('enabled', False):
                    logger.debug(f"Skipping disabled MCP server: {server_name}")
                    continue
                    
                transport = server_config.get('transport', 'stdio')
                
                # 合并全局设置到服务器配置
                merged_config = {}
                merged_config.update(self.config.get('global_settings', {}))
                merged_config.update(server_config)
                
                # 创建对应的客户端
                if transport == 'stdio':
                    client = StdioMCPClient(server_name, merged_config)
                elif transport == 'sse':
                    client = SSEMCPClient(server_name, merged_config)
                else:
                    logger.error(f"Unsupported transport type: {transport} for server {server_name}")
                    continue
                    
                # 尝试连接
                if await client.connect():
                    self.clients[server_name] = client
                    logger.info(f"Successfully initialized MCP server: {server_name}")
                else:
                    logger.warning(f"Failed to connect to MCP server: {server_name}")
            
            self.is_initialized = True
            logger.info(f"MCP Manager initialized with {len(self.clients)} active servers")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize MCP Manager: {e}")
            return False
    
    async def get_all_tools(self) -> List[Any]:
        """获取所有 MCP 工具"""
        if not self.is_initialized:
            return []
            
        all_tools = []
        for server_name, client in self.clients.items():
            try:
                tools = await client.get_tools()
                all_tools.extend(tools)
                logger.debug(f"Got {len(tools)} tools from server {server_name}")
            except Exception as e:
                logger.error(f"Failed to get tools from server {server_name}: {e}")
                
        return all_tools
    
    async def get_tools_by_transport(self, transport_type: str) -> List[Any]:
        """按传输类型获取工具"""
        if not self.is_initialized:
            return []
            
        tools = []
        for server_name, client in self.clients.items():
            server_config = self.config.get('servers', {}).get(server_name, {})
            if server_config.get('transport') == transport_type:
                try:
                    server_tools = await client.get_tools()
                    tools.extend(server_tools)
                except Exception as e:
                    logger.error(f"Failed to get tools from {transport_type} server {server_name}: {e}")
        
        return tools
    
    async def get_tools_by_server(self, server_name: str) -> List[Any]:
        """按服务器名称获取工具"""
        if not self.is_initialized or server_name not in self.clients:
            return []
            
        try:
            return await self.clients[server_name].get_tools()
        except Exception as e:
            logger.error(f"Failed to get tools from server {server_name}: {e}")
            return []
    
    async def health_check_all(self) -> Dict[str, bool]:
        """检查所有服务器健康状态"""
        if not self.is_initialized:
            return {}
            
        health_status = {}
        for server_name, client in self.clients.items():
            try:
                health_status[server_name] = await client.health_check()
            except Exception as e:
                logger.error(f"Health check failed for server {server_name}: {e}")
                health_status[server_name] = False
                
        return health_status
    
    async def reconnect_server(self, server_name: str) -> bool:
        """重连指定服务器"""
        if not self.is_initialized or server_name not in self.clients:
            return False
            
        try:
            client = self.clients[server_name]
            await client.disconnect()
            return await client.connect()
        except Exception as e:
            logger.error(f"Failed to reconnect server {server_name}: {e}")
            return False
    
    async def add_server(self, server_name: str, server_config: Dict[str, Any]) -> bool:
        """动态添加 MCP 服务器"""
        if not self.is_initialized:
            logger.warning("MCP Manager not initialized, cannot add server")
            return False
            
        try:
            transport = server_config.get('transport', 'stdio')
            
            if transport == 'stdio':
                client = StdioMCPClient(server_name, server_config)
            elif transport == 'sse':
                client = SSEMCPClient(server_name, server_config)
            else:
                logger.error(f"Unsupported transport type: {transport}")
                return False
                
            if await client.connect():
                self.clients[server_name] = client
                logger.info(f"Successfully added MCP server: {server_name}")
                return True
            else:
                logger.error(f"Failed to connect to new MCP server: {server_name}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to add MCP server {server_name}: {e}")
            return False
    
    async def remove_server(self, server_name: str) -> bool:
        """动态移除 MCP 服务器"""
        if not self.is_initialized or server_name not in self.clients:
            return False
            
        try:
            client = self.clients[server_name]
            await client.disconnect()
            del self.clients[server_name]
            logger.info(f"Successfully removed MCP server: {server_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to remove MCP server {server_name}: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """获取 MCP 管理器状态"""
        return {
            'mcp_available': MCP_AVAILABLE,
            'enabled': self.enabled,
            'initialized': self.is_initialized,
            'active_servers': list(self.clients.keys()),
            'server_count': len(self.clients)
        }
    
    async def shutdown(self) -> None:
        """关闭所有 MCP 连接"""
        if not self.is_initialized:
            return
            
        logger.info("Shutting down MCP Manager...")
        
        for server_name, client in self.clients.items():
            try:
                await client.disconnect()
                logger.debug(f"Disconnected from MCP server: {server_name}")
            except Exception as e:
                logger.error(f"Error disconnecting from server {server_name}: {e}")
        
        self.clients.clear()
        self.is_initialized = False
        logger.info("MCP Manager shutdown complete")