# Video Link Extractor Tool Integration Guide

## 概述

VideoLinkExtractorTool 是 HomeSystem 中的一个网页视频链接提取工具，用于从指定网页中提取所有可用的视频链接和标题。该工具支持多种视频来源类型，包括iframe嵌入视频、HTML5 video标签和直接视频文件链接。

## 核心功能

### 视频检测类型
- **iframe嵌入视频**: YouTube、Bilibili、Vimeo、抖音、快手等平台的嵌入式视频
- **HTML5 video标签**: 网页中直接的video元素及其source子标签
- **直接视频文件链接**: 指向视频文件的直接链接(.mp4、.webm、.avi等)

### 标题提取
- 从iframe的title属性和data-title属性提取
- 从周围文本内容智能分析
- 从链接文本和文件名解析
- 找不到标题时显示"unknown"
- 没找到任何视频时返回"没有视频"消息

## 支持的平台

### 国际平台
- **YouTube**: 支持多种嵌入格式
  - `https://youtube.com/embed/VIDEO_ID`
  - `https://www.youtube.com/watch?v=VIDEO_ID`
  - `https://youtu.be/VIDEO_ID`

- **Vimeo**: 视频分享平台
  - `https://vimeo.com/VIDEO_ID`
  - `https://player.vimeo.com/video/VIDEO_ID`

### 中文平台
- **哔哩哔哩 (Bilibili)**: 支持多种视频ID格式
  - `https://www.bilibili.com/video/BV[ID]`
  - `https://www.bilibili.com/video/av[ID]`
  - `https://player.bilibili.com/player.html?aid=[ID]`

- **抖音 (Douyin)**: 短视频平台
  - `https://www.douyin.com/video/VIDEO_ID`
  - `https://v.douyin.com/SHORT_ID`

- **快手 (Kuaishou)**: 短视频平台
  - `https://www.kuaishou.com/profile/USER/video/VIDEO_ID`
  - `https://v.kuaishou.com/SHORT_ID`

### 其他支持
- **直接视频文件**: .mp4、.webm、.ogg、.avi、.mov、.mkv、.flv、.m4v、.wmv

## 安装和配置

### 依赖要求

```bash
pip install beautifulsoup4 lxml requests
```

### 基本导入

```python
from HomeSystem.graph.tool import create_video_link_extractor_tool
```

## 基本使用方法

### 1. 创建工具实例

```python
# 创建视频链接提取工具
tool = create_video_link_extractor_tool()
```

### 2. 基本网页视频提取

```python
# 从网页提取所有视频
result = tool._run(
    url="https://example.com/page-with-videos",
    include_embeds=True,      # 包含嵌入式视频
    include_direct=True,      # 包含直接视频文件链接  
    include_video_tags=True   # 包含HTML5 video标签
)

print(f"状态: {result['status']}")
print(f"消息: {result['message']}")
print(f"找到视频: {result['total_count']} 个")

if result['videos']:
    for video in result['videos']:
        print(f"标题: {video['title']}")
        print(f"平台: {video['platform']}")
        print(f"来源类型: {video['source_type']}")
        print(f"URL: {video['video_url']}")
```

### 3. 选择性提取

```python
# 只提取嵌入式视频
result = tool._run(
    url="https://example.com/embedded-videos",
    include_embeds=True,
    include_direct=False,
    include_video_tags=False
)

# 只提取直接视频文件
result = tool._run(
    url="https://example.com/video-files",
    include_embeds=False,
    include_direct=True,
    include_video_tags=False
)
```

## 返回数据结构

### 成功提取结果

```python
{
    "videos": [
        {
            "video_url": "https://www.youtube.com/embed/dQw4w9WgXcQ",
            "title": "Rick Astley - Never Gonna Give You Up",
            "platform": "youtube",
            "source_type": "embed",
            "thumbnail_url": null,
            "duration": null
        },
        {
            "video_url": "https://example.com/videos/demo.mp4",
            "title": "demo",
            "platform": "direct",
            "source_type": "direct",
            "thumbnail_url": null,
            "duration": null
        }
    ],
    "total_count": 2,
    "platforms_found": ["youtube", "direct"],
    "status": "success",
    "message": "找到2个视频"
}
```

### 没有视频的结果

```python
{
    "videos": [],
    "total_count": 0,
    "platforms_found": [],
    "status": "no_videos_found",
    "message": "没有视频"
}
```

### 错误情况

```python
{
    "videos": [],
    "total_count": 0,
    "platforms_found": [],
    "status": "error",
    "message": "提取过程中发生错误: [具体错误信息]"
}
```

### 视频信息字段

- **video_url**: 视频URL（嵌入URL或直接文件URL）
- **title**: 视频标题，找不到时为"unknown"
- **platform**: 视频平台（youtube、bilibili、vimeo、direct等）
- **source_type**: 来源类型（embed、direct、video_tag）
- **thumbnail_url**: 缩略图URL（预留，目前为null）
- **duration**: 视频时长（预留，目前为null）

## 高级功能

### 平台检测

工具能够智能检测iframe中的视频平台：

```python
# 自动识别不同平台的嵌入模式
platforms_detected = [
    'youtube',    # YouTube嵌入
    'bilibili',   # 哔哩哔哩嵌入
    'vimeo',      # Vimeo嵌入
    'douyin',     # 抖音嵌入
    'kuaishou',   # 快手嵌入
    'direct'      # 直接视频文件
]
```

### 标题智能提取

工具使用多种方法提取视频标题：

1. **iframe属性**: title、data-title属性
2. **上下文分析**: 父级元素中的标题标签
3. **链接文本**: 链接的显示文本
4. **文件名解析**: 从URL路径提取文件名

### 去重处理

工具自动对检测到的视频进行去重：

```python
# 相同URL的视频只会出现一次
unique_videos = tool._deduplicate_videos(all_detected_videos)
```

## 性能优化

### 网络请求优化

工具使用持久化会话和合理的请求头：

```python
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) ...'
})
```

### 超时控制

网络请求设置了合理的超时时间：

```python
response = self.session.get(url, timeout=15)
```

### 选择性提取

可以根据需求选择要提取的视频类型以提高性能：

```python
# 只提取iframe嵌入视频（最快）
result = tool._run(url, include_embeds=True, include_direct=False, include_video_tags=False)

# 全面提取（较慢）
result = tool._run(url, include_embeds=True, include_direct=True, include_video_tags=True)
```

## 集成到 LangGraph 代理

### 作为工具添加到代理

```python
from HomeSystem.graph.tool import create_video_link_extractor_tool

# 在代理中添加工具
video_extractor = create_video_link_extractor_tool()

# 在 LangGraph 中使用
tools = [video_extractor]
```

### LangChain工具接口

```python
# 通过LangChain工具接口调用
result = tool.invoke({
    "url": "https://example.com/video-page",
    "include_embeds": True,
    "include_direct": True,
    "include_video_tags": True
})
```

### 代理对话示例

```python
# 代理可以分析用户提供的网页链接
user_message = "请帮我看看这个页面有什么视频：https://example.com/news"
# 代理会自动使用VideoLinkExtractorTool提取视频信息
```

## 错误处理

### 常见错误场景

1. **网络连接问题**: 目标网页无法访问
2. **无效URL格式**: URL格式不正确
3. **解析错误**: HTML内容解析失败
4. **权限限制**: 网站阻止爬虫访问

### 错误处理示例

```python
result = tool._run(url="https://example.com")

if result['status'] == 'error':
    print(f"提取失败: {result['message']}")
elif result['status'] == 'no_videos_found':
    print("该网页没有找到视频")
else:
    print(f"成功提取 {result['total_count']} 个视频")
```

### 容错处理

```python
def safe_video_extraction(url):
    try:
        result = tool._run(url)
        return result
    except Exception as e:
        logger.error(f"视频提取失败 {url}: {e}")
        return {
            "videos": [],
            "total_count": 0,
            "platforms_found": [],
            "status": "error",
            "message": f"提取失败: {str(e)}"
        }
```

## 配置和定制

### 平台支持扩展

可以通过修改 `platform_patterns` 添加新平台支持：

```python
new_patterns = {
    'new_platform': [
        r'new-platform\.com/video/(\d+)',
        r'np\.video/([a-zA-Z0-9]+)'
    ]
}
```

### 视频文件格式扩展

可以添加新的视频文件格式支持：

```python
additional_extensions = {'.webm', '.ogv', '.3gp'}
```

### 自定义User-Agent

```python
tool.session.headers.update({
    'User-Agent': 'Custom Bot 1.0'
})
```

## 测试和验证

### 运行示例测试

```bash
# 运行完整示例
python examples/video_link_detector_example.py
```

### 单元测试示例

```python
def test_youtube_embed_detection():
    tool = create_video_link_extractor_tool()
    # 注意：需要使用包含YouTube嵌入的真实网页进行测试
    result = tool._run("https://example.com/youtube-embed-page")
    
    assert result['status'] in ['success', 'no_videos_found']
    if result['total_count'] > 0:
        youtube_videos = [v for v in result['videos'] if v['platform'] == 'youtube']
        assert len(youtube_videos) > 0

def test_no_videos_page():
    tool = create_video_link_extractor_tool()
    result = tool._run("https://example.com/text-only-page")
    
    assert result['status'] == 'no_videos_found'
    assert result['message'] == "没有视频"
    assert result['total_count'] == 0
```

### 网络测试注意事项

由于工具需要实际访问网页，测试时需要注意：

1. 使用真实的网页URL
2. 确保网络连接稳定
3. 考虑目标网站的访问限制
4. 为测试设置合理的超时时间

## 最佳实践

### 1. 选择合适的提取范围

```python
# 新闻网站通常包含嵌入视频
result = tool._run(news_url, include_embeds=True, include_direct=False, include_video_tags=False)

# 媒体网站可能有直接视频文件
result = tool._run(media_url, include_embeds=True, include_direct=True, include_video_tags=True)
```

### 2. 处理大量URL

```python
def batch_video_extraction(urls, max_concurrent=5):
    results = []
    for i in range(0, len(urls), max_concurrent):
        batch = urls[i:i + max_concurrent]
        batch_results = []
        
        for url in batch:
            result = safe_video_extraction(url)
            batch_results.append(result)
        
        results.extend(batch_results)
        # 添加延迟避免过于频繁的请求
        time.sleep(1)
    
    return results
```

### 3. 结果筛选和排序

```python
def filter_high_quality_videos(result):
    if result['status'] != 'success':
        return []
    
    quality_videos = []
    for video in result['videos']:
        # 过滤有标题的视频
        if video['title'] != 'unknown':
            quality_videos.append(video)
    
    # 按平台优先级排序
    platform_priority = {'youtube': 1, 'bilibili': 2, 'vimeo': 3, 'direct': 4}
    quality_videos.sort(key=lambda v: platform_priority.get(v['platform'], 5))
    
    return quality_videos
```

## 故障排查

### 常见问题

1. **提取不到视频**
   - 检查URL是否可访问
   - 确认网页是否包含支持的视频类型
   - 查看工具日志输出

2. **标题显示unknown**
   - 网页可能没有合适的标题信息
   - iframe可能缺少title属性
   - 考虑这是正常情况

3. **网络超时**
   - 检查网络连接
   - 考虑增加超时时间
   - 实现重试机制

### 调试技巧

```python
# 启用详细日志
import logging
logging.basicConfig(level=logging.DEBUG)

# 检查具体的HTML内容
result = tool._run(url)
# 如果需要，可以手动检查网页源码
```

## 版本历史

- **v2.0**: 重构为网页视频提取工具
  - 从文本链接检测转为网页内容分析
  - 支持iframe嵌入、HTML5 video标签、直接链接
  - 智能标题提取和平台检测
  - 完整的错误处理和状态反馈

## 迁移指南

从旧版本VideoLinkDetectorTool迁移到新版本VideoLinkExtractorTool：

### 主要变更

1. **功能变更**: 从文本链接检测改为网页视频提取
2. **输入参数**: 从text改为url参数
3. **输出格式**: 数据结构有所调整

### 迁移步骤

```python
# 旧版本用法
old_result = old_tool._run(text="包含链接的文本", extract_titles=True)

# 新版本用法  
new_result = new_tool._run(url="https://webpage-with-videos.com", include_embeds=True)
```

## 总结

VideoLinkExtractorTool 是一个功能强大的网页视频链接提取工具，特别适合需要从网页中发现和提取视频内容的应用场景。工具支持多种视频来源类型，提供智能的标题提取和平台识别，具有良好的错误处理和性能优化。通过合理配置提取选项，可以在功能完整性和执行效率之间取得良好平衡。