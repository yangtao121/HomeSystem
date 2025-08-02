# HomeSystem MCP 集成指南

本指南介绍如何在 HomeSystem 中使用 MCP (Model Context Protocol) 功能，实现与外部工具和服务的标准化集成。

## 概述

MCP 是 Anthropic 在 2024 年推出的开放协议，用于标准化语言模型如何访问工具和上下文。HomeSystem 现在原生支持 stdio 和 SSE 两种传输模式的 MCP 服务器。

### 特性

- ✅ **完全可选**: MCP 功能默认禁用，不影响现有代码
- ✅ **双传输模式**: 同时支持 stdio 和 SSE (Server-Sent Events)
- ✅ **向后兼容**: 现有 Agent 无需修改即可工作
- ✅ **动态配置**: 运行时添加/移除 MCP 服务器
- ✅ **健康监控**: 自动检测和重连机制
- ✅ **优雅降级**: MCP 故障不影响基础功能

## 安装依赖

```bash
# 安装 MCP 相关依赖
pip install langchain-mcp-adapters>=0.1.0 mcp>=1.0.0

# 或者使用项目的 requirements.txt（已包含 MCP 依赖）
pip install -r requirements.txt
```

## 配置

### 1. MCP 配置文件

MCP 配置位于 `HomeSystem/graph/config/mcp_config.yaml`：

```yaml
mcp:
  enabled: true  # 启用 MCP 功能
  
  global_settings:
    connection_timeout: 30
    reconnect_interval: 5
    max_reconnect_attempts: 3
    verbose_logging: false
  
  servers:
    # stdio 模式服务器
    filesystem:
      transport: "stdio"
      command: "npx"
      args: ["@modelcontextprotocol/server-filesystem", "/tmp/mcp-workspace"]
      enabled: true
      description: "文件系统操作工具"
      
    # SSE 模式服务器
    web_search:
      transport: "sse"
      url: "http://localhost:8000/sse"
      enabled: true
      description: "网页搜索和内容提取"
      headers:
        Authorization: "Bearer your-api-key"
```

### 2. 环境变量配置

```bash
# 可选的环境变量
export MCP_ENABLED=true
export MCP_CONFIG_PATH=/path/to/custom/mcp_config.yaml
export MCP_LOG_LEVEL=INFO
```

## 基本使用

### 1. 启用 MCP 的 ChatAgent

```python
from HomeSystem.graph.chat_agent import ChatAgent, ChatAgentConfig
import asyncio

async def main():
    # 创建配置
    config = ChatAgentConfig(
        model_name="ollama.Qwen3_30B",
        system_message="你是支持 MCP 工具的智能助理。"
    )
    
    # 创建启用 MCP 的 Agent
    agent = ChatAgent(
        config=config,
        enable_mcp=True,  # 启用 MCP
        mcp_config_path=None  # 使用默认配置
    )
    
    # 异步初始化 MCP
    success = await agent.initialize_with_mcp()
    if success:
        print(f"MCP 初始化成功，可用工具: {len(agent.mcp_tools)}")
    
    # 使用 Agent
    response = agent.chat_once("你好，有哪些工具可用？")
    print(response)
    
    # 清理资源
    await agent.shutdown_mcp()

# 运行
asyncio.run(main())
```

### 2. 自定义 BaseGraph 类

```python
from HomeSystem.graph.base_graph import BaseGraph
import asyncio

class MyCustomAgent(BaseGraph):
    def __init__(self):
        # 启用 MCP 支持
        super().__init__(enable_mcp=True)
        
    async def setup(self):
        # 初始化 MCP
        if self.mcp_enabled:
            await self.initialize_mcp_async()
            print(f"MCP 工具数量: {len(self.mcp_tools)}")
    
    def get_available_tools(self):
        # 获取 MCP 工具
        stdio_tools = self.get_mcp_tools(transport_type="stdio")
        sse_tools = self.get_mcp_tools(transport_type="sse")
        
        return {
            'stdio_tools': len(stdio_tools),
            'sse_tools': len(sse_tools),
            'total_tools': len(self.mcp_tools)
        }
```

## 高级功能

### 1. 动态添加服务器

```python
# 添加 stdio 服务器
success = await agent.add_mcp_server("my_tool", {
    "transport": "stdio",
    "command": "python",
    "args": ["my_mcp_server.py"],
    "enabled": True
})

# 添加 SSE 服务器
success = await agent.add_mcp_server("web_service", {
    "transport": "sse",
    "url": "http://localhost:9000/sse",
    "enabled": True,
    "headers": {"Authorization": "Bearer token"}
})
```

### 2. 健康检查和监控

```python
# 检查所有服务器健康状态
health_status = await agent.mcp_health_check()
print(health_status)  # {'server1': True, 'server2': False}

# 获取详细状态
status = agent.get_mcp_status()
print(status)
# {
#     'mcp_available': True,
#     'enabled': True,
#     'initialized': True,
#     'active_servers': ['filesystem', 'web_search'],
#     'server_count': 2,
#     'tools_count': 15
# }
```

### 3. 工具筛选和查询

```python
# 获取所有工具
all_tools = agent.get_mcp_tools()

# 按传输类型筛选
stdio_tools = agent.get_mcp_tools(transport_type="stdio")
sse_tools = agent.get_mcp_tools(transport_type="sse")

# 按服务器筛选
server_tools = await agent.get_mcp_tools_async(server_name="filesystem")

# 实时查询（异步）
latest_tools = await agent.get_mcp_tools_async()
```

## 传输模式详解

### stdio 模式

适用于本地工具和脚本：

```yaml
servers:
  local_tool:
    transport: "stdio"
    command: "python"
    args: ["tools/my_server.py"]
    working_directory: "/path/to/workspace"
    enabled: true
```

**特点:**
- 通过标准输入输出通信
- 适合本地工具和脚本
- 进程生命周期管理
- 自动重启机制

### SSE 模式

适用于网络服务：

```yaml
servers:
  web_service:
    transport: "sse"
    url: "http://localhost:8000/sse"
    enabled: true
    headers:
      Authorization: "Bearer your-token"
      Content-Type: "application/json"
```

**特点:**
- 基于 HTTP Server-Sent Events
- 适合远程服务和 API
- 连接池管理
- 自动重连机制

## 错误处理和故障恢复

### 1. 连接失败处理

```python
# MCP 初始化失败不会影响基础功能
agent = ChatAgent(enable_mcp=True)
success = await agent.initialize_with_mcp()

if not success:
    print("MCP 初始化失败，但 Agent 仍可正常工作")
    # Agent 会自动禁用 MCP 功能，使用标准模式
```

### 2. 服务器故障恢复

```python
# 自动重连
await agent.reconnect_server("server_name")

# 手动移除故障服务器
await agent.remove_mcp_server("problematic_server")
```

### 3. 日志和监控

```python
# 启用详细日志
import logging
logging.getLogger("HomeSystem.graph.mcp_manager").setLevel(logging.DEBUG)

# 监控 MCP 状态
status = agent.get_mcp_status()
if not status['initialized']:
    print("MCP 未正确初始化，请检查配置")
```

## 最佳实践

### 1. 开发环境配置

```yaml
environments:
  development:
    mcp:
      global_settings:
        verbose_logging: true
        connection_timeout: 10
      servers:
        local_tools:
          enabled: true
        filesystem:
          enabled: true
```

### 2. 生产环境配置

```yaml
environments:
  production:
    mcp:
      global_settings:
        verbose_logging: false
        connection_timeout: 30
        max_reconnect_attempts: 5
      servers:
        critical_service:
          enabled: true
          transport: "sse"
          url: "https://api.example.com/mcp"
```

### 3. 资源管理

```python
async def cleanup_example():
    try:
        # 你的 MCP 操作
        await agent.some_mcp_operation()
    finally:
        # 确保清理资源
        await agent.shutdown_mcp()
```

## 故障排除

### 常见问题

1. **MCP 依赖未安装**
   ```bash
   pip install langchain-mcp-adapters mcp
   ```

2. **配置文件未找到**
   ```python
   # 指定自定义配置路径
   agent = ChatAgent(enable_mcp=True, mcp_config_path="/path/to/config.yaml")
   ```

3. **服务器连接失败**
   ```python
   # 检查服务器状态
   health = await agent.mcp_health_check()
   print(health)
   ```

4. **工具未正确加载**
   ```python
   # 重新加载工具
   tools_count = await agent.reload_mcp_tools()
   print(f"重新加载了 {tools_count} 个工具")
   ```

### 调试技巧

```python
# 启用调试模式
import os
os.environ['MCP_LOG_LEVEL'] = 'DEBUG'

# 查看详细状态
status = agent.get_mcp_status()
tools_info = agent.get_available_mcp_tools_info()

print("MCP 状态:", status)
print("工具信息:", tools_info)
```

## 示例项目

查看完整示例：
- `examples/mcp_chat_agent_example.py` - 基础使用示例
- `examples/custom_mcp_agent.py` - 自定义 Agent 示例
- `examples/mcp_server_management.py` - 服务器管理示例

## 进阶主题

### 1. 自定义 MCP 服务器

```python
# 创建你自己的 MCP 服务器
# tools/my_mcp_server.py
from mcp.server import Server
from mcp.types import Tool

server = Server("my-custom-server")

@server.list_tools()
async def list_tools():
    return [
        Tool(
            name="custom_tool",
            description="我的自定义工具",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"}
                }
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, query: str):
    if name == "custom_tool":
        return f"处理查询: {query}"
```

### 2. 工具权限控制

```yaml
tool_config:
  disabled_tools:
    - "dangerous_operation"
  
  tool_permissions:
    filesystem:
      - "read"
      # - "write"  # 禁用写操作
```

### 3. 性能优化

```python
# 缓存工具列表
tools = agent.get_mcp_tools()  # 使用缓存

# 异步获取最新工具
latest_tools = await agent.get_mcp_tools_async()  # 实时查询
```

## 支持和贡献

- 问题报告: [HomeSystem Issues](https://github.com/your-repo/homesystem/issues)
- 文档更新: [MCP Integration Guide](docs/mcp-integration-guide.md)
- 示例代码: [examples/](examples/)

---

**注意**: MCP 功能是完全可选的。如果不需要外部工具集成，simply不启用 MCP 即可，不会影响任何现有功能。