# 视频分析工具集成指南

## 概述

VideoAnalysisTool 是一个专门的视频内容分析工具，通过从视频中提取关键帧并使用本地VL（Vision-Language）模型进行分析，实现对视频内容的智能理解和描述。

## 核心特性

- **多种帧采样策略**: 支持顺序、随机、首帧、中间随机等采样方式
- **智能帧提取**: 基于OpenCV的高效视频处理
- **本地VL模型集成**: 使用现有VisionAgent架构进行帧分析  
- **中文交互支持**: 支持中文查询和分析结果
- **批量帧分析**: 自动分析多帧并生成综合报告
- **临时文件管理**: 自动清理提取的临时帧文件

## 安装和配置

### 依赖要求

```bash
# 核心依赖（通常已安装）
pip install opencv-python>=4.8.0
pip install langchain-core
pip install pydantic
pip install loguru

# 如果需要更好的视频处理支持
# apt-get install ffmpeg  # Linux
# brew install ffmpeg     # macOS
```

### VL模型配置

确保本地VL模型可用：

```python
# 检查可用的VL模型
from HomeSystem.graph.llm_factory import LLMFactory

factory = LLMFactory()
available_models = factory.get_available_chat_models()
print("可用的视觉模型:", [model for model in available_models if 'VL' in model or 'vision' in model.lower()])
```

## 基本使用

### 1. 创建工具实例

```python
from HomeSystem.graph.tool.video_analysis_tool import create_video_analysis_tool

# 基本创建
tool = create_video_analysis_tool()

# 带配置的创建
tool = create_video_analysis_tool(
    base_folder_path="/path/to/video/folder",  # 视频文件基础路径
    vision_model="ollama.Qwen2_5_VL_7B"       # 指定VL模型
)
```

### 2. 验证视频文件

```python
# 验证视频文件
validation = tool.validate_video("sample_video.mp4")

if validation['is_valid']:
    video_info = validation['video_info']
    print(f"视频时长: {video_info['duration']:.1f}秒")
    print(f"分辨率: {video_info['resolution']}")
    print(f"帧率: {video_info['fps']} FPS")
else:
    print(f"验证失败: {validation['error_message']}")
```

### 3. 基本视频分析

```python
# 基本分析
result = tool._run(
    analysis_query="分析这个视频的主要内容，描述关键场景和活动",
    video_path="sample_video.mp4",
    frame_count=5,
    sampling_method="sequential"
)

print("分析结果:")
print(result)
```

## 采样方法详解

### Sequential (顺序采样)
- **用途**: 分析视频的时间流程和连续性内容
- **特点**: 在视频时间轴上均匀分布提取帧
- **适用场景**: 教学视频、演示视频、故事情节分析

```python
result = tool._run(
    analysis_query="分析视频的整体流程",
    video_path="tutorial.mp4",
    frame_count=6,
    sampling_method="sequential"
)
```

### Random (随机采样)
- **用途**: 获取视频内容的随机样本，适合内容丰富的视频
- **特点**: 随机选择时间点提取帧
- **适用场景**: 综合性内容、多场景视频

```python
result = tool._run(
    analysis_query="随机分析视频中的不同场景",
    video_path="variety_show.mp4", 
    frame_count=8,
    sampling_method="random"
)
```

### First (首帧采样)
- **用途**: 快速了解视频开头内容
- **特点**: 只提取第一帧进行分析
- **适用场景**: 视频缩略图生成、快速内容预览

```python
result = tool._run(
    analysis_query="描述视频的开头画面",
    video_path="movie.mp4",
    frame_count=1,  # 实际只会提取1帧
    sampling_method="first"
)
```

### Middle Random (中间随机采样)
- **用途**: 避开开头结尾，专注分析视频核心内容
- **特点**: 从视频中间50%部分随机采样
- **适用场景**: 跳过片头片尾，分析主要内容

```python
result = tool._run(
    analysis_query="分析视频的核心内容，忽略开头结尾",
    video_path="presentation.mp4",
    frame_count=5,
    sampling_method="middle_random"
)
```

## 高级用法

### 1. 特定场景分析

```python
# 人物分析
result = tool._run(
    analysis_query="识别并描述视频中出现的人物，包括外观、服装和行为",
    video_path="interview.mp4",
    frame_count=8,
    sampling_method="random"
)

# 技术内容分析  
result = tool._run(
    analysis_query="这是一个技术演示视频，请重点分析技术要点、操作步骤和关键信息",
    video_path="tech_demo.mp4",
    frame_count=10,
    sampling_method="sequential"
)

# 场景环境分析
result = tool._run(
    analysis_query="详细描述视频中的场景环境、地点特征和背景信息",
    video_path="travel_vlog.mp4", 
    frame_count=6,
    sampling_method="middle_random"
)
```

### 2. 批量视频处理

```python
import os
from pathlib import Path

def analyze_video_folder(folder_path: str):
    """批量分析文件夹中的所有视频"""
    tool = create_video_analysis_tool(base_folder_path=folder_path)
    
    video_extensions = {'.mp4', '.avi', '.mov', '.mkv'}
    video_files = [f for f in os.listdir(folder_path) 
                   if Path(f).suffix.lower() in video_extensions]
    
    results = {}
    for video_file in video_files:
        try:
            result = tool._run(
                analysis_query="分析视频内容，提供详细描述",
                video_path=video_file,
                frame_count=5,
                sampling_method="sequential"
            )
            results[video_file] = result
        except Exception as e:
            results[video_file] = f"分析失败: {e}"
    
    return results
```

## 在LangGraph Agent中集成

### 1. 添加到Agent工具集

```python
from HomeSystem.graph.base_graph import BaseGraph
from HomeSystem.graph.tool.video_analysis_tool import create_video_analysis_tool

class VideoAnalysisAgent(BaseGraph):
    def __init__(self):
        super().__init__()
        
        # 添加视频分析工具
        self.video_tool = create_video_analysis_tool(
            base_folder_path="/data/videos",
            vision_model="ollama.Qwen2_5_VL_7B"
        )
        
        # 添加到工具列表
        self.tools = [self.video_tool]
        
        # 配置图节点
        self._setup_graph()
    
    def _setup_graph(self):
        """设置图结构"""
        # 实现具体的图节点配置
        pass
```

### 2. 工具调用示例

```python
# 在Agent对话中使用
agent = VideoAnalysisAgent()

# 通过自然语言调用
user_message = "请分析这个演示视频的内容: demo_video.mp4"
response = agent.run(user_message, thread_id="video_analysis_session")
```

## 性能优化建议

### 1. 帧数选择
- **短视频 (< 30秒)**: 3-5帧
- **中等视频 (30秒-5分钟)**: 5-8帧  
- **长视频 (> 5分钟)**: 8-12帧，或考虑视频分段

### 2. 采样策略选择
- **流程分析**: 使用 `sequential`
- **内容丰富**: 使用 `random`
- **快速预览**: 使用 `first`  
- **核心内容**: 使用 `middle_random`

### 3. 内存和存储管理
- 工具自动清理临时帧文件
- 大批量处理时考虑分批进行
- 监控临时目录磁盘使用

### 4. 模型选择
- `Qwen2_5_VL_7B`: 平衡性能和准确性
- 其他VL模型需验证兼容性

## 错误处理

### 常见错误和解决方案

```python
# 文件不存在
try:
    result = tool._run(
        analysis_query="分析视频",
        video_path="nonexistent.mp4"
    )
except FileNotFoundError as e:
    print(f"视频文件不存在: {e}")

# 格式不支持
validation = tool.validate_video("unsupported_format.xyz")
if not validation['is_valid']:
    print(f"不支持的格式: {validation['error_message']}")

# VL模型问题
try:
    tool = create_video_analysis_tool(vision_model="invalid_model")
except Exception as e:
    print(f"模型配置错误: {e}")
```

### 调试信息

启用详细日志：

```python
from loguru import logger
import sys

# 配置日志级别
logger.remove()
logger.add(sys.stdout, level="DEBUG")

# 现在运行分析会显示详细信息
result = tool._run(...)
```

## 支持的视频格式

当前支持的格式：
- `.mp4` (推荐)
- `.avi`
- `.mov`
- `.mkv` 
- `.flv`
- `.wmv`
- `.webm`
- `.m4v`
- `.3gp`
- `.ogv`

## 故障排除

### 1. OpenCV相关问题
```bash
# 重新安装OpenCV
pip uninstall opencv-python
pip install opencv-python==4.8.1.78
```

### 2. VL模型不可用
```python
# 检查模型状态
from HomeSystem.graph.llm_factory import LLMFactory
factory = LLMFactory()
try:
    llm = factory.create_chat_model("ollama.Qwen2_5_VL_7B")
    print("模型可用")
except Exception as e:
    print(f"模型不可用: {e}")
```

### 3. 临时文件清理问题
```python
# 手动清理临时文件
import tempfile
import shutil

temp_dir = tempfile.gettempdir()
for item in os.listdir(temp_dir):
    if item.startswith("video_frames_"):
        shutil.rmtree(os.path.join(temp_dir, item), ignore_errors=True)
```

## 完整示例

参考 `examples/video_analysis_example.py` 获取完整的使用示例和最佳实践。

## 更多资源

- [Vision Integration Guide](vision-integration-guide.md) - VL模型配置详解
- [LLM Integration Guide](llm-integration-guide.md) - 多模态模型集成
- [Project Structure](project-structure.md) - 项目架构说明