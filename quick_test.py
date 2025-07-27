#!/usr/bin/env python3
"""
快速数据库连接测试脚本
用于验证数据库服务是否正常运行
"""

import os
import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def quick_test():
    """快速测试数据库连接"""
    print("🔧 快速数据库连接测试")
    print("-" * 40)
    
    # 显示当前配置
    print("数据库配置:")
    print(f"  DB_HOST: {os.getenv('DB_HOST', 'localhost')}")
    print(f"  DB_PORT: {os.getenv('DB_PORT', '5432')}")
    print(f"  DB_NAME: {os.getenv('DB_NAME', 'homesystem')}")
    print(f"  REDIS_HOST: {os.getenv('REDIS_HOST', 'localhost')}")
    print(f"  REDIS_PORT: {os.getenv('REDIS_PORT', '6379')}")
    print()
    
    # 测试导入
    try:
        from HomeSystem.integrations.database import check_database_health
        print("✅ 数据库模块导入成功")
    except ImportError as e:
        print(f"❌ 数据库模块导入失败: {e}")
        return False
    
    # 测试连接
    try:
        health = check_database_health()
        print(f"PostgreSQL: {'✅ 连接成功' if health.get('postgres_sync') else '❌ 连接失败'}")
        print(f"Redis: {'✅ 连接成功' if health.get('redis') else '❌ 连接失败'}")
        
        if health.get('postgres_sync') and health.get('redis'):
            print("\n🎉 数据库连接测试通过！")
            return True
        else:
            print("\n⚠️  部分数据库连接失败")
            return False
            
    except Exception as e:
        print(f"❌ 连接测试异常: {e}")
        return False

if __name__ == "__main__":
    # 尝试加载环境变量
    try:
        from dotenv import load_dotenv
        load_dotenv()
        print("✅ 已加载 .env 文件")
    except ImportError:
        print("⚠️  未安装 python-dotenv，使用系统环境变量")
    except Exception:
        print("⚠️  未找到 .env 文件，使用默认配置")
    
    success = quick_test()
    
    if not success:
        print("\n💡 故障排除:")
        print("1. 启动数据库服务: docker-compose up -d")
        print("2. 检查端口是否被占用")
        print("3. 验证 .env 配置")
        sys.exit(1)
    else:
        sys.exit(0)