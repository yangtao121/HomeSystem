#!/usr/bin/env python3
"""
Video Link Detector Example

This example demonstrates how to use the VideoLinkDetectorTool to detect video links
from various platforms including YouTube, Bilibili, Douyin, Kuaishou, Vimeo, etc.

The tool can:
1. Detect video links from text content using pattern matching
2. Extract video titles when possible
3. Support multiple video platforms (domestic and international)
"""

import sys
from pathlib import Path

# Add the project root to the Python path
sys.path.append(str(Path(__file__).parent.parent))

from HomeSystem.graph.tool import create_video_link_detector_tool


def basic_video_detection_example():
    """Basic video link detection without title extraction"""
    print("=" * 60)
    print("Basic Video Link Detection Example")
    print("=" * 60)
    
    # Create the video link detector tool
    tool = create_video_link_detector_tool()
    
    # Test content with various video links
    test_content = """
    这里有一些视频链接分享：
    
    1. YouTube视频：https://www.youtube.com/watch?v=dQw4w9WgXcQ
    2. 哔哩哔哩：https://www.bilibili.com/video/BV1xx411c7XD
    3. 抖音短视频：https://www.douyin.com/video/1234567890123456789
    4. Vimeo: https://vimeo.com/123456789
    5. 快手视频：https://www.kuaishou.com/profile/user123/video/abc123def
    6. 这只是普通文本，没有视频链接
    7. YouTube短链接：https://youtu.be/abc12345678
    8. 微博视频：https://weibo.com/tv/show/1234567:abcdefg
    """
    
    # Run detection without title extraction for speed
    result = tool._run(
        text=test_content,
        extract_titles=False,  # Skip title extraction for faster processing
        use_llm_analysis=False
    )
    
    # Display results
    print(f"检测状态: {result['status']}")
    print(f"找到视频数量: {result['total_count']}")
    print(f"涉及平台: {result['platforms_found']}")
    print()
    
    if result['detected_videos']:
        print("检测到的视频:")
        for i, video in enumerate(result['detected_videos'], 1):
            print(f"  {i}. 平台: {video['platform']}")
            print(f"     URL: {video['url']}")
            print(f"     视频ID: {video['video_id']}")
            print(f"     置信度: {video['confidence']}")
            print()
    else:
        print("未检测到视频链接")
    
    return result


def video_detection_with_titles_example():
    """Video link detection with title extraction"""
    print("=" * 60)
    print("Video Link Detection with Title Extraction")
    print("=" * 60)
    
    # Create tool
    tool = create_video_link_detector_tool()
    
    # Test with a few real video links
    test_content = """
    推荐几个有趣的视频：
    1. 经典视频：https://www.youtube.com/watch?v=dQw4w9WgXcQ
    2. 技术分享：https://www.bilibili.com/video/BV1x4411V75C
    """
    
    print("测试内容:")
    print(test_content)
    print("\n正在检测并提取标题...")
    
    # Run with title extraction enabled
    result = tool._run(
        text=test_content,
        extract_titles=True,  # Enable title extraction
        use_llm_analysis=False
    )
    
    print(f"\n检测结果:")
    print(f"状态: {result['status']}")
    print(f"找到视频: {result['total_count']} 个")
    print(f"平台: {result['platforms_found']}")
    
    if result['detected_videos']:
        print("\n详细信息:")
        for i, video in enumerate(result['detected_videos'], 1):
            print(f"  视频 {i}:")
            print(f"    平台: {video['platform']}")
            print(f"    标题: {video['title']}")
            print(f"    URL: {video['url']}")
            print(f"    状态: {video['status']}")
            print(f"    置信度: {video['confidence']}")
            print()
    
    return result


def pattern_matching_example():
    """Example using pattern matching for video link detection"""
    print("=" * 60)
    print("Video Link Detection with Pattern Matching")
    print("=" * 60)
    
    # Create tool without LLM factory (pattern matching only)
    tool = create_video_link_detector_tool()
    
    # Test with some video links including potential edge cases
    test_content = """
    一些视频链接测试：
    1. https://www.youtube.com/watch?v=dQw4w9WgXcQ
    2. https://www.bilibili.com/video/BV1x4411V75C
    3. https://vimeo.com/123456789
    4. https://regular-website.com/article (这不是视频链接)
    5. https://youtu.be/abc12345678
    """
    
    print("测试内容:")
    print(test_content)
    print("\n使用纯模式匹配检测视频链接...")
    
    result = tool._run(
        text=test_content,
        extract_titles=False,  # Skip title extraction for demo
        use_llm_analysis=False  # Only use pattern matching
    )
    
    print(f"\n检测结果:")
    print(f"状态: {result['status']}")
    print(f"找到视频: {result['total_count']} 个")
    
    if result['detected_videos']:
        print("\n检测到的视频:")
        for i, video in enumerate(result['detected_videos'], 1):
            print(f"  {i}. 平台: {video['platform']}")
            print(f"     URL: {video['url']}")
            print(f"     检测方式: {video['status']}")
            print(f"     置信度: {video['confidence']}")
            print()
    else:
        print("\n未检测到视频链接")
    
    return result


def platform_coverage_test():
    """Test coverage of different video platforms"""
    print("=" * 60)
    print("Platform Coverage Test")
    print("=" * 60)
    
    tool = create_video_link_detector_tool()
    
    platform_tests = {
        'YouTube': [
            'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            'https://youtu.be/dQw4w9WgXcQ',
            'https://youtube.com/embed/dQw4w9WgXcQ'
        ],
        'Bilibili': [
            'https://www.bilibili.com/video/BV1xx411c7XD',
            'https://www.bilibili.com/video/av123456',
            'https://b23.tv/abc123'
        ],
        'Douyin': [
            'https://www.douyin.com/video/1234567890123456789',
            'https://v.douyin.com/abc123def'
        ],
        'Kuaishou': [
            'https://www.kuaishou.com/profile/user123/video/abc123def',
            'https://v.kuaishou.com/xyz789'
        ],
        'Vimeo': [
            'https://vimeo.com/123456789',
            'https://player.vimeo.com/video/123456789'
        ],
        'Weibo': [
            'https://weibo.com/tv/show/1234567:abcdefg',
            'https://video.weibo.com/show?fid=1234567:abcdefg'
        ]
    }
    
    total_detected = 0
    platform_results = {}
    
    for platform, urls in platform_tests.items():
        print(f"\n测试 {platform} 平台:")
        platform_count = 0
        
        for url in urls:
            result = tool._run(
                text=f"测试链接: {url}",
                extract_titles=False,
                use_llm_analysis=False
            )
            
            detected = result['total_count']
            platform_count += detected
            total_detected += detected
            
            print(f"  {url} -> {'检测成功' if detected > 0 else '未检测到'}")
        
        platform_results[platform] = platform_count
        print(f"  {platform} 总计: {platform_count}/{len(urls)}")
    
    print(f"\n总结:")
    print(f"总计测试链接: {sum(len(urls) for urls in platform_tests.values())}")
    print(f"成功检测: {total_detected}")
    
    for platform, count in platform_results.items():
        total_tests = len(platform_tests[platform])
        success_rate = (count / total_tests) * 100 if total_tests > 0 else 0
        print(f"  {platform}: {count}/{total_tests} ({success_rate:.1f}%)")


def performance_test():
    """Simple performance test"""
    print("=" * 60)
    print("Performance Test")
    print("=" * 60)
    
    import time
    
    tool = create_video_link_detector_tool()
    
    # Generate test content with multiple video links
    test_urls = [
        'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
        'https://www.bilibili.com/video/BV1xx411c7XD',
        'https://vimeo.com/123456789',
        'https://www.douyin.com/video/1234567890123456789',
        'https://youtu.be/abc12345678'
    ] * 10  # 50 URLs total
    
    test_content = "测试内容包含视频链接: " + " ".join(test_urls)
    
    print(f"测试内容长度: {len(test_content)} 字符")
    print(f"包含视频链接: {len(test_urls)} 个")
    
    # Test without title extraction
    start_time = time.time()
    result = tool._run(
        text=test_content,
        extract_titles=False,
        use_llm_analysis=False
    )
    no_title_time = time.time() - start_time
    
    print(f"\n不提取标题:")
    print(f"  处理时间: {no_title_time:.2f} 秒")
    print(f"  检测到: {result['total_count']} 个视频")
    print(f"  平均每个链接: {(no_title_time / len(test_urls)) * 1000:.1f} 毫秒")
    
    # Test a smaller sample with title extraction
    small_content = "测试标题提取: " + " ".join(test_urls[:5])
    start_time = time.time()
    result_with_titles = tool._run(
        text=small_content,
        extract_titles=True,
        use_llm_analysis=False
    )
    with_title_time = time.time() - start_time
    
    print(f"\n提取标题 (5个链接):")
    print(f"  处理时间: {with_title_time:.2f} 秒")
    print(f"  检测到: {result_with_titles['total_count']} 个视频")
    print(f"  平均每个链接: {(with_title_time / 5) * 1000:.1f} 毫秒")


def main():
    """Main example function"""
    print("视频链接检测工具使用示例")
    print("Video Link Detector Tool Examples")
    print("=" * 80)
    
    try:
        # 1. Basic detection example
        basic_video_detection_example()
        
        # 2. Title extraction example
        video_detection_with_titles_example()
        
        # 3. Pattern matching example
        pattern_matching_example()
        
        # 4. Platform coverage test
        platform_coverage_test()
        
        # 5. Performance test
        performance_test()
        
    except KeyboardInterrupt:
        print("\n\n示例被用户中断")
    except Exception as e:
        print(f"\n\n示例执行出错: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 80)
    print("示例执行完成！")


if __name__ == "__main__":
    main()