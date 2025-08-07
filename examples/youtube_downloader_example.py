"""
YouTube视频下载工具使用示例

演示如何使用YouTubeDownloaderTool下载视频资源，包括：
- 基本视频下载
- 音频提取
- 自定义文件命名
- 批量下载
- 错误处理

适用于论文研究中的视频资源收集和管理。
"""

import sys
import asyncio
import tempfile
from pathlib import Path
from typing import List, Dict, Any

# 添加项目根目录到路径
sys.path.append(str(Path(__file__).parent.parent))

from HomeSystem.graph.tool import create_youtube_downloader_tool
from HomeSystem.graph.tool.youtube_downloader import YouTubeDownloaderInput
from loguru import logger


def basic_video_download_example():
    """基本视频下载示例"""
    print("=" * 60)
    print("基本视频下载示例")
    print("=" * 60)
    
    # 创建临时下载目录
    with tempfile.TemporaryDirectory(prefix="youtube_demo_") as temp_dir:
        print(f"下载目录: {temp_dir}")
        
        # 创建YouTube下载工具
        downloader = create_youtube_downloader_tool(temp_dir)
        
        # 示例URL (Rick Roll - 经典测试视频)
        test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        
        print(f"正在下载视频: {test_url}")
        
        try:
            # 执行下载
            result = downloader.invoke({
                "url": test_url,
                "filename": "demo_video",
                "quality": "720p",
                "format_preference": "mp4",
                "max_filesize": "50M"
            })
            
            print("下载结果:")
            print(result)
            
            # 列出下载的文件
            download_path = Path(temp_dir)
            files = list(download_path.glob("*"))
            print(f"\n下载的文件: {[f.name for f in files]}")
            
        except Exception as e:
            print(f"下载失败: {e}")
            print("注意: 这可能是由于网络问题或视频不可用")


def audio_extraction_example():
    """音频提取示例"""
    print("\n" + "=" * 60)
    print("音频提取示例")
    print("=" * 60)
    
    with tempfile.TemporaryDirectory(prefix="youtube_audio_") as temp_dir:
        print(f"下载目录: {temp_dir}")
        
        downloader = create_youtube_downloader_tool(temp_dir)
        
        # 教育性视频URL示例
        educational_url = "https://www.youtube.com/watch?v=example"
        
        print("正在提取音频...")
        
        try:
            result = downloader.invoke({
                "url": educational_url,
                "filename": "lecture_audio",
                "audio_only": True,
                "max_filesize": "100M"
            })
            
            print("音频提取结果:")
            print(result)
            
        except Exception as e:
            print(f"音频提取演示: {e}")
            print("注意: 这是演示代码，实际使用时请提供有效的URL")


def batch_download_example():
    """批量下载示例"""
    print("\n" + "=" * 60)
    print("批量下载示例")
    print("=" * 60)
    
    # 示例视频列表（实际使用时替换为真实URL）
    video_list = [
        {
            "url": "https://www.youtube.com/watch?v=example1",
            "filename": "research_video_1",
            "description": "机器学习基础"
        },
        {
            "url": "https://www.youtube.com/watch?v=example2", 
            "filename": "research_video_2",
            "description": "深度学习进阶"
        },
        {
            "url": "https://www.youtube.com/watch?v=example3",
            "filename": "research_video_3", 
            "description": "自然语言处理"
        }
    ]
    
    with tempfile.TemporaryDirectory(prefix="youtube_batch_") as temp_dir:
        print(f"批量下载目录: {temp_dir}")
        
        downloader = create_youtube_downloader_tool(temp_dir)
        
        results = []
        
        for i, video in enumerate(video_list, 1):
            print(f"\n处理视频 {i}/{len(video_list)}: {video['description']}")
            
            try:
                result = downloader.invoke({
                    "url": video["url"],
                    "filename": video["filename"],
                    "quality": "best",
                    "format_preference": "mp4",
                    "max_filesize": "200M"
                })
                
                results.append({
                    "video": video["description"],
                    "status": "success",
                    "result": result
                })
                
                print(f"✓ 下载成功: {video['description']}")
                
            except Exception as e:
                results.append({
                    "video": video["description"],
                    "status": "failed", 
                    "error": str(e)
                })
                
                print(f"✗ 下载失败: {video['description']} - {e}")
        
        # 汇总结果
        print(f"\n批量下载完成!")
        print(f"成功: {sum(1 for r in results if r['status'] == 'success')}")
        print(f"失败: {sum(1 for r in results if r['status'] == 'failed')}")


def input_validation_example():
    """输入验证示例"""
    print("\n" + "=" * 60)
    print("输入验证示例")
    print("=" * 60)
    
    test_cases = [
        {
            "name": "有效输入",
            "input": {
                "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "filename": "valid_filename",
                "quality": "720p"
            }
        },
        {
            "name": "无效URL",
            "input": {
                "url": "not_a_valid_url",
                "filename": "test"
            }
        },
        {
            "name": "不安全文件名",
            "input": {
                "url": "https://www.youtube.com/watch?v=test",
                "filename": "file<>name|with:bad*chars?/\\",
                "quality": "1080p"
            }
        },
        {
            "name": "长文件名",
            "input": {
                "url": "https://www.youtube.com/watch?v=test",
                "filename": "a" * 250  # 过长的文件名
            }
        }
    ]
    
    for test_case in test_cases:
        print(f"\n测试: {test_case['name']}")
        
        try:
            validated_input = YouTubeDownloaderInput(**test_case['input'])
            print(f"  ✓ 验证通过")
            print(f"    URL: {validated_input.url}")
            print(f"    文件名: {validated_input.filename}")
            print(f"    质量: {validated_input.quality}")
            
        except Exception as e:
            print(f"  ✗ 验证失败: {e}")


def platform_support_example():
    """平台支持检查示例"""
    print("\n" + "=" * 60)
    print("平台支持检查示例")
    print("=" * 60)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        downloader = create_youtube_downloader_tool(temp_dir)
        
        test_urls = [
            "https://www.youtube.com/watch?v=test",
            "https://youtu.be/test",
            "https://www.bilibili.com/video/test",
            "https://vimeo.com/test",
            "https://www.dailymotion.com/video/test",
            "https://www.twitch.tv/videos/test",
            "https://www.tiktok.com/@user/video/test",
            "https://unknown-platform.com/video/test"
        ]
        
        print("平台支持检查结果:")
        for url in test_urls:
            is_supported = downloader._is_supported_platform(url)
            status = "✓ 支持" if is_supported else "✗ 不支持"
            print(f"  {url:<45} {status}")


def configuration_examples():
    """配置选项示例"""
    print("\n" + "=" * 60)
    print("配置选项示例")
    print("=" * 60)
    
    configurations = [
        {
            "name": "高质量视频",
            "config": {
                "quality": "1080p",
                "format_preference": "mp4",
                "max_filesize": "500M"
            }
        },
        {
            "name": "快速下载",
            "config": {
                "quality": "480p",
                "format_preference": "webm",
                "max_filesize": "100M"
            }
        },
        {
            "name": "音频播客",
            "config": {
                "audio_only": True,
                "max_filesize": "50M"
            }
        },
        {
            "name": "最佳质量",
            "config": {
                "quality": "best",
                "format_preference": "mkv",
                "max_filesize": "1G"
            }
        }
    ]
    
    print("不同使用场景的配置建议:")
    for config in configurations:
        print(f"\n{config['name']}:")
        for key, value in config['config'].items():
            print(f"  {key}: {value}")


def error_handling_example():
    """错误处理示例"""
    print("\n" + "=" * 60)
    print("错误处理示例")
    print("=" * 60)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        downloader = create_youtube_downloader_tool(temp_dir)
        
        error_cases = [
            {
                "name": "无效视频ID",
                "url": "https://www.youtube.com/watch?v=invalid_id_12345"
            },
            {
                "name": "私有视频",
                "url": "https://www.youtube.com/watch?v=private_video"
            },
            {
                "name": "地区限制视频",
                "url": "https://www.youtube.com/watch?v=region_blocked"
            }
        ]
        
        print("错误处理测试:")
        for case in error_cases:
            print(f"\n测试: {case['name']}")
            
            try:
                result = downloader._run(
                    url=case['url'],
                    filename=f"error_test_{case['name'].replace(' ', '_').lower()}",
                    quality="720p"
                )
                print(f"  结果: {result}")
                
            except Exception as e:
                print(f"  捕获异常: {type(e).__name__}: {e}")


def integration_with_research_workflow():
    """与研究工作流集成示例"""
    print("\n" + "=" * 60)
    print("研究工作流集成示例")
    print("=" * 60)
    
    # 模拟论文分析结果中包含视频链接
    paper_analysis_result = {
        "title": "深度学习在计算机视觉中的应用",
        "video_resources": [
            {
                "url": "https://www.youtube.com/watch?v=example1",
                "description": "卷积神经网络讲解",
                "relevance": "high"
            },
            {
                "url": "https://www.youtube.com/watch?v=example2", 
                "description": "目标检测算法演示",
                "relevance": "medium"
            }
        ]
    }
    
    print("论文分析结果:")
    print(f"标题: {paper_analysis_result['title']}")
    print(f"发现视频资源: {len(paper_analysis_result['video_resources'])}个")
    
    # 为研究项目创建专门目录
    project_dir = Path(tempfile.gettempdir()) / "research_project_videos"
    project_dir.mkdir(exist_ok=True)
    
    print(f"\n项目视频目录: {project_dir}")
    
    try:
        downloader = create_youtube_downloader_tool(str(project_dir))
        
        for i, video in enumerate(paper_analysis_result['video_resources'], 1):
            print(f"\n下载视频 {i}: {video['description']}")
            print(f"相关性: {video['relevance']}")
            
            # 根据相关性确定质量设置
            quality = "1080p" if video['relevance'] == "high" else "720p"
            
            # 生成基于论文和序号的文件名
            safe_title = paper_analysis_result['title'].replace(" ", "_").replace(":", "")[:50]
            filename = f"{safe_title}_video_{i:02d}"
            
            print(f"目标文件名: {filename}")
            print(f"质量设置: {quality}")
            
            # 模拟下载（实际使用时取消注释）
            # try:
            #     result = downloader.invoke({
            #         "url": video["url"],
            #         "filename": filename,
            #         "quality": quality,
            #         "format_preference": "mp4",
            #         "max_filesize": "300M"
            #     })
            #     print(f"✓ 下载完成: {result}")
            # except Exception as e:
            #     print(f"✗ 下载失败: {e}")
            
            print("  [演示模式 - 实际下载已跳过]")
    
    finally:
        # 清理演示目录
        import shutil
        if project_dir.exists():
            shutil.rmtree(project_dir)


def main():
    """主函数 - 运行所有示例"""
    logger.info("YouTube下载工具使用示例开始")
    
    try:
        # 基础功能示例
        input_validation_example()
        platform_support_example() 
        configuration_examples()
        
        # 实际下载示例（需要网络连接）
        print("\n" + "=" * 60)
        print("实际下载示例")
        print("=" * 60)
        print("注意: 以下示例需要网络连接和有效的视频URL")
        print("在生产环境中使用前，请替换为实际的视频链接")
        
        # basic_video_download_example()
        # audio_extraction_example()
        # batch_download_example()
        # error_handling_example()
        
        # 工作流集成示例
        integration_with_research_workflow()
        
        print("\n" + "=" * 60)
        print("所有示例完成!")
        print("=" * 60)
        print("\n使用提示:")
        print("1. 实际使用时，请提供有效的视频URL")
        print("2. 确保有足够的磁盘空间和网络连接")
        print("3. 遵守相关平台的服务条款")
        print("4. 仅下载您有权使用的内容")
        
    except Exception as e:
        logger.error(f"示例运行错误: {e}")
        raise


if __name__ == "__main__":
    main()