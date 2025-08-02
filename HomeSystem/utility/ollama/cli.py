"""
Ollama模型管理命令行工具

提供命令行接口来管理Ollama模型和更新配置文件
"""

import os
import sys
import argparse
import logging
from typing import Optional

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from HomeSystem.utility.ollama import OllamaModelManager, ConfigUpdater


def setup_logging(verbose: bool = False):
    """设置日志"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def cmd_list_models(args):
    """列出可用模型"""
    manager = OllamaModelManager(args.base_url)
    
    # 测试连接
    if not manager.test_connection():
        print(f"❌ 无法连接到Ollama服务: {manager.base_url}")
        return 1
    
    print(f"✅ 已连接到Ollama服务: {manager.base_url}")
    
    # 获取所有模型
    all_models = manager.get_available_models()
    if not all_models:
        print("⚠️  未找到任何模型")
        return 0
    
    print(f"\n📊 发现 {len(all_models)} 个模型:")
    
    # 解析并分类模型
    large_models = []
    small_models = []
    
    for model_data in all_models:
        model_info = manager.parse_model_info(model_data)
        if model_info:
            param_value = manager._parameter_to_float(model_info.parameters)
            if param_value >= args.min_params:
                large_models.append(model_info)
            else:
                small_models.append(model_info)
    
    if large_models:
        print(f"\n🎯 符合要求的大模型 ({args.min_params}B+):")
        for model in large_models:
            size_gb = model.size / (1024**3) if model.size > 0 else 0
            print(f"  ✓ {model.name}")
            print(f"    显示名称: {model.display_name}")
            print(f"    参数规模: {model.parameters}")
            print(f"    模型大小: {size_gb:.1f}GB")
            print(f"    LLM Key: {model.key}")
            print(f"    描述: {model.description}")
            print()
    
    if small_models and args.show_all:
        print(f"\n📝 其他模型 (< {args.min_params}B):")
        for model in small_models:
            size_gb = model.size / (1024**3) if model.size > 0 else 0
            print(f"  - {model.name} ({model.parameters}, {size_gb:.1f}GB)")
    
    if not args.show_all and small_models:
        print(f"\n💡 还有 {len(small_models)} 个小于 {args.min_params}B 的模型 (使用 --show-all 查看)")
    
    return 0


def cmd_compare_config(args):
    """比较当前模型与配置文件"""
    manager = OllamaModelManager(args.base_url)
    updater = ConfigUpdater(args.config)
    
    # 测试连接
    if not manager.test_connection():
        print(f"❌ 无法连接到Ollama服务: {manager.base_url}")
        return 1
    
    # 获取当前大模型
    current_models = manager.get_large_models(args.min_params)
    if not current_models:
        print("⚠️  未找到任何符合要求的大模型")
        return 0
    
    # 比较模型
    comparison = updater.compare_models(current_models)
    
    print(f"📊 模型对比结果:")
    print(f"  当前Ollama中的模型: {len(current_models)} 个")
    print(f"  配置文件中的模型: {len(updater.get_current_ollama_models())} 个")
    
    if comparison['new_models']:
        print(f"\n🆕 新发现的模型 ({len(comparison['new_models'])} 个):")
        for model_name in comparison['new_models']:
            print(f"  + {model_name}")
    
    if comparison['removed_models']:
        print(f"\n🗑️  配置中存在但Ollama中不存在的模型 ({len(comparison['removed_models'])} 个):")
        for model_name in comparison['removed_models']:
            print(f"  - {model_name}")
    
    if comparison['existing_models']:
        print(f"\n✅ 已存在的模型 ({len(comparison['existing_models'])} 个):")
        for model_name in comparison['existing_models']:
            print(f"  = {model_name}")
    
    return 0


def cmd_update_config(args):
    """更新配置文件"""
    manager = OllamaModelManager(args.base_url)
    updater = ConfigUpdater(args.config)
    
    # 测试连接
    if not manager.test_connection():
        print(f"❌ 无法连接到Ollama服务: {manager.base_url}")
        return 1
    
    # 验证配置文件
    if not updater.validate_config():
        print("❌ 配置文件验证失败")
        return 1
    
    # 获取当前大模型
    current_models = manager.get_large_models(args.min_params)
    if not current_models:
        print("⚠️  未找到任何符合要求的大模型")
        return 0
    
    print(f"🔍 发现 {len(current_models)} 个符合要求的模型")
    
    # 执行更新
    if args.dry_run:
        print("\n🧪 DRY RUN 模式 - 仅预览更改，不会实际修改文件")
    
    success = updater.update_ollama_models(current_models, dry_run=args.dry_run)
    
    if success:
        if args.dry_run:
            print("✅ DRY RUN 完成")
        else:
            print("✅ 配置文件更新成功")
            
            # 验证更新后的配置
            if updater.validate_config():
                print("✅ 更新后的配置文件验证通过")
            else:
                print("⚠️  更新后的配置文件验证失败，请检查")
                return 1
    else:
        print("❌ 配置文件更新失败")
        return 1
    
    return 0


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="Ollama模型管理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 列出所有3B+参数的模型（默认）
  python -m HomeSystem.utility.ollama.cli list

  # 列出所有模型（包括小模型）
  python -m HomeSystem.utility.ollama.cli list --show-all

  # 比较当前模型与配置文件
  python -m HomeSystem.utility.ollama.cli compare

  # 预览配置更新（不实际修改）
  python -m HomeSystem.utility.ollama.cli update --dry-run

  # 更新配置文件
  python -m HomeSystem.utility.ollama.cli update

  # 使用自定义Ollama地址
  python -m HomeSystem.utility.ollama.cli list --base-url http://192.168.1.100:11434
        """
    )
    
    # 全局参数
    parser.add_argument(
        '--base-url', 
        default=None,
        help='Ollama服务地址 (默认: $OLLAMA_BASE_URL 或 http://localhost:11434)'
    )
    parser.add_argument(
        '--config',
        default=None,
        help='配置文件路径 (默认: 项目中的llm_providers.yaml)'
    )
    parser.add_argument(
        '--min-params',
        type=float,
        default=3.0,
        help='最小参数量要求 (默认: 3.0B)'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='详细输出'
    )
    
    # 子命令
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # list命令
    parser_list = subparsers.add_parser('list', help='列出可用模型')
    parser_list.add_argument(
        '--show-all',
        action='store_true',
        help='显示所有模型，包括小于参数要求的模型'
    )
    
    # compare命令
    parser_compare = subparsers.add_parser('compare', help='比较当前模型与配置文件')
    
    # update命令
    parser_update = subparsers.add_parser('update', help='更新配置文件')
    parser_update.add_argument(
        '--dry-run',
        action='store_true',
        help='预览模式，不实际修改文件'
    )
    
    # 解析参数
    args = parser.parse_args()
    
    # 设置日志
    setup_logging(args.verbose)
    
    # 如果没有指定命令，显示帮助
    if not args.command:
        parser.print_help()
        return 1
    
    # 执行相应命令
    try:
        if args.command == 'list':
            return cmd_list_models(args)
        elif args.command == 'compare':
            return cmd_compare_config(args)
        elif args.command == 'update':
            return cmd_update_config(args)
        else:
            parser.print_help()
            return 1
    except KeyboardInterrupt:
        print("\n⚠️  操作被用户取消")
        return 1
    except Exception as e:
        print(f"❌ 执行失败: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())