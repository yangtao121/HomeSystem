#!/usr/bin/env python3
"""
MCP ChatAgent 使用示例

展示如何在 HomeSystem 中使用 MCP 功能：
1. 启用 MCP 的 ChatAgent
2. 动态添加 MCP 服务器
3. 查看可用工具
4. 健康检查

运行前请确保：
1. 已安装 MCP 相关依赖: pip install langchain-mcp-adapters mcp
2. 根据需要配置 HomeSystem/graph/config/mcp_config.yaml
"""

import asyncio
import sys
import os
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from HomeSystem.graph.chat_agent import ChatAgent, ChatAgentConfig
from loguru import logger


async def main():
    """MCP ChatAgent 使用示例"""
    
    logger.info("=== HomeSystem MCP ChatAgent 示例 ===")
    
    # 1. 创建启用 MCP 的 ChatAgent
    logger.info("1. 创建启用 MCP 的 ChatAgent...")
    
    config = ChatAgentConfig(
        model_name="ollama.DeepSeek_R1_14B",
        system_message="你是一个支持 MCP 工具的智能助理。可以帮助用户使用各种外部工具和服务。",
        memory_enabled=True
    )
    
    # 启用 MCP 功能
    agent = ChatAgent(
        config=config,
        enable_mcp=True,  # 启用 MCP
        mcp_config_path=None  # 使用默认配置路径
    )
    
    # 2. 异步初始化 MCP
    logger.info("2. 初始化 MCP 连接...")
    mcp_success = await agent.initialize_with_mcp()
    
    if mcp_success:
        logger.info("✅ MCP 初始化成功")
    else:
        logger.warning("⚠️ MCP 初始化失败或未启用，将使用标准模式")
    
    # 3. 查看 MCP 状态
    logger.info("3. 查看 MCP 状态...")
    mcp_status = agent.get_mcp_status()
    logger.info(f"MCP 状态: {mcp_status}")
    
    # 4. 查看可用工具信息
    logger.info("4. 查看可用 MCP 工具...")
    tools_info = agent.get_available_mcp_tools_info()
    logger.info(f"工具信息: {tools_info}")
    
    if agent.mcp_enabled:
        # 5. 健康检查
        logger.info("5. 执行 MCP 服务器健康检查...")
        health_message = await agent.check_mcp_health_interactive()
        logger.info(f"健康检查结果: {health_message}")
        
        # 6. 动态添加服务器示例（如果需要）
        logger.info("6. 动态添加服务器示例...")
        
        # 示例：添加一个文件系统工具服务器（stdio 模式）
        add_result = await agent.add_mcp_server_interactive(
            server_name="example_filesystem",
            transport="stdio",
            command="echo",  # 这是一个示例命令，实际应该是有效的 MCP 服务器
            args=["Hello MCP"],
            description="示例文件系统工具"
        )
        logger.info(f"添加服务器结果: {add_result}")
        
        # 示例：添加一个 Web 服务器（SSE 模式）
        # add_result = await agent.add_mcp_server_interactive(
        #     server_name="example_web_service",
        #     transport="sse",
        #     url="http://localhost:8000/sse",
        #     description="示例 Web 服务工具"
        # )
        # logger.info(f"添加 Web 服务器结果: {add_result}")
    
    # 7. 交互式聊天示例
    logger.info("7. 开始交互式聊天...")
    logger.info("提示：输入 'mcp-status' 查看 MCP 状态")
    logger.info("提示：输入 'mcp-tools' 查看可用工具")
    logger.info("提示：输入 'mcp-health' 进行健康检查")
    logger.info("提示：输入 'exit' 退出")
    
    while True:
        try:
            user_input = input("\n用户: ").strip()
            
            if user_input.lower() in ['exit', 'quit', 'q']:
                break
            elif user_input.lower() == 'mcp-status':
                status = agent.get_mcp_status()
                print(f"助理: MCP 状态信息：{status}")
                continue
            elif user_input.lower() == 'mcp-tools':
                tools_info = agent.get_available_mcp_tools_info()
                print(f"助理: MCP 工具信息：{tools_info}")
                continue
            elif user_input.lower() == 'mcp-health':
                if agent.mcp_enabled:
                    health_msg = await agent.check_mcp_health_interactive()
                    print(f"助理: {health_msg}")
                else:
                    print("助理: MCP 功能未启用")
                continue
            
            if not user_input:
                continue
            
            # 正常聊天
            response = agent.chat_once(user_input)
            print(f"助理: {response}")
            
        except KeyboardInterrupt:
            logger.info("用户中断，退出程序")
            break
        except Exception as e:
            logger.error(f"聊天过程中发生错误: {e}")
    
    # 8. 清理资源
    logger.info("8. 清理资源...")
    if agent.mcp_enabled:
        await agent.shutdown_mcp()
    
    logger.info("=== 示例完成 ===")


def run_example():
    """运行示例的便利函数"""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("用户中断程序")
    except Exception as e:
        logger.error(f"程序执行出错: {e}")
        raise


if __name__ == "__main__":
    # 配置日志级别
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    
    run_example()