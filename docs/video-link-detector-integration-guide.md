# Video Link Detection Tool Integration Guide

## 概述

VideoLinkDetectorTool 是 HomeSystem 中的一个强大工具，用于从文本内容中检测和提取视频链接信息。该工具支持多个国内外主流视频平台，能够识别视频链接、提取标题，并通过高效的模式匹配提供准确的检测结果。

## 支持的平台

### 国际平台
- **YouTube**: 支持多种URL格式
  - `https://www.youtube.com/watch?v=VIDEO_ID`
  - `https://youtu.be/VIDEO_ID` 
  - `https://youtube.com/embed/VIDEO_ID`

- **Vimeo**: 视频分享平台
  - `https://vimeo.com/VIDEO_ID`
  - `https://player.vimeo.com/video/VIDEO_ID`

- **DailyMotion**: 法国视频平台
  - `https://www.dailymotion.com/video/VIDEO_ID`
  - `https://dai.ly/VIDEO_ID`

- **Twitch**: 游戏直播平台
  - `https://www.twitch.tv/videos/VIDEO_ID`
  - `https://clips.twitch.tv/CLIP_ID`

### 中文平台
- **哔哩哔哩 (Bilibili)**: 支持多种视频ID格式
  - `https://www.bilibili.com/video/BV[ID]`
  - `https://www.bilibili.com/video/av[ID]`
  - `https://b23.tv/[SHORT_ID]`

- **抖音 (Douyin)**: 短视频平台
  - `https://www.douyin.com/video/VIDEO_ID`
  - `https://v.douyin.com/SHORT_ID`

- **快手 (Kuaishou)**: 短视频平台
  - `https://www.kuaishou.com/profile/USER/video/VIDEO_ID`
  - `https://v.kuaishou.com/SHORT_ID`

- **微博 (Weibo)**: 社交媒体视频
  - `https://weibo.com/tv/show/ID:KEY`
  - `https://video.weibo.com/show?fid=ID:KEY`

## 安装和配置

### 依赖要求

```bash
pip install beautifulsoup4 lxml requests
```

### 基本导入

```python
from HomeSystem.graph.tool import create_video_link_detector_tool
```

## 基本使用方法

### 1. 创建工具实例

```python
# 创建基本检测工具（推荐）
tool = create_video_link_detector_tool()
```

### 2. 检测视频链接

```python
# 基本检测（不提取标题，速度最快）
result = tool._run(
    text="这里有个视频：https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    extract_titles=False
)

print(f"找到 {result['total_count']} 个视频")
for video in result['detected_videos']:
    print(f"平台: {video['platform']}, URL: {video['url']}")
```

### 3. 带标题提取的检测

```python
# 启用标题提取（会增加处理时间）
result = tool._run(
    text="推荐视频：https://www.bilibili.com/video/BV1x4411V75C",
    extract_titles=True
)

for video in result['detected_videos']:
    print(f"标题: {video['title']}")
    print(f"平台: {video['platform']}")
```

## 返回数据结构

### 检测结果

```python
{
    "detected_videos": [
        {
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "platform": "youtube",
            "video_id": "dQw4w9WgXcQ",
            "title": "Rick Astley - Never Gonna Give You Up",
            "status": "detected",
            "confidence": 0.9
        }
    ],
    "total_count": 1,
    "platforms_found": ["youtube"],
    "status": "success"
}
```

### 视频信息字段

- **url**: 原始视频URL
- **platform**: 检测到的平台名称
- **video_id**: 提取的视频ID
- **title**: 视频标题（如果启用标题提取）
- **status**: 检测状态 (`detected`)
- **confidence**: 检测置信度 (0.0 - 1.0)

## 高级功能

### 标题提取

工具支持从视频页面自动提取标题：

```python
# 启用标题提取
result = tool._run(
    text=content,
    extract_titles=True  # 默认为 True
)
```

**支持的标题提取方式：**
- 网页META标签 (`og:title`)
- HTML标题标签
- 页面JSON数据
- 平台特定的数据提取

### 批量检测

工具可以一次性检测文本中的多个视频链接：

```python
content = """
这里有几个视频推荐：
1. YouTube: https://www.youtube.com/watch?v=dQw4w9WgXcQ
2. 哔哩哔哩: https://www.bilibili.com/video/BV1xx411c7XD
3. 抖音: https://www.douyin.com/video/1234567890123456789
"""

result = tool._run(text=content, extract_titles=False)
print(f"检测到 {result['total_count']} 个视频，涉及平台: {result['platforms_found']}")
```

## 性能优化

### 检测模式选择

根据需求选择合适的检测模式：

```python
# 高速模式：只进行链接匹配（推荐）
result = tool._run(text=content, extract_titles=False)

# 完整模式：包含标题提取（较慢）
result = tool._run(text=content, extract_titles=True)
```

### 性能指标

基于测试结果：

- **模式匹配检测**: ~0.1毫秒/链接（极快）
- **含标题提取**: ~1000-1300毫秒/链接（需要网络请求）

## 集成到 LangGraph 代理

### 作为工具添加到代理

```python
from HomeSystem.graph.tool import create_video_link_detector_tool

# 在代理中添加工具
video_detector = create_video_link_detector_tool()

# 在 LangGraph 中使用
tools = [video_detector]
```

### 代理对话示例

```python
# 代理可以自动检测用户分享的视频链接
user_message = "我想分享个视频：https://www.bilibili.com/video/BV1xx411c7XD"
# 代理会自动使用VideoLinkDetectorTool提取视频信息
```

## 错误处理

### 常见错误场景

1. **网络超时**: 标题提取时可能遇到网络问题
2. **平台限制**: 某些平台可能限制爬虫访问
3. **URL格式变更**: 新的URL格式可能不被识别

### 错误处理示例

```python
result = tool._run(text=content)

if result['status'] == 'error':
    print(f"检测失败: {result.get('error', '未知错误')}")
else:
    # 处理成功结果
    for video in result['detected_videos']:
        if video['title'] == "Unknown video link":
            print(f"无法获取标题: {video['url']}")
        else:
            print(f"成功提取: {video['title']}")
```

## 配置和定制

### 平台支持扩展

可以通过修改 `PLATFORM_PATTERNS` 添加新平台支持：

```python
# 在 VideoLinkDetectorTool 类中添加新的正则模式
new_patterns = {
    'new_platform': [
        r'pattern1',
        r'pattern2'
    ]
}
```

### 标题提取定制

可以为新平台添加专用的标题提取方法：

```python
def _extract_new_platform_title(self, video_id: str) -> str:
    # 实现特定平台的标题提取逻辑
    pass
```

## 测试和验证

### 运行示例测试

```bash
# 运行完整示例
python examples/video_link_detector_example.py
```

### 平台覆盖率测试

测试结果显示各平台检测准确率：

- YouTube: 100% (3/3)
- Bilibili: 100% (3/3) 
- Douyin: 100% (2/2)
- Kuaishou: 100% (2/2)
- Vimeo: 100% (2/2)
- Weibo: 100% (2/2)

### 单元测试

```python
def test_basic_detection():
    tool = create_video_link_detector_tool()
    result = tool._run("测试: https://www.youtube.com/watch?v=test123")
    assert result['total_count'] == 1
    assert result['detected_videos'][0]['platform'] == 'youtube'
```

## 最佳实践

### 1. 选择合适的检测模式

```python
# 大批量文本处理：关闭标题提取
for batch in large_text_batches:
    result = tool._run(batch, extract_titles=False)

# 单个重要链接：启用标题提取
result = tool._run(important_link, extract_titles=True)
```

### 2. 处理检测结果

```python
def process_video_results(result):
    if result['status'] != 'success':
        return []
    
    videos = []
    for video_info in result['detected_videos']:
        # 过滤高置信度结果
        if video_info['confidence'] >= 0.8:
            videos.append({
                'platform': video_info['platform'],
                'title': video_info['title'],
                'url': video_info['url']
            })
    
    return videos
```

### 3. 错误容忍

```python
def safe_video_detection(text):
    try:
        result = tool._run(text, extract_titles=True)
        return process_video_results(result)
    except Exception as e:
        logger.error(f"视频检测失败: {e}")
        # 降级到基本检测
        try:
            result = tool._run(text, extract_titles=False)
            return process_video_results(result)
        except Exception as e2:
            logger.error(f"基本检测也失败: {e2}")
            return []
```

## 故障排查

### 常见问题

1. **检测不到链接**
   - 检查URL格式是否正确
   - 确认平台是否在支持列表中
   - 查看日志输出

2. **标题提取失败**
   - 检查网络连接
   - 确认目标网站是否可访问
   - 考虑关闭标题提取以提高稳定性

3. **性能问题**
   - 关闭标题提取功能
   - 减少批量处理的文本大小
   - 考虑异步处理

### 调试模式

```python
import logging
logging.getLogger('HomeSystem.graph.tool.video_link_detector').setLevel(logging.DEBUG)

# 运行检测查看详细日志
result = tool._run(text=content, extract_titles=True)
```

## 版本历史

- **v1.0**: 初始版本，支持主要平台检测
- **v1.1**: 添加标题提取功能
- **v1.2**: 优化中文平台支持

## 贡献和扩展

欢迎为工具添加新平台支持或改进现有功能：

1. 添加新的正则模式到 `PLATFORM_PATTERNS`
2. 实现对应的标题提取方法
3. 添加测试用例
4. 更新文档

## 总结

VideoLinkDetectorTool 是一个功能强大、易于使用的视频链接检测工具，特别适合需要处理多平台视频内容的应用场景。通过合理配置检测选项，可以在准确性和性能之间取得良好平衡。