#!/usr/bin/env python3
"""
Video Link Extractor Example

This example demonstrates how to use the VideoLinkExtractorTool to extract video links
from web pages including embedded videos, HTML5 video tags, and direct video file links.

The tool can:
1. Extract embedded videos from iframes (YouTube, Bilibili, Vimeo, etc.)
2. Find HTML5 video elements with their sources  
3. Detect direct video file links (.mp4, .webm, etc.)
4. Extract video titles when possible, showing "unknown" when not found
5. Return "没有视频" when no videos are found
"""

import sys
from pathlib import Path
import json

# Add the project root to the Python path
sys.path.append(str(Path(__file__).parent.parent))

from HomeSystem.graph.tool import create_video_link_extractor_tool


def basic_webpage_video_extraction():
    """Basic example of extracting videos from a webpage URL"""
    print("=" * 60)
    print("Basic Webpage Video Extraction Example")
    print("=" * 60)
    
    # Create the video link extractor tool
    tool = create_video_link_extractor_tool()
    
    # Example webpage URL - replace with actual URL for testing
    test_url = "https://general-navigation-models.github.io"
    
    print(f"提取URL中的视频: {test_url}")
    print("正在分析网页...")
    
    # Extract videos from the webpage
    result = tool._run(
        url=test_url,
        include_embeds=True,
        include_direct=True,
        include_video_tags=True
    )
    
    # Display results
    print(f"\n提取状态: {result['status']}")
    print(f"状态消息: {result['message']}")
    print(f"找到视频数量: {result['total_count']}")
    
    if result['platforms_found']:
        print(f"涉及平台: {result['platforms_found']}")
    
    if result['videos']:
        print("\n检测到的视频:")
        for i, video in enumerate(result['videos'], 1):
            print(f"  {i}. 标题: {video['title']}")
            print(f"     平台: {video['platform']}")
            print(f"     来源类型: {video['source_type']}")
            print(f"     URL: {video['video_url']}")
            print()
    
    return result


def iframe_embed_extraction_example():
    """Example showing extraction of embedded videos from iframes"""
    print("=" * 60)
    print("Iframe Embedded Video Extraction")
    print("=" * 60)
    
    tool = create_video_link_extractor_tool()
    
    # Test URL that contains embedded videos - replace with real URL
    test_url = "https://general-navigation-models.github.io"
    
    print(f"从网页提取嵌入式视频: {test_url}")
    
    # Extract only embedded videos
    result = tool._run(
        url=test_url,
        include_embeds=True,      # Include iframe embeds
        include_direct=False,     # Skip direct links
        include_video_tags=False  # Skip video tags
    )
    
    print(f"\n提取结果: {result['message']}")
    
    if result['videos']:
        print(f"\n找到 {result['total_count']} 个嵌入式视频:")
        for i, video in enumerate(result['videos'], 1):
            print(f"  视频 {i}:")
            print(f"    标题: {video['title']}")
            print(f"    平台: {video['platform']}")
            print(f"    嵌入URL: {video['video_url']}")
            print()
    
    return result


def html5_video_extraction_example():
    """Example showing extraction of HTML5 video elements"""
    print("=" * 60)
    print("HTML5 Video Tag Extraction")
    print("=" * 60)
    
    tool = create_video_link_extractor_tool()
    
    # Test URL with HTML5 video elements - replace with real URL
    test_url = "https://general-navigation-models.github.io"
    
    print(f"从网页提取HTML5视频: {test_url}")
    
    # Extract only HTML5 video tags
    result = tool._run(
        url=test_url,
        include_embeds=False,     # Skip embeds
        include_direct=False,     # Skip direct links
        include_video_tags=True   # Include video tags only
    )
    
    print(f"\n提取结果: {result['message']}")
    
    if result['videos']:
        print(f"\n找到 {result['total_count']} 个HTML5视频:")
        for i, video in enumerate(result['videos'], 1):
            print(f"  视频 {i}:")
            print(f"    标题: {video['title']}")
            print(f"    视频URL: {video['video_url']}")
            print(f"    来源类型: {video['source_type']}")
            print()
    
    return result


def direct_video_links_example():
    """Example showing extraction of direct video file links"""
    print("=" * 60)
    print("Direct Video File Links Extraction")
    print("=" * 60)
    
    tool = create_video_link_extractor_tool()
    
    # Test URL with direct video file links - replace with real URL
    test_url = "https://general-navigation-models.github.io"
    
    print(f"从网页提取直接视频文件链接: {test_url}")
    
    # Extract only direct video file links
    result = tool._run(
        url=test_url,
        include_embeds=False,     # Skip embeds
        include_direct=True,      # Include direct links only
        include_video_tags=False  # Skip video tags
    )
    
    print(f"\n提取结果: {result['message']}")
    
    if result['videos']:
        print(f"\n找到 {result['total_count']} 个直接视频文件:")
        for i, video in enumerate(result['videos'], 1):
            print(f"  文件 {i}:")
            print(f"    标题: {video['title']}")
            print(f"    文件URL: {video['video_url']}")
            print(f"    来源类型: {video['source_type']}")
            print()
    
    return result


def comprehensive_extraction_example():
    """Comprehensive example extracting all types of videos"""
    print("=" * 60)
    print("Comprehensive Video Extraction")
    print("=" * 60)
    
    tool = create_video_link_extractor_tool()
    
    # Test URL with mixed video content - replace with real URL
    test_url = "https://general-navigation-models.github.io"
    
    print(f"全面提取网页中的所有视频: {test_url}")
    print("包括：嵌入式视频、HTML5视频标签、直接视频文件链接")
    
    # Extract all types of videos
    result = tool._run(
        url=test_url,
        include_embeds=True,      # Include all types
        include_direct=True,
        include_video_tags=True
    )
    
    print(f"\n提取结果: {result['message']}")
    print(f"总共找到: {result['total_count']} 个视频")
    
    if result['platforms_found']:
        print(f"涉及平台: {', '.join(result['platforms_found'])}")
    
    if result['videos']:
        # Group by source type
        by_source_type = {}
        for video in result['videos']:
            source_type = video['source_type']
            if source_type not in by_source_type:
                by_source_type[source_type] = []
            by_source_type[source_type].append(video)
        
        print(f"\n按来源类型分组:")
        for source_type, videos in by_source_type.items():
            print(f"\n  {source_type.upper()} ({len(videos)} 个):")
            for i, video in enumerate(videos, 1):
                print(f"    {i}. {video['title']} [{video['platform']}]")
                print(f"       {video['video_url']}")
    
    return result


def no_videos_example():
    """Example showing behavior when no videos are found"""
    print("=" * 60)
    print("No Videos Found Example")
    print("=" * 60)
    
    tool = create_video_link_extractor_tool()
    
    # Test URL without videos - replace with actual URL that has no videos
    test_url = "https://general-navigation-models.github.io"
    
    print(f"测试没有视频的网页: {test_url}")
    
    result = tool._run(
        url=test_url,
        include_embeds=True,
        include_direct=True,
        include_video_tags=True
    )
    
    print(f"\n提取结果:")
    print(f"状态: {result['status']}")
    print(f"消息: {result['message']}")
    print(f"视频数量: {result['total_count']}")
    print(f"平台列表: {result['platforms_found']}")
    
    return result


def error_handling_example():
    """Example showing error handling for invalid URLs"""
    print("=" * 60)
    print("Error Handling Example")
    print("=" * 60)
    
    tool = create_video_link_extractor_tool()
    
    # Test with invalid URL
    invalid_url = "https://general-navigation-models.github.io"
    
    print(f"测试无效URL的错误处理: {invalid_url}")
    
    result = tool._run(
        url=invalid_url,
        include_embeds=True,
        include_direct=True,
        include_video_tags=True
    )
    
    print(f"\n错误处理结果:")
    print(f"状态: {result['status']}")
    print(f"消息: {result['message']}")
    print(f"视频数量: {result['total_count']}")
    
    # Test with malformed URL
    try:
        malformed_result = tool._run(
            url="not-a-valid-url",
            include_embeds=True,
            include_direct=True,
            include_video_tags=True
        )
        print(f"\n格式错误URL处理:")
        print(f"状态: {malformed_result['status']}")
        print(f"消息: {malformed_result['message']}")
    except Exception as e:
        print(f"\n格式错误URL触发异常: {e}")
    
    return result


def langchain_tool_integration_example():
    """Example showing integration with LangChain tool interface"""
    print("=" * 60)
    print("LangChain Tool Integration Example")
    print("=" * 60)
    
    tool = create_video_link_extractor_tool()
    
    print("使用LangChain工具接口:")
    print(f"工具名称: {tool.name}")
    print(f"工具描述: {tool.description}")
    print(f"参数模型: {tool.args_schema.__name__}")
    
    # Use the tool through LangChain interface
    test_params = {
        "url": "https://general-navigation-models.github.io",
        "include_embeds": True,
        "include_direct": True,
        "include_video_tags": True
    }
    
    print(f"\n调用参数: {json.dumps(test_params, indent=2, ensure_ascii=False)}")
    
    try:
        # This would be how you call it in a LangChain environment
        result = tool.invoke(test_params)
        print(f"\nLangChain调用结果:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"\nLangChain调用示例（模拟）:")
        print(f"由于网络或URL限制，实际调用可能失败: {e}")
        print("在实际环境中，请使用有效的网页URL进行测试")


def main():
    """Main example function"""
    print("网页视频链接提取工具使用示例")
    print("Video Link Extractor Tool Examples")
    print("=" * 80)
    print("注意：示例使用了占位符URL，实际使用时请替换为真实的网页URL")
    print("=" * 80)
    
    try:
        # 1. Basic webpage video extraction
        basic_webpage_video_extraction()
        
        # 2. Iframe embed extraction  
        iframe_embed_extraction_example()
        
        # 3. HTML5 video extraction
        html5_video_extraction_example()
        
        # 4. Direct video links extraction
        direct_video_links_example()
        
        # 5. Comprehensive extraction
        comprehensive_extraction_example()
        
        # 6. No videos found example
        no_videos_example()
        
        # 7. Error handling
        error_handling_example()
        
        # 8. LangChain integration
        langchain_tool_integration_example()
        
    except KeyboardInterrupt:
        print("\n\n示例被用户中断")
    except Exception as e:
        print(f"\n\n示例执行出错: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 80)
    print("示例执行完成！")
    print("\n使用建议:")
    print("1. 将示例中的占位符URL替换为实际的网页URL")
    print("2. 测试包含视频内容的网页以验证提取功能")
    print("3. 根据需要调整include_embeds、include_direct、include_video_tags参数")
    print("4. 在生产环境中添加适当的错误处理和重试机制")


if __name__ == "__main__":
    main()