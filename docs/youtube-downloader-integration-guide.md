# HomeSystem YouTube视频下载工具集成指南

HomeSystem现已支持YouTube等多平台视频下载功能，专为论文研究中的视频资源收集和管理而设计。

## 📋 目录

- [概述](#概述)
- [功能特性](#功能特性)
- [快速开始](#快速开始)
- [API参考](#api参考)
- [使用示例](#使用示例)
- [配置选项](#配置选项)
- [安全特性](#安全特性)
- [故障排除](#故障排除)
- [最佳实践](#最佳实践)
- [平台支持](#平台支持)

## 概述

YouTubeDownloaderTool是基于yt-dlp库实现的多功能视频下载工具，完全集成到HomeSystem的LangGraph代理系统中。该工具特别针对学术研究场景进行了优化，支持论文相关视频资源的自动化收集和管理。

### 核心优势

- 🎯 **多平台支持**：YouTube、Bilibili、Vimeo、Dailymotion等
- 🏷️ **智能命名**：支持大模型确定文件名，自动清理不安全字符
- ⚙️ **灵活配置**：质量、格式、大小限制等多维度控制
- 🔒 **安全可靠**：输入验证、平台检查、磁盘空间管理
- 🔄 **无缝集成**：完全兼容LangChain工具生态系统

## 功能特性

### 下载功能
- **多格式支持**：MP4、WEBM、MKV、AVI等
- **质量控制**：支持best/worst/720p/1080p等设置
- **音频提取**：支持纯音频下载模式（MP3格式）
- **文件大小限制**：防止下载过大文件

### 智能特性
- **自动文件命名**：基于视频标题和用户指定名称
- **重复检测**：避免重复下载相同内容
- **进度跟踪**：实时显示下载进度和状态
- **错误恢复**：智能重试和错误处理机制

### 安全特性
- **URL验证**：检查URL格式和有效性
- **平台白名单**：仅支持已验证的视频平台
- **文件名清理**：自动清理不安全字符
- **磁盘空间检查**：下载前检查可用空间

## 快速开始

### 1. 安装依赖

```bash
pip install "yt-dlp[default]>=2024.12.0"
```

### 2. 基本使用

```python
from HomeSystem.graph.tool import create_youtube_downloader_tool

# 创建下载工具
downloader = create_youtube_downloader_tool("/path/to/download/directory")

# 下载视频
result = downloader.invoke({
    "url": "https://www.youtube.com/watch?v=example",
    "filename": "research_video",
    "quality": "720p",
    "format_preference": "mp4"
})

print(result)
```

### 3. 在LangGraph中使用

```python
from HomeSystem.graph.tool import create_youtube_downloader_tool
from langgraph.graph import StateGraph

# 创建工具
tools = [create_youtube_downloader_tool("./downloads")]

# 添加到图中
graph = StateGraph(state_schema)
graph.add_node("download", tools[0])
```

## API参考

### YouTubeDownloaderTool

主要的视频下载工具类。

#### 构造函数

```python
YouTubeDownloaderTool(download_dir: str, **kwargs)
```

**参数：**
- `download_dir` (str): 下载目录路径，工具初始化时创建

#### 输入模型 - YouTubeDownloaderInput

```python
class YouTubeDownloaderInput(BaseModel):
    url: str  # 视频URL（必需）
    filename: Optional[str] = None  # 自定义文件名
    format_preference: str = "mp4"  # 首选格式
    quality: str = "best"  # 视频质量
    audio_only: bool = False  # 是否只下载音频
    max_filesize: Optional[str] = "500M"  # 最大文件大小
```

#### 主要方法

##### invoke(input_dict) -> str

执行视频下载操作。

**参数：**
- `input_dict` (dict): 包含下载参数的字典

**返回值：**
- `str`: 下载结果信息

##### _is_supported_platform(url) -> bool

检查URL是否属于支持的平台。

**参数：**
- `url` (str): 视频URL

**返回值：**
- `bool`: 是否支持该平台

### 工厂函数

#### create_youtube_downloader_tool(download_dir) -> YouTubeDownloaderTool

创建YouTube下载工具实例的便捷函数。

**参数：**
- `download_dir` (str): 下载目录路径

**返回值：**
- `YouTubeDownloaderTool`: 配置好的工具实例

## 使用示例

### 基本视频下载

```python
from HomeSystem.graph.tool import create_youtube_downloader_tool

downloader = create_youtube_downloader_tool("./research_videos")

result = downloader.invoke({
    "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "filename": "demo_video",
    "quality": "720p",
    "format_preference": "mp4",
    "max_filesize": "100M"
})

print(result)
```

### 音频提取

```python
# 提取音频用于播客或讲座
result = downloader.invoke({
    "url": "https://www.youtube.com/watch?v=lecture_id",
    "filename": "machine_learning_lecture",
    "audio_only": True,
    "max_filesize": "50M"
})
```

### 批量下载

```python
video_list = [
    {
        "url": "https://www.youtube.com/watch?v=vid1",
        "filename": "intro_to_ai",
        "quality": "1080p"
    },
    {
        "url": "https://www.youtube.com/watch?v=vid2", 
        "filename": "deep_learning_basics",
        "quality": "720p"
    }
]

for video in video_list:
    try:
        result = downloader.invoke(video)
        print(f"✓ 成功: {video['filename']}")
    except Exception as e:
        print(f"✗ 失败: {video['filename']} - {e}")
```

### 与论文分析工作流集成

```python
# 模拟论文分析发现的视频资源
paper_videos = [
    "https://www.youtube.com/watch?v=cnn_explanation",
    "https://www.youtube.com/watch?v=transformer_demo"
]

# 为特定论文创建目录
paper_title = "attention_is_all_you_need"
video_dir = f"./research/{paper_title}/videos"

downloader = create_youtube_downloader_tool(video_dir)

for i, url in enumerate(paper_videos, 1):
    result = downloader.invoke({
        "url": url,
        "filename": f"{paper_title}_supplement_{i:02d}",
        "quality": "best",
        "format_preference": "mp4"
    })
```

## 配置选项

### 视频质量设置

| 选项 | 说明 | 适用场景 |
|------|------|----------|
| `best` | 最佳可用质量 | 重要研究视频 |
| `worst` | 最低质量 | 快速预览 |
| `1080p` | 1080p高清 | 详细分析 |
| `720p` | 720p标清 | 一般用途 |
| `480p` | 480p低清 | 网络受限环境 |

### 格式偏好

| 格式 | 优势 | 适用场景 |
|------|------|----------|
| `mp4` | 兼容性最好 | 通用播放 |
| `webm` | 文件较小 | 存储受限 |
| `mkv` | 质量最高 | 专业分析 |

### 文件大小限制

```python
# 不同场景的大小限制建议
size_limits = {
    "quick_preview": "50M",     # 快速预览
    "standard_video": "200M",   # 标准视频
    "high_quality": "500M",     # 高质量视频
    "research_archive": "1G"    # 研究存档
}
```

## 安全特性

### 输入验证

工具会自动验证和清理：
- **URL格式**：检查URL的有效性和安全性
- **文件名安全**：清理特殊字符，防止路径注入
- **参数合法性**：验证质量、格式等参数的有效性

### 平台限制

目前支持的平台：
- ✅ YouTube (youtube.com, youtu.be)
- ✅ Bilibili (bilibili.com)
- ✅ Vimeo (vimeo.com)
- ✅ Dailymotion (dailymotion.com)
- ✅ Twitch (twitch.tv)
- ✅ TikTok (tiktok.com)

### 资源保护

- **磁盘空间检查**：下载前检查可用空间（默认1GB阈值）
- **文件大小限制**：防止下载过大文件占用存储
- **超时控制**：防止长时间占用系统资源

## 故障排除

### 常见问题

#### 1. 下载失败

**症状**：下载过程中出现错误
```
下载失败: ERROR: Video unavailable
```

**解决方案**：
- 检查视频URL是否有效
- 确认视频未被删除或设为私有
- 验证网络连接状态
- 尝试使用不同的质量设置

#### 2. 不支持的平台

**症状**：平台检查失败
```
警告: 平台可能不受支持，但将尝试下载
```

**解决方案**：
- 检查URL是否属于支持的平台列表
- 如需支持新平台，可联系开发团队

#### 3. 磁盘空间不足

**症状**：空间检查失败
```
错误: 磁盘空间不足，无法下载
```

**解决方案**：
- 清理下载目录中的旧文件
- 选择其他有足够空间的目录
- 设置更小的文件大小限制

#### 4. 文件名问题

**症状**：文件名包含特殊字符
```
文件名被清理为: video___title_cleaned
```

**解决方案**：
- 这是正常的安全清理行为
- 如需特定文件名，请在filename参数中指定

### 调试技巧

#### 启用详细日志

```python
import logging

# 设置日志级别
logging.getLogger("HomeSystem.graph.tool.youtube_downloader").setLevel(logging.DEBUG)

# 或使用loguru
from loguru import logger
logger.add("download.log", level="DEBUG")
```

#### 测试工具连接

```python
from HomeSystem.graph.tool import create_youtube_downloader_tool

# 创建测试工具
downloader = create_youtube_downloader_tool("/tmp/test")

# 测试平台支持
test_urls = [
    "https://www.youtube.com/watch?v=test",
    "https://your-target-url.com"
]

for url in test_urls:
    supported = downloader._is_supported_platform(url)
    print(f"{url}: {'支持' if supported else '不支持'}")
```

## 最佳实践

### 1. 目录管理

```python
# 按研究主题组织
research_structure = {
    "computer_vision": "./research/cv/videos",
    "nlp": "./research/nlp/videos", 
    "robotics": "./research/robotics/videos"
}

# 按论文组织
paper_videos = f"./research/papers/{paper_id}/supplementary_videos"
```

### 2. 质量选择策略

```python
# 根据用途选择质量
quality_strategy = {
    "quick_review": "480p",      # 快速浏览
    "detailed_analysis": "720p", # 详细分析
    "presentation": "1080p",     # 演示用途
    "archive": "best"           # 长期存档
}
```

### 3. 批量处理优化

```python
import time
from pathlib import Path

def batch_download_with_retry(downloader, video_list, max_retries=3):
    """批量下载with重试机制"""
    
    results = []
    
    for video in video_list:
        retry_count = 0
        success = False
        
        while retry_count < max_retries and not success:
            try:
                result = downloader.invoke(video)
                results.append({"video": video, "status": "success", "result": result})
                success = True
                
            except Exception as e:
                retry_count += 1
                if retry_count < max_retries:
                    print(f"重试 {retry_count}/{max_retries}: {video.get('filename', 'unknown')}")
                    time.sleep(5)  # 等待5秒后重试
                else:
                    results.append({"video": video, "status": "failed", "error": str(e)})
    
    return results
```

### 4. 存储空间管理

```python
def manage_storage(download_dir, max_size_gb=10):
    """管理下载目录的存储空间"""
    
    download_path = Path(download_dir)
    
    # 计算当前使用空间
    total_size = sum(f.stat().st_size for f in download_path.rglob('*') if f.is_file())
    total_size_gb = total_size / (1024**3)
    
    if total_size_gb > max_size_gb:
        # 删除最旧的文件
        files = sorted(download_path.rglob('*'), key=lambda x: x.stat().st_mtime)
        
        for old_file in files:
            if old_file.is_file():
                old_file.unlink()
                total_size_gb -= old_file.stat().st_size / (1024**3)
                
                if total_size_gb <= max_size_gb * 0.8:  # 保留20%缓冲
                    break
```

### 5. 与AI代理集成

```python
from HomeSystem.graph.tool import create_youtube_downloader_tool
from langchain.agents import create_openai_tools_agent

# 创建包含下载功能的代理
tools = [
    create_youtube_downloader_tool("./research_downloads"),
    # 其他工具...
]

agent = create_openai_tools_agent(
    llm=your_llm,
    tools=tools,
    prompt="""你是一个研究助手，可以帮助下载和分析视频资源。
    当用户提到需要视频资料时，使用youtube_downloader工具下载相关内容。"""
)
```

## 平台支持

### 当前支持的平台

| 平台 | 域名 | 状态 | 备注 |
|------|------|------|------|
| YouTube | youtube.com, youtu.be | ✅ 完全支持 | 主要测试平台 |
| Bilibili | bilibili.com | ✅ 完全支持 | 中文内容丰富 |
| Vimeo | vimeo.com | ✅ 完全支持 | 高质量内容 |
| Dailymotion | dailymotion.com | ✅ 完全支持 | 欧洲平台 |
| Twitch | twitch.tv | ✅ 支持VOD | 直播录像 |
| TikTok | tiktok.com | ✅ 部分支持 | 短视频平台 |

### 平台特性说明

#### YouTube
- **优势**：内容丰富，API稳定，质量选择多样
- **特殊功能**：支持播放列表，字幕下载
- **限制**：地区限制，版权保护

#### Bilibili
- **优势**：中文学术内容多，技术讲座丰富
- **特殊功能**：弹幕数据，多P视频
- **限制**：部分内容需要登录

#### Vimeo
- **优势**：高质量内容，专业制作
- **特殊功能**：隐私控制，嵌入选项
- **限制**：部分内容付费

### 扩展新平台

如果需要支持新的视频平台，请联系开发团队或参考以下步骤：

1. **检查yt-dlp支持**：确认目标平台在yt-dlp支持列表中
2. **更新平台列表**：在`_supported_platforms`中添加新域名
3. **测试功能**：验证下载和解析功能正常
4. **更新文档**：添加平台特性说明

## 性能优化

### 下载性能调优

```python
# 自定义yt-dlp选项以提高性能
def create_optimized_downloader(download_dir):
    downloader = create_youtube_downloader_tool(download_dir)
    
    # 可以通过修改内部选项来优化性能
    # 注意：这需要对工具内部实现的了解
    return downloader

# 并发下载（谨慎使用，避免被平台限制）
import asyncio
from concurrent.futures import ThreadPoolExecutor

async def concurrent_download(video_list, max_workers=3):
    """并发下载多个视频（注意速率限制）"""
    
    def download_single(video):
        downloader = create_youtube_downloader_tool(f"./downloads/{video['category']}")
        return downloader.invoke(video)
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        loop = asyncio.get_event_loop()
        tasks = [
            loop.run_in_executor(executor, download_single, video) 
            for video in video_list
        ]
        return await asyncio.gather(*tasks)
```

### 存储优化

```python
# 压缩下载的视频以节省空间
import subprocess

def compress_video(input_path, output_path, crf=28):
    """使用ffmpeg压缩视频"""
    
    cmd = [
        'ffmpeg', '-i', input_path,
        '-vcodec', 'libx264', '-crf', str(crf),
        '-preset', 'medium', '-acodec', 'aac',
        output_path
    ]
    
    subprocess.run(cmd, check=True)
```

## 版本更新

### 当前版本：1.0.0

#### 新增功能
- ✅ 多平台视频下载支持
- ✅ 智能文件命名和清理
- ✅ 完整的输入验证和错误处理
- ✅ LangChain工具生态集成
- ✅ 音频提取功能
- ✅ 批量下载支持

#### 已知限制
- 不支持需要登录的平台内容
- 不支持直播流下载
- 某些地区限制内容可能无法下载

### 路线图

#### v1.1.0（计划中）
- [ ] 字幕下载和处理
- [ ] 播放列表批量下载
- [ ] 下载进度回调增强
- [ ] 更多平台支持

#### v1.2.0（计划中）
- [ ] 视频内容AI分析集成
- [ ] 自动转录功能
- [ ] 智能分类和标记
- [ ] 云存储集成

## 技术实现细节

### 架构设计

```
YouTubeDownloaderTool
├── 输入验证层 (YouTubeDownloaderInput)
├── 平台检查层 (_is_supported_platform)
├── 资源管理层 (_check_disk_space)
├── 下载执行层 (yt-dlp wrapper)
├── 文件管理层 (_find_downloaded_files)
└── 错误处理层 (Exception handling)
```

### 依赖关系

```
yt-dlp[default] >= 2024.12.0
├── brotli              # 压缩支持
├── mutagen             # 音频元数据
├── pycryptodomex       # 加密支持
├── websockets          # 流协议支持
└── requests            # HTTP请求
```

### 安全考虑

1. **输入清理**：所有用户输入都经过严格验证和清理
2. **路径安全**：防止路径遍历攻击，限制下载位置
3. **资源限制**：文件大小和磁盘空间检查，防止资源耗尽
4. **平台验证**：仅支持白名单中的可信平台
5. **错误隐藏**：不暴露内部系统信息给用户

## 贡献指南

### 如何贡献

1. **报告问题**：在GitHub Issues中描述遇到的问题
2. **建议功能**：提交功能请求和改进建议
3. **代码贡献**：Fork项目，创建Pull Request
4. **文档改进**：完善使用指南和API文档

### 开发环境设置

```bash
# 克隆项目
git clone https://github.com/your-org/homesystem.git
cd homesystem

# 安装开发依赖
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 运行测试
python -m pytest tests/test_youtube_downloader.py

# 运行示例
python examples/youtube_downloader_example.py
```

---

## 📞 支持与反馈

如有问题或建议，请通过以下方式联系：

- **GitHub Issues**: [项目问题跟踪](https://github.com/your-org/homesystem/issues)
- **文档**: 查看完整的[项目文档](../README.md)
- **示例**: 参考[使用示例](../examples/youtube_downloader_example.py)

---

*最后更新：2024年12月*