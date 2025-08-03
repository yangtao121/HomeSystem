# HomeSystem视觉功能集成指南

HomeSystem现已支持视觉功能，允许本地模型处理图片输入，同时保持云端模型的纯文本策略。

## 📋 目录

- [概述](#概述)
- [支持策略](#支持策略)
- [快速开始](#快速开始)
- [API参考](#api参考)
- [示例代码](#示例代码)
- [配置说明](#配置说明)
- [故障排除](#故障排除)
- [最佳实践](#最佳实践)

## 概述

HomeSystem的视觉功能基于以下核心原则：
- **本地模型**：完整视觉支持，可处理图片和文本
- **云端模型**：仅支持纯文本，拒绝图片输入
- **安全优先**：严格区分本地和云端模型的能力边界
- **用户友好**：提供清晰的错误提示和使用指导

### 支持的功能

- 多种图片格式支持 (JPEG, PNG, WebP, BMP, GIF, TIFF)
- 自动图片预处理和尺寸调整
- 多模态消息创建和处理
- 交互式视觉聊天
- 批量图片处理
- 完善的错误处理和验证

## 支持策略

### 本地模型 (Ollama)
- ✅ **支持视觉**：可处理图片和文本输入
- 🏠 **本地部署**：数据不离开本地环境
- 👁️ **视觉模型**：专门的多模态模型

### 云端模型 (API)
- ❌ **禁用视觉**：仅支持纯文本输入
- ☁️ **云端服务**：DeepSeek、SiliconFlow、火山引擎、月之暗面
- 🛡️ **安全策略**：防止敏感图片数据上传

## 快速开始

### 1. 环境准备

确保已安装必要依赖：
```bash
pip install Pillow  # 图片处理
```

确保Ollama服务正在运行，并下载视觉模型：
```bash
ollama pull qwen2.5vl:7b
```

### 2. 检查可用模型

```python
from HomeSystem.graph.llm_factory import list_available_vision_models

# 查看所有支持视觉的模型
vision_models = list_available_vision_models()
print("可用视觉模型:", vision_models)
```

### 3. 基础图片处理

```python
from HomeSystem.graph.chat_agent import ChatAgent

# 创建聊天代理
agent = ChatAgent()

# 使用图片进行单次查询
result = agent.run_with_image(
    image_path="your_image.jpg",
    text="请描述这张图片的内容"
)

print("AI分析结果:", result)
```

### 4. 交互式视觉聊天

```python
# 启动支持图片的交互式聊天
agent.chat_with_image("your_image.jpg")
```

## API参考

### LLMFactory 视觉相关方法

#### `get_available_vision_models() -> List[str]`
获取所有支持视觉的模型列表。

```python
from HomeSystem.graph.llm_factory import LLMFactory

factory = LLMFactory()
vision_models = factory.get_available_vision_models()
```

#### `supports_vision(model_name: str) -> bool`
检查指定模型是否支持视觉功能。

```python
supports_vision = factory.supports_vision("ollama.Qwen2_5_VL_7B")
```

#### `is_local_model(model_name: str) -> bool`
检查是否为本地模型。

```python
is_local = factory.is_local_model("ollama.Qwen2_5_VL_7B")
```

#### `create_vision_llm(model_name: str = None, **kwargs) -> BaseChatModel`
创建支持视觉的LLM实例。

```python
vision_llm = factory.create_vision_llm("ollama.Qwen2_5_VL_7B")
```

#### `validate_vision_input(model_name: str) -> None`
验证模型是否可以接受视觉输入。

```python
try:
    factory.validate_vision_input("deepseek.DeepSeek_V3")
except ValueError as e:
    print("错误:", e)  # 云端模型仅支持纯文本输入
```

### VisionUtils 图片处理工具

#### `image_to_base64(file_path: str, resize: bool = True) -> str`
将图片转换为base64编码。

```python
from HomeSystem.graph.vision_utils import VisionUtils

base64_data = VisionUtils.image_to_base64("image.jpg")
```

#### `create_image_message_content(image_path: str, text: str = "") -> List[dict]`
创建包含图片的多模态消息内容。

```python
content = VisionUtils.create_image_message_content(
    image_path="image.jpg",
    text="请分析这张图片"
)
```

#### `get_image_info(file_path: str) -> dict`
获取详细的图片信息。

```python
info = VisionUtils.get_image_info("image.jpg")
print(f"格式: {info['format']}, 尺寸: {info['size']}")
```

#### `validate_image_format(file_path: str) -> bool`
验证图片格式是否支持。

```python
is_supported = VisionUtils.validate_image_format("image.jpg")
```

### BaseGraph 视觉增强方法

#### `process_image_input(image_path: str, text: str = "") -> List[dict]`
处理图片输入，创建多模态消息内容。

```python
content = agent.process_image_input("image.jpg", "描述图片")
```

#### `run_with_image(image_path: str, text: str = "", model_name: str = None, thread_id: str = "1")`
使用图片输入运行agent。

```python
result = agent.run_with_image(
    image_path="image.jpg",
    text="这是什么？",
    model_name="ollama.Qwen2_5_VL_7B"
)
```

#### `chat_with_image(image_path: str, model_name: str = None)`
支持图片的交互式聊天模式。

```python
agent.chat_with_image("image.jpg", "ollama.Qwen2_5_VL_7B")
```

## 示例代码

### 完整使用示例

```python
#!/usr/bin/env python3
"""
HomeSystem视觉功能完整示例
"""

from HomeSystem.graph.llm_factory import (
    LLMFactory, 
    list_available_vision_models,
    check_vision_support
)
from HomeSystem.graph.vision_utils import VisionUtils
from HomeSystem.graph.chat_agent import ChatAgent

def main():
    # 1. 检查可用模型
    print("=== 检查可用模型 ===")
    vision_models = list_available_vision_models()
    print(f"支持视觉的模型: {vision_models}")
    
    if not vision_models:
        print("错误: 没有可用的视觉模型")
        return
    
    # 2. 验证图片
    image_path = "test_image.jpg"
    print(f"\n=== 验证图片: {image_path} ===")
    
    if not VisionUtils.validate_image_format(image_path):
        print("错误: 不支持的图片格式")
        return
    
    # 获取图片信息
    info = VisionUtils.get_image_info(image_path)
    print(f"图片信息: {info}")
    
    # 3. 创建聊天代理
    print("\n=== 创建聊天代理 ===")
    agent = ChatAgent()
    
    # 4. 使用图片进行查询
    print("\n=== 图片分析 ===")
    result = agent.run_with_image(
        image_path=image_path,
        text="请详细描述这张图片的内容，包括颜色、形状、文字等。",
        model_name=vision_models[0]
    )
    
    print("AI分析结果:")
    print(result)
    
    # 5. 演示错误处理
    print("\n=== 错误处理演示 ===")
    try:
        # 尝试用云端模型处理图片
        from HomeSystem.graph.llm_factory import validate_vision_input
        validate_vision_input("deepseek.DeepSeek_V3")
    except ValueError as e:
        print(f"预期错误: {e}")

if __name__ == "__main__":
    main()
```

### 批量图片处理

```python
from HomeSystem.graph.vision_utils import VisionUtils

def batch_analyze_images(image_paths, description_prompt="描述这张图片"):
    """批量分析多张图片"""
    results = []
    
    for image_path in image_paths:
        try:
            # 验证图片
            if not VisionUtils.validate_image_format(image_path):
                results.append({
                    'path': image_path,
                    'status': 'error',
                    'error': '不支持的图片格式'
                })
                continue
            
            # 分析图片
            agent = ChatAgent()
            result = agent.run_with_image(image_path, description_prompt)
            
            results.append({
                'path': image_path,
                'status': 'success',
                'analysis': result
            })
            
        except Exception as e:
            results.append({
                'path': image_path,
                'status': 'error',
                'error': str(e)
            })
    
    return results

# 使用示例
image_files = ["img1.jpg", "img2.png", "img3.webp"]
results = batch_analyze_images(image_files)

for result in results:
    print(f"图片: {result['path']}")
    if result['status'] == 'success':
        print(f"分析: {result['analysis']}")
    else:
        print(f"错误: {result['error']}")
    print("-" * 50)
```

### 自定义图片预处理

```python
from HomeSystem.graph.vision_utils import VisionUtils
from PIL import Image

def custom_image_processing(image_path, max_size=(1024, 1024)):
    """自定义图片预处理"""
    
    # 打开图片
    with Image.open(image_path) as img:
        # 转换为RGB
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # 调整尺寸
        img.thumbnail(max_size, Image.Resampling.LANCZOS)
        
        # 保存处理后的图片
        processed_path = f"processed_{Path(image_path).name}"
        img.save(processed_path, "JPEG", quality=90)
        
        return processed_path

# 使用自定义预处理
processed_image = custom_image_processing("large_image.jpg")
result = agent.run_with_image(processed_image, "分析处理后的图片")
```

## 配置说明

### 模型配置

在 `HomeSystem/graph/config/llm_providers.yaml` 中，每个模型都有 `supports_vision` 标识：

```yaml
# 本地视觉模型
- name: qwen2.5vl:7b
  key: ollama.Qwen2_5_VL_7B
  display_name: 通义千问 2.5-VL-7B (视觉)
  supports_vision: true  # 支持视觉
  
# 云端文本模型  
- name: deepseek-chat
  key: deepseek.DeepSeek_V3
  display_name: DeepSeek V3
  supports_vision: false  # 仅支持文本
```

### 环境变量

确保 `.env` 文件中配置了正确的Ollama地址：

```env
# Ollama 本地模型服务配置
OLLAMA_BASE_URL=http://192.168.5.217:11434
```

### 图片处理限制

```python
# vision_utils.py 中的默认限制
MAX_IMAGE_SIZE = (2048, 2048)  # 最大尺寸
MAX_FILE_SIZE = 20 * 1024 * 1024  # 最大20MB
SUPPORTED_IMAGE_FORMATS = {
    'JPEG', 'JPG', 'PNG', 'WebP', 'BMP', 'GIF', 'TIFF'
}
```

## 故障排除

### 常见问题

#### 1. "没有可用的视觉模型"

**原因**: Ollama未运行或未安装视觉模型

**解决方案**:
```bash
# 启动Ollama服务
ollama serve

# 下载视觉模型
ollama pull qwen2.5vl:7b

# 验证模型已安装
ollama list
```

#### 2. "云端模型仅支持纯文本输入"

**原因**: 尝试用云端模型处理图片

**解决方案**: 使用本地视觉模型
```python
# 错误的方式
agent.run_with_image("image.jpg", model_name="deepseek.DeepSeek_V3")

# 正确的方式
agent.run_with_image("image.jpg", model_name="ollama.Qwen2_5_VL_7B")
```

#### 3. "不支持的图片格式"

**原因**: 图片格式不在支持列表中

**解决方案**: 转换图片格式
```python
from PIL import Image

# 转换为JPEG格式
with Image.open("image.bmp") as img:
    img.convert('RGB').save("image.jpg", "JPEG")
```

#### 4. "文件过大"

**原因**: 图片文件超过20MB限制

**解决方案**: 压缩图片
```python
from HomeSystem.graph.vision_utils import VisionUtils

# 自动压缩和调整尺寸
base64_data = VisionUtils.image_to_base64("large_image.jpg", resize=True)
```

#### 5. 连接Ollama失败

**原因**: Ollama服务未运行或地址配置错误

**解决方案**:
```bash
# 检查Ollama状态
curl http://192.168.5.217:11434/api/version

# 检查环境变量
echo $OLLAMA_BASE_URL
```

### 调试方法

#### 启用详细日志

```python
from loguru import logger

# 设置日志级别
logger.add("vision_debug.log", level="DEBUG")
```

#### 测试模型连接

```python
from HomeSystem.graph.llm_factory import LLMFactory

factory = LLMFactory()

# 检查所有模型状态
factory.list_models()

# 测试特定模型
try:
    llm = factory.create_vision_llm("ollama.Qwen2_5_VL_7B")
    print("视觉模型创建成功")
except Exception as e:
    print(f"创建失败: {e}")
```

#### 验证图片处理

```python
from HomeSystem.graph.vision_utils import VisionUtils

# 获取详细图片信息
info = VisionUtils.get_image_info("test_image.jpg")
print("图片信息:", info)

# 测试base64编码
try:
    base64_data = VisionUtils.image_to_base64("test_image.jpg")
    print(f"编码成功，长度: {len(base64_data)}")
except Exception as e:
    print(f"编码失败: {e}")
```

## 最佳实践

### 1. 模型选择策略

```python
from HomeSystem.graph.llm_factory import list_available_vision_models

def get_best_vision_model():
    """选择最佳视觉模型"""
    vision_models = list_available_vision_models()
    
    # 优先级排序
    preferred_models = [
        "ollama.Qwen2_5_VL_7B",
        "ollama.Llama3_2_Vision_11B",
        "ollama.Qwen2_VL_7B"
    ]
    
    for model in preferred_models:
        if model in vision_models:
            return model
    
    return vision_models[0] if vision_models else None
```

### 2. 图片预处理优化

```python
def optimize_image_for_vision(image_path, target_size=(1024, 1024)):
    """优化图片以提高视觉处理效果"""
    from PIL import Image, ImageEnhance
    
    with Image.open(image_path) as img:
        # 转换颜色模式
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # 调整尺寸
        img.thumbnail(target_size, Image.Resampling.LANCZOS)
        
        # 增强对比度（可选）
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.2)
        
        # 保存优化后的图片
        optimized_path = f"optimized_{Path(image_path).name}"
        img.save(optimized_path, "JPEG", quality=85, optimize=True)
        
        return optimized_path
```

### 3. 错误处理模式

```python
def safe_vision_analysis(image_path, prompt, fallback_model=None):
    """安全的视觉分析，包含完整错误处理"""
    from HomeSystem.graph.chat_agent import ChatAgent
    from HomeSystem.graph.llm_factory import list_available_vision_models
    
    try:
        # 验证图片
        if not VisionUtils.validate_image_format(image_path):
            return {"error": "不支持的图片格式"}
        
        if not VisionUtils.validate_image_size(image_path):
            return {"error": "图片文件过大"}
        
        # 获取可用模型
        vision_models = list_available_vision_models()
        if not vision_models:
            return {"error": "没有可用的视觉模型"}
        
        # 选择模型
        model = fallback_model if fallback_model in vision_models else vision_models[0]
        
        # 执行分析
        agent = ChatAgent()
        result = agent.run_with_image(image_path, prompt, model)
        
        return {"success": True, "result": result, "model": model}
        
    except Exception as e:
        return {"error": f"分析失败: {str(e)}"}

# 使用示例
result = safe_vision_analysis("image.jpg", "描述图片内容")
if result.get("success"):
    print(f"分析结果: {result['result']}")
else:
    print(f"错误: {result['error']}")
```

### 4. 性能优化

```python
def batch_vision_analysis_optimized(image_paths, prompt, batch_size=5):
    """优化的批量图片分析"""
    import concurrent.futures
    from threading import Lock
    
    agent = ChatAgent()
    results = []
    lock = Lock()
    
    def analyze_single(image_path):
        try:
            result = agent.run_with_image(image_path, prompt)
            with lock:
                results.append({
                    'path': image_path,
                    'status': 'success',
                    'result': result
                })
        except Exception as e:
            with lock:
                results.append({
                    'path': image_path,
                    'status': 'error',
                    'error': str(e)
                })
    
    # 并发处理（注意：根据模型性能调整并发数）
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        executor.map(analyze_single, image_paths)
    
    return results
```

### 5. 内存管理

```python
def memory_efficient_vision_processing(large_image_path):
    """内存高效的大图片处理"""
    from PIL import Image
    import tempfile
    import os
    
    # 使用临时文件避免内存占用过大
    with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp_file:
        try:
            # 分块处理大图片
            with Image.open(large_image_path) as img:
                # 计算合适的尺寸
                max_size = (2048, 2048)
                img.thumbnail(max_size, Image.Resampling.LANCZOS)
                
                # 保存到临时文件
                img.save(tmp_file.name, "JPEG", quality=85)
            
            # 使用临时文件进行分析
            agent = ChatAgent()
            result = agent.run_with_image(tmp_file.name, "分析图片")
            
            return result
            
        finally:
            # 清理临时文件
            if os.path.exists(tmp_file.name):
                os.unlink(tmp_file.name)
```

## 总结

HomeSystem的视觉功能提供了强大而安全的图片处理能力：

- **本地处理**：确保敏感图片数据不离开本地环境
- **云端安全**：云端模型严格限制为纯文本，防止数据泄露
- **易于使用**：简洁的API和丰富的示例代码
- **高度可配置**：支持多种图片格式和自定义处理选项
- **完善错误处理**：友好的错误提示和故障排除指导

通过本指南，您可以充分利用HomeSystem的视觉功能，为您的应用添加强大的图片理解能力。