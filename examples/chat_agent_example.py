#!/usr/bin/env python3
"""
ChatAgent使用示例
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from HomeSystem.graph.chat_agent import ChatAgent, ChatAgentConfig

def main():
    """主函数 - 演示ChatAgent的基本用法"""
    
    # 方法1: 使用默认配置
    print("=" * 60)
    print("方法1: 使用默认配置创建聊天代理")
    print("=" * 60)
    
    agent = ChatAgent()
    
    # 查看配置信息
    config = agent.get_config()
    print(f"模型: {config.model_name}")
    print(f"系统消息: {config.system_message}")
    print(f"记忆功能: {'启用' if config.memory_enabled else '禁用'}")
    
    # 单次对话测试
    print("\n测试单次对话:")
    response = agent.chat_once("你好，请介绍一下你自己")
    print(f"AI回复: {response}")
    
    # 查看对话统计
    stats = agent.get_conversation_stats()
    print(f"\n对话统计: {stats}")
    
    # 方法2: 使用自定义配置
    print("\n" + "=" * 60)
    print("方法2: 使用自定义配置创建聊天代理")
    print("=" * 60)
    
    custom_config = ChatAgentConfig(
        model_name="ollama.Qwen3_30B",  # 可根据实际可用模型调整
        system_message="你是一个专业的技术助理，专门帮助用户解决编程和技术问题。请用中文回答，保持专业和友善。",
        memory_enabled=True,
        conversation_context_limit=20
    )
    
    # 保存配置到文件
    config_path = "/tmp/chat_agent_config.json"
    custom_config.save_to_file(config_path)
    print(f"配置已保存到: {config_path}")
    
    # 从配置文件创建代理
    agent_custom = ChatAgent(config_path=config_path)
    
    print("\n测试自定义配置的对话:")
    response = agent_custom.chat_once("我想学习Python编程，你能给我一些建议吗？")
    print(f"AI回复: {response}")
    
    # 方法3: 动态更新配置
    print("\n" + "=" * 60)
    print("方法3: 动态更新配置")
    print("=" * 60)
    
    agent_custom.update_config(
        system_message="你现在是一个幽默风趣的聊天伙伴，请用轻松愉快的语调与用户交流。"
    )
    
    print("测试更新配置后的对话:")
    response = agent_custom.chat_once("今天天气不错啊")
    print(f"AI回复: {response}")
    
    # 方法4: 交互式聊天（可选）
    print("\n" + "=" * 60)
    print("方法4: 交互式聊天模式")
    print("输入 'skip' 跳过交互模式，输入其他内容开始聊天")
    print("=" * 60)
    
    user_choice = input("是否进入交互模式? (输入'skip'跳过): ").strip()
    
    if user_choice.lower() != 'skip':
        print("进入交互式聊天模式，输入 'exit' 退出")
        agent_custom.chat()  # 使用BaseGraph的交互式聊天方法
    
    print("\n程序结束")

if __name__ == "__main__":
    main()