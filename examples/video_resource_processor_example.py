#!/usr/bin/env python3
"""
视频资源处理器使用示例

演示如何使用VideoResourceProcessor从网页批量提取、下载和分析视频，
并使用LLM生成精炼标题和专业总结，自动重命名文件。
"""

import os
import sys
import asyncio
import json
from pathlib import Path

# 添加HomeSystem路径到sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
homesystem_root = os.path.join(current_dir, '..')
sys.path.append(homesystem_root)

from HomeSystem.graph.tool.video_resource_processor import VideoResourceProcessor


def print_separator(title: str):
    """打印分隔符"""
    print(f"\n{'='*60}")
    print(f" {title}")
    print(f"{'='*60}")


def print_video_result(video: dict, index: int):
    """格式化打印单个视频结果"""
    print(f"\n📹 视频 {index + 1}:")
    print(f"   标题: {video['title']}")
    print(f"   源URL: {video['source_url']}")
    print(f"   本地路径: {video['local_path']}")
    print(f"   文件大小: {video['file_size_mb']} MB")
    print(f"   分析总结:")
    # 缩进显示总结内容
    summary_lines = video['analysis_summary'].split('\n')
    for line in summary_lines[:5]:  # 只显示前5行
        print(f"      {line}")
    if len(summary_lines) > 5:
        print(f"      ... (还有{len(summary_lines) - 5}行)")


async def example_basic_usage():
    """基础使用示例"""
    print_separator("基础使用示例")
    
    # 创建下载目录
    base_folder = Path("data/test")
    base_folder.mkdir(parents=True, exist_ok=True)
    
    print(f"📁 视频将保存到: {base_folder.absolute()}")
    
    # 创建视频资源处理器
    processor = VideoResourceProcessor(
        base_folder_path=str(base_folder),
        summarization_model="ollama.Qwen3_30B"  # 使用本地Qwen模型
    )
    
    # 测试URL - 妈妈厨房网站
    test_url = "https://svl.stanford.edu/projects/relmogen/"
    
    print(f"🌐 处理页面: {test_url}")
    print("📋 配置参数:")
    print("   - 下载质量: 720p")
    print("   - 最大视频数: 3")
    print("   - LLM模型: Qwen3_30B")
    
    try:
        # 执行处理
        print("\n🚀 开始处理...")
        result_json = processor._run(
            url=test_url,
            download_quality="720p",
            max_videos=3
        )
        
        # 解析结果
        result = json.loads(result_json)
        
        # 显示处理结果
        print_separator("处理结果")
        print(f"✅ 成功处理: {result['processed_count']} 个视频")
        print(f"📊 总大小: {result['total_size_mb']} MB")
        print(f"❌ 失败数量: {len(result['failed_downloads'])} 个")
        
        if result['failed_downloads']:
            print("失败的视频:")
            for failed_url in result['failed_downloads']:
                print(f"   - {failed_url}")
        
        # 显示每个视频的详细信息
        if result['videos']:
            print_separator("视频详情")
            for i, video in enumerate(result['videos']):
                print_video_result(video, i)
        
        print(f"\n📝 处理摘要: {result['processing_summary']}")
        
    except Exception as e:
        print(f"❌ 处理失败: {e}")
        import traceback
        traceback.print_exc()


def example_advanced_configuration():
    """高级配置示例"""
    print_separator("高级配置示例")
    
    base_folder = Path("./video_advanced_demo")
    base_folder.mkdir(exist_ok=True)
    
    # 使用不同的LLM模型
    processor = VideoResourceProcessor(
        base_folder_path=str(base_folder),
        summarization_model="deepseek.DeepSeek_V3"  # 使用DeepSeek模型
    )
    
    # 料理网站示例
    cooking_urls = [
        "https://momakitchen.github.io/",
        "https://momakitchen.github.io/recipes/",
        "https://momakitchen.github.io/tutorials/"
    ]
    
    print("🍳 处理料理类视频...")
    
    for url in cooking_urls[:1]:  # 只处理第一个作为示例
        print(f"\n🌐 处理页面: {url}")
        
        try:
            result_json = processor._run(
                url=url,
                download_quality="1080p",  # 更高质量
                max_videos=2  # 限制数量
            )
            
            result = json.loads(result_json)
            print(f"✅ 从该页面成功处理: {result['processed_count']} 个视频")
            
        except Exception as e:
            print(f"❌ 处理页面失败: {e}")


def example_custom_analysis():
    """自定义分析示例"""
    print_separator("自定义分析示例")
    
    base_folder = Path("./video_custom_demo")
    base_folder.mkdir(exist_ok=True)
    
    # 使用自定义分析参数
    processor = VideoResourceProcessor(
        base_folder_path=str(base_folder),
        summarization_model="ollama.Qwen3_30B"
    )
    
    print("🔍 自定义分析配置:")
    print("   - 高质量下载 (1080p)")
    print("   - 详细内容分析")
    print("   - 专业学术总结")
    
    # 料理教程网站
    cooking_url = "https://momakitchen.github.io/"
    
    try:
        result_json = processor._run(
            url=cooking_url,
            download_quality="1080p",
            max_videos=1
        )
        
        result = json.loads(result_json)
        
        if result['videos']:
            video = result['videos'][0]
            print("\n📊 详细分析结果:")
            print(f"精炼标题: {video['title']}")
            print(f"完整总结:\n{video['analysis_summary']}")
            
    except Exception as e:
        print(f"❌ 自定义分析失败: {e}")


def example_batch_processing():
    """批量处理示例"""
    print_separator("批量处理示例")
    
    base_folder = Path("./video_batch_demo")
    base_folder.mkdir(exist_ok=True)
    
    processor = VideoResourceProcessor(
        base_folder_path=str(base_folder),
        summarization_model="ollama.Qwen3_30B"
    )
    
    # 多个页面批量处理
    batch_urls = [
        "https://momakitchen.github.io/",
        "https://momakitchen.github.io/recipes/",
        "https://momakitchen.github.io/about/"
    ]
    
    all_results = []
    
    print(f"🔄 批量处理 {len(batch_urls)} 个页面...")
    
    for i, url in enumerate(batch_urls, 1):
        print(f"\n📄 处理页面 {i}/{len(batch_urls)}: {url}")
        
        try:
            result_json = processor._run(
                url=url,
                download_quality="720p",
                max_videos=2
            )
            
            result = json.loads(result_json)
            all_results.append(result)
            
            print(f"   ✅ 成功: {result['processed_count']} 个视频")
            
        except Exception as e:
            print(f"   ❌ 失败: {e}")
            all_results.append({"processed_count": 0, "videos": [], "failed_downloads": []})
    
    # 汇总统计
    total_videos = sum(r['processed_count'] for r in all_results)
    total_size = sum(r.get('total_size_mb', 0) for r in all_results)
    total_failures = sum(len(r['failed_downloads']) for r in all_results)
    
    print(f"\n📈 批量处理统计:")
    print(f"   总视频数: {total_videos}")
    print(f"   总大小: {total_size:.1f} MB")
    print(f"   失败数: {total_failures}")


def example_file_management():
    """文件管理示例"""
    print_separator("文件管理和重命名示例")
    
    base_folder = Path("./video_management_demo")
    base_folder.mkdir(exist_ok=True)
    
    processor = VideoResourceProcessor(
        base_folder_path=str(base_folder),
        summarization_model="ollama.Qwen3_30B"
    )
    
    print("📁 文件管理功能演示:")
    print("   - 自动根据LLM生成的标题重命名文件")
    print("   - 处理文件名冲突")
    print("   - 生成安全的文件名")
    
    # 测试重命名功能
    test_titles = [
        "日式料理制作教程：传统家庭烹饪技巧",
        "妈妈厨房秘籍：从基础调料到高级料理",
        "料理视频精选：简单美味的家常菜制作"
    ]
    
    print("\n🔤 测试文件名生成:")
    for title in test_titles:
        safe_name = processor._generate_safe_filename(title)
        print(f"   '{title}' -> '{safe_name}'")
    
    print("\n📝 重命名功能说明:")
    print("   - 自动替换特殊字符为下划线")
    print("   - 限制文件名长度在100字符以内")
    print("   - 处理重复文件名(添加数字后缀)")
    print("   - 保持原始文件扩展名")


def print_usage_tips():
    """打印使用建议"""
    print_separator("使用建议和最佳实践")
    
    tips = [
        "🔧 配置建议:",
        "   • 对于学习内容，建议使用720p质量平衡质量和存储空间",
        "   • 首次使用时建议max_videos=1-3，避免下载过多内容",
        "   • 确保有足够的磁盘空间(每个视频可能几百MB到几GB)",
        "",
        "🤖 LLM模型选择:",
        "   • Qwen3_30B: 本地运行，隐私性好，中文支持佳",
        "   • DeepSeek_V3: 云端API，处理速度快，多语言支持",
        "",
        "📁 文件管理:",
        "   • 视频会自动重命名为LLM生成的精炼标题",
        "   • 支持中文文件名，便于管理和查找",
        "   • 自动处理文件名冲突",
        "",
        "⚠️ 注意事项:",
        "   • 确保网络连接稳定",
        "   • 遵守视频网站的使用条款",
        "   • 仅用于个人学习和研究目的",
        "   • 大量下载前请检查磁盘空间"
    ]
    
    for tip in tips:
        print(tip)


async def main():
    """主函数"""
    print("🎬 视频资源处理器使用示例")
    print("演示批量视频提取、下载、分析和智能重命名功能")
    print("测试网站: https://momakitchen.github.io/")
    
    # 检查依赖
    try:
        from HomeSystem.graph.llm_factory import llm_factory
        print("✅ LLM工厂模块加载成功")
    except ImportError as e:
        print(f"❌ 依赖检查失败: {e}")
        print("请确保安装了所有必要的依赖包")
        return
    
    # 直接运行基础使用示例
    print("\n🚀 运行基础使用示例...")
    
    try:
        await example_basic_usage()
        print("✅ 基础示例运行完成")
    except Exception as e:
        print(f"❌ 基础示例运行出错: {e}")
        import traceback
        traceback.print_exc()
    
    # 显示使用建议
    print_usage_tips()
    
    print(f"\n✨ 示例运行完成")
    print("💡 提示: 查看生成的demo目录了解输出结果")


if __name__ == "__main__":
    # 运行主程序
    asyncio.run(main())