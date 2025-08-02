#!/usr/bin/env python3
"""
Ollama模型更新示例脚本

演示如何使用Ollama模型管理工具：
1. 查询可用模型
2. 比较与配置文件的差异
3. 更新配置文件

使用方法:
    python examples/update_ollama_models.py
"""

import os
import sys
import logging

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from HomeSystem.utility.ollama import OllamaModelManager, ConfigUpdater


def setup_logging():
    """设置日志"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def main():
    """主函数"""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    print("🤖 Ollama模型管理工具演示")
    print("=" * 50)
    
    # 初始化管理器
    manager = OllamaModelManager()
    updater = ConfigUpdater()
    
    # 1. 测试连接
    print("\n1️⃣ 测试Ollama连接...")
    if not manager.test_connection():
        print(f"❌ 无法连接到Ollama服务: {manager.base_url}")
        print("请确保Ollama服务正在运行")
        return 1
    
    print(f"✅ 已连接到Ollama服务: {manager.base_url}")
    
    # 2. 获取所有模型
    print("\n2️⃣ 查询可用模型...")
    all_models_data = manager.get_available_models()
    if not all_models_data:
        print("⚠️  未找到任何模型")
        return 0
    
    print(f"发现 {len(all_models_data)} 个模型")
    
    # 3. 过滤大模型
    print("\n3️⃣ 分析模型参数...")
    large_models = manager.get_large_models(min_parameters=14.0)
    
    if not large_models:
        print("⚠️  未找到符合要求的大模型 (14B+)")
        return 0
    
    print(f"✅ 找到 {len(large_models)} 个符合要求的大模型:")
    for model in large_models:
        size_gb = model.size / (1024**3) if model.size > 0 else 0
        print(f"  • {model.display_name} ({model.parameters}, {size_gb:.1f}GB)")
        print(f"    模型名: {model.name}")
        print(f"    LLM Key: {model.key}")
    
    # 4. 比较与配置文件的差异
    print("\n4️⃣ 对比配置文件...")
    comparison = updater.compare_models(large_models)
    
    print(f"当前配置文件中有 {len(updater.get_current_ollama_models())} 个Ollama模型")
    
    if comparison['new_models']:
        print(f"\n🆕 新发现的模型 ({len(comparison['new_models'])} 个):")
        for model_name in comparison['new_models']:
            print(f"  + {model_name}")
    else:
        print("\n✅ 没有新发现的模型")
    
    if comparison['removed_models']:
        print(f"\n🗑️  配置中存在但Ollama中不存在的模型 ({len(comparison['removed_models'])} 个):")
        for model_name in comparison['removed_models']:
            print(f"  - {model_name}")
    
    if comparison['existing_models']:
        print(f"\n🔄 已存在的模型 ({len(comparison['existing_models'])} 个):")
        for model_name in comparison['existing_models']:
            print(f"  = {model_name}")
    
    # 5. 询问是否更新配置
    if comparison['new_models'] or comparison['removed_models']:
        print("\n5️⃣ 配置文件更新...")
        response = input("是否要更新配置文件? (y/n): ").lower().strip()
        
        if response in ['y', 'yes']:
            # 先执行dry run
            print("\n🧪 预览更改...")
            if updater.update_ollama_models(large_models, dry_run=True):
                # 再次确认
                response = input("确认要应用这些更改? (y/n): ").lower().strip()
                
                if response in ['y', 'yes']:
                    print("\n💾 更新配置文件...")
                    if updater.update_ollama_models(large_models, dry_run=False):
                        print("✅ 配置文件更新成功!")
                        
                        # 验证更新后的配置
                        if updater.validate_config():
                            print("✅ 配置文件验证通过")
                        else:
                            print("⚠️  配置文件验证失败，请检查")
                    else:
                        print("❌ 配置文件更新失败")
                        return 1
                else:
                    print("⚠️  更新已取消")
            else:
                print("❌ 预览失败")
                return 1
        else:
            print("⚠️  更新已跳过")
    else:
        print("\n5️⃣ 配置文件已是最新状态，无需更新")
    
    print("\n🎉 完成!")
    return 0


if __name__ == '__main__':
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠️  操作被用户取消")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 执行失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)