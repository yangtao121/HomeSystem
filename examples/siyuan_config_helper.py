#!/usr/bin/env python3
"""
SiYuan 配置助手

帮助用户配置 SiYuan API 连接和测试环境
"""

import os
import sys
import json
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def create_env_template():
    """创建环境变量模板文件"""
    env_file = project_root / ".env"
    
    template = """# SiYuan 笔记 API 配置
# SiYuan Notes API Configuration

# SiYuan API 服务地址 (默认本地地址)
SIYUAN_API_URL=http://127.0.0.1:6806

# SiYuan API 访问令牌 (在 SiYuan 设置 -> API 中获取)
SIYUAN_API_TOKEN=your_api_token_here

# 可选配置
SIYUAN_TIMEOUT=30
SIYUAN_MAX_RETRIES=3
"""
    
    if env_file.exists():
        print(f"⚠️  环境变量文件已存在: {env_file}")
        response = input("是否覆盖现有文件? (y/N): ").lower().strip()
        if response != 'y':
            print("取消操作")
            return False
    
    env_file.write_text(template)
    print(f"✅ 环境变量模板已创建: {env_file}")
    print("\n📝 请编辑该文件并设置正确的 API 令牌")
    
    return True

def check_siyuan_connection():
    """检查 SiYuan 连接状态"""
    import requests
    
    api_url = os.getenv('SIYUAN_API_URL', 'http://127.0.0.1:6806')
    api_token = os.getenv('SIYUAN_API_TOKEN', '')
    
    if not api_token:
        print("❌ 未设置 API 令牌")
        return False
    
    headers = {
        'Authorization': f'token {api_token}',
        'Content-Type': 'application/json'
    }
    
    try:
        # 简单的连接测试
        response = requests.post(
            f"{api_url}/api/query/sql",
            json={'stmt': 'SELECT COUNT(*) as count FROM blocks LIMIT 1'},
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('code') == 0:
                count = data.get('data', [{}])[0].get('count', 0)
                print(f"✅ SiYuan 连接成功")
                print(f"📊 数据库中有 {count} 个块")
                return True
            else:
                print(f"❌ API 返回错误: {data.get('msg', '未知错误')}")
        else:
            print(f"❌ HTTP 错误: {response.status_code}")
            
    except requests.exceptions.ConnectionError:
        print("❌ 连接失败: 无法连接到 SiYuan 服务")
        print("💡 请确保 SiYuan 正在运行")
    except requests.exceptions.Timeout:
        print("❌ 连接超时")
    except Exception as e:
        print(f"❌ 连接测试失败: {e}")
    
    return False

def get_siyuan_info():
    """获取 SiYuan 系统信息"""
    import requests
    
    api_url = os.getenv('SIYUAN_API_URL', 'http://127.0.0.1:6806')
    api_token = os.getenv('SIYUAN_API_TOKEN', '')
    
    headers = {
        'Authorization': f'token {api_token}',
        'Content-Type': 'application/json'
    }
    
    try:
        # 获取笔记本列表
        response = requests.post(
            f"{api_url}/api/notebook/lsNotebooks",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('code') == 0:
                notebooks = data.get('data', {}).get('notebooks', [])
                
                print(f"📚 发现 {len(notebooks)} 个笔记本:")
                for i, notebook in enumerate(notebooks, 1):
                    name = notebook.get('name', '未知')
                    notebook_id = notebook.get('id', '')
                    closed = notebook.get('closed', False)
                    status = "已关闭" if closed else "已打开"
                    print(f"   {i}. {name} (ID: {notebook_id[:8]}..., 状态: {status})")
                
                # 获取统计信息
                stats_queries = [
                    ("文档总数", "SELECT COUNT(*) as count FROM blocks WHERE type = 'd'"),
                    ("段落总数", "SELECT COUNT(*) as count FROM blocks WHERE type = 'p'"),
                    ("最近更新", "SELECT MAX(updated) as last_updated FROM blocks")
                ]
                
                print(f"\n📊 数据库统计:")
                for name, sql in stats_queries:
                    try:
                        response = requests.post(
                            f"{api_url}/api/query/sql",
                            json={'stmt': sql},
                            headers=headers,
                            timeout=5
                        )
                        
                        if response.status_code == 200:
                            result = response.json()
                            if result.get('code') == 0:
                                data_row = result.get('data', [{}])[0]
                                value = list(data_row.values())[0] if data_row else 0
                                
                                # 格式化时间戳
                                if name == "最近更新" and value:
                                    try:
                                        from datetime import datetime
                                        if len(str(value)) == 14:
                                            dt = datetime.strptime(str(value), '%Y%m%d%H%M%S')
                                            value = dt.strftime('%Y-%m-%d %H:%M:%S')
                                    except:
                                        pass
                                
                                print(f"   {name}: {value}")
                    except:
                        print(f"   {name}: 获取失败")
                
                return True
                
    except Exception as e:
        print(f"❌ 获取系统信息失败: {e}")
    
    return False

def setup_wizard():
    """设置向导"""
    print("🧙‍♂️ SiYuan 集成设置向导")
    print("=" * 40)
    
    # 步骤1: 检查 .env 文件
    env_file = project_root / ".env"
    if not env_file.exists():
        print("📝 步骤1: 创建环境配置文件")
        create_env_template()
        print("\n⏸️  请先编辑 .env 文件设置 API 令牌，然后重新运行此脚本")
        return
    
    # 步骤2: 加载环境变量
    print("📝 步骤2: 加载环境配置")
    try:
        from dotenv import load_dotenv
        load_dotenv()
        print("✅ 环境变量已加载")
    except ImportError:
        print("⚠️  python-dotenv 未安装，使用系统环境变量")
    
    # 步骤3: 测试连接
    print("\n📝 步骤3: 测试连接")
    if not check_siyuan_connection():
        print("\n💡 连接失败排查:")
        print("1. 确保 SiYuan 正在运行")
        print("2. 在 SiYuan 中启用 API: 设置 -> 关于 -> API")
        print("3. 检查 API 令牌是否正确")
        print("4. 检查端口是否正确 (默认 6806)")
        return
    
    # 步骤4: 获取系统信息
    print("\n📝 步骤4: 获取系统信息")
    get_siyuan_info()
    
    # 步骤5: 运行示例
    print("\n📝 步骤5: 运行示例")
    print("✅ 设置完成！现在可以运行以下命令测试集成:")
    print(f"   python {Path(__file__).parent}/siyuan_integration_example.py")

def main():
    """主函数"""
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "template":
            create_env_template()
        elif command == "test":
            # 加载环境变量
            try:
                from dotenv import load_dotenv
                load_dotenv()
            except ImportError:
                pass
            
            print("🔍 测试 SiYuan 连接...")
            check_siyuan_connection()
        elif command == "info":
            # 加载环境变量
            try:
                from dotenv import load_dotenv
                load_dotenv()
            except ImportError:
                pass
            
            print("📊 获取 SiYuan 信息...")
            get_siyuan_info()
        elif command == "wizard":
            setup_wizard()
        else:
            print(f"❌ 未知命令: {command}")
            print("可用命令: template, test, info, wizard")
    else:
        # 默认运行设置向导
        setup_wizard()

if __name__ == "__main__":
    main()