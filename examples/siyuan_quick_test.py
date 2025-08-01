#!/usr/bin/env python3
"""
SiYuan 快速测试脚本

用于快速验证 SiYuan 集成功能
"""

import os
import sys
import asyncio
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

async def quick_test():
    """快速测试 SiYuan 集成功能"""
    print("⚡ SiYuan 集成快速测试")
    print("=" * 30)
    
    # 检查环境变量
    api_url = os.getenv('SIYUAN_API_URL', 'http://127.0.0.1:6806')
    api_token = os.getenv('SIYUAN_API_TOKEN', '')
    
    print(f"🔗 API 地址: {api_url}")
    print(f"🔑 API 令牌: {'已设置' if api_token else '未设置'}")
    
    if not api_token:
        print("\n❌ 未设置 API 令牌")
        print("💡 请运行: python siyuan_config_helper.py")
        return False
    
    try:
        from HomeSystem.integrations.siyuan import SiYuanClient, SiYuanAPIError
        
        # 创建客户端
        client = SiYuanClient.from_environment()
        print("✅ 客户端创建成功")
        
        # 测试连接
        print("\n🔄 测试连接...")
        is_connected = await client.test_connection()
        
        if not is_connected:
            print("❌ 连接失败")
            return False
        
        print("✅ 连接成功")
        
        # 获取基本信息
        print("\n📊 获取基本信息...")
        
        # 健康检查
        health = await client.health_check()
        print(f"健康状态: {'正常' if health.is_healthy else '异常'}")
        print(f"响应时间: {health.response_time:.2f}ms")
        
        # 获取笔记本数量
        notebooks = await client.get_notebooks()
        print(f"笔记本数量: {len(notebooks)}")
        
        # 简单SQL查询
        result = await client.execute_sql("SELECT COUNT(*) as count FROM blocks WHERE type = 'd'")
        doc_count = result[0]['count'] if result else 0
        print(f"文档数量: {doc_count}")
        
        # 搜索测试
        if doc_count > 0:
            print("\n🔍 搜索测试...")
            search_result = await client.search_notes("", limit=1)  # 搜索所有
            print(f"搜索结果: {search_result.total_count} 条记录")
            print(f"搜索耗时: {search_result.search_time:.2f}ms")
        
        print("\n✅ 快速测试完成，集成功能正常！")
        print("🎯 现在可以运行完整示例:")
        print("   python siyuan_integration_example.py")
        
        return True
        
    except ImportError as e:
        print(f"❌ 导入失败: {e}")
        print("💡 请检查 SiYuan 集成模块是否正确安装")
        return False
    except SiYuanAPIError as e:
        print(f"❌ SiYuan API 错误: {e}")
        return False
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

def main():
    """主函数"""
    # 加载环境变量
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        print("⚠️  python-dotenv 未安装，使用系统环境变量")
    
    # 运行测试
    success = asyncio.run(quick_test())
    
    if not success:
        print("\n💡 故障排除:")
        print("1. 运行 python siyuan_config_helper.py 进行配置")
        print("2. 确保 SiYuan 正在运行且 API 已启用")
        print("3. 检查防火墙和网络连接")
        sys.exit(1)

if __name__ == "__main__":
    main()