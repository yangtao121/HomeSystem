#!/usr/bin/env python3
"""
HomeSystem视觉功能使用示例

这个示例展示了如何使用HomeSystem的视觉功能：
1. 检查可用的视觉模型
2. 验证图片支持
3. 使用图片进行AI对话
4. 处理云端模型的限制

使用前确保：
1. 已安装Ollama并下载了qwen2.5vl:7b模型
2. 准备了测试图片文件
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.append(str(Path(__file__).parent.parent))

from loguru import logger
from HomeSystem.graph.llm_factory import (
    LLMFactory, 
    list_available_vision_models, 
    check_vision_support,
    validate_vision_input
)
from HomeSystem.graph.vision_utils import (
    VisionUtils, 
    check_image_support, 
    get_supported_formats
)
from HomeSystem.graph.chat_agent import ChatAgent


def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("HomeSystem视觉功能演示")
    logger.info("=" * 60)
    
    # 1. 检查可用的视觉模型
    logger.info("\n🔍 检查可用的视觉模型...")
    vision_models = list_available_vision_models()
    
    if not vision_models:
        logger.error("❌ 没有找到支持视觉的模型！")
        logger.info("请确保安装了Ollama并下载了视觉模型，例如：")
        logger.info("ollama pull qwen2.5vl:7b")
        return
    
    logger.info("✅ 找到以下视觉模型：")
    for model in vision_models:
        logger.info(f"  - {model}")
    
    # 2. 演示模型视觉支持检查
    logger.info("\n🔍 检查模型视觉支持...")
    
    # 测试本地视觉模型
    test_vision_model = "ollama.Qwen2_5_VL_7B"
    if check_vision_support(test_vision_model):
        logger.info(f"✅ {test_vision_model} 支持视觉功能")
    else:
        logger.warning(f"⚠️ {test_vision_model} 不支持视觉功能")
    
    # 测试云端模型（应该不支持）
    test_cloud_model = "deepseek.DeepSeek_V3"
    try:
        validate_vision_input(test_cloud_model)
        logger.warning(f"⚠️ {test_cloud_model} 意外支持视觉？")
    except ValueError as e:
        logger.info(f"✅ {test_cloud_model} 正确拒绝视觉输入: {e}")
    
    # 3. 检查图片格式支持
    logger.info(f"\n📷 支持的图片格式: {', '.join(get_supported_formats())}")
    
    # 4. 寻找测试图片
    logger.info("\n🔍 寻找测试图片...")
    test_image_paths = [
        "test_image.jpg",
        "test_image.png", 
        "sample.jpg",
        "sample.png",
        "/tmp/test.jpg",
        Path.home() / "Pictures" / "test.jpg"
    ]
    
    test_image = None
    for img_path in test_image_paths:
        if Path(img_path).exists():
            if check_image_support(img_path):
                test_image = img_path
                logger.info(f"✅ 找到测试图片: {img_path}")
                break
            else:
                logger.warning(f"⚠️ 图片格式不支持: {img_path}")
    
    if not test_image:
        logger.warning("⚠️ 没有找到测试图片，创建一个示例图片...")
        create_sample_image()
        test_image = "sample_test.jpg"
    
    # 5. 获取图片信息
    if test_image and Path(test_image).exists():
        logger.info("\n📊 图片信息:")
        image_info = VisionUtils.get_image_info(test_image)
        for key, value in image_info.items():
            logger.info(f"  {key}: {value}")
    
    # 6. 演示视觉功能使用
    if test_image and Path(test_image).exists() and vision_models:
        logger.info(f"\n🤖 使用视觉模型分析图片: {test_image}")
        try:
            # 创建聊天Agent
            agent = ChatAgent()

            logger.info(f"vision_models: {vision_models}")
            
            # 使用图片进行单次查询
            result = agent.run_with_image(
                image_path=test_image,
                text="请描述这张图片的内容。",
                model_name=vision_models[0]  # 使用第一个可用的视觉模型
            )
            
            logger.info("🎯 AI分析结果:")
            logger.info(result)
            
        except Exception as e:
            logger.error(f"❌ 视觉功能测试失败: {e}")
    
    # 7. 演示错误处理
    logger.info("\n🧪 演示错误处理...")
    try:
        # 尝试用云端模型处理图片（应该失败）
        validate_vision_input("deepseek.DeepSeek_V3")
    except ValueError as e:
        logger.info(f"✅ 正确处理云端模型限制: {e}")
    
    logger.info("\n✅ 视觉功能演示完成！")
    logger.info("\n💡 使用提示:")
    logger.info("1. 本地模型支持图片分析")
    logger.info("2. 云端模型仅支持纯文本")
    logger.info("3. 支持JPEG、PNG、WebP等常见格式")
    logger.info("4. 图片会自动调整大小以优化处理")


def create_sample_image():
    """创建一个简单的测试图片"""
    try:
        from PIL import Image, ImageDraw, ImageFont
        
        # 创建一个简单的测试图片
        img = Image.new('RGB', (400, 300), color='lightblue')
        draw = ImageDraw.Draw(img)
        
        # 绘制一些简单的形状
        draw.rectangle([50, 50, 150, 150], fill='red', outline='black', width=2)
        draw.ellipse([200, 100, 350, 200], fill='green', outline='black', width=2)
        
        # 添加文字
        try:
            # 尝试使用默认字体
            draw.text((100, 250), "HomeSystem Vision Test", fill='black')
        except:
            # 如果没有字体，使用默认的
            draw.text((100, 250), "Test Image", fill='black')
        
        # 保存图片
        img.save("sample_test.jpg", "JPEG")
        logger.info("✅ 创建了示例测试图片: sample_test.jpg")
        
    except ImportError:
        logger.warning("⚠️ PIL库未安装，无法创建测试图片")
        logger.info("请手动准备一张测试图片，或安装PIL: pip install Pillow")
    except Exception as e:
        logger.error(f"❌ 创建测试图片失败: {e}")


def interactive_vision_demo():
    """交互式视觉演示"""
    logger.info("\n🎮 交互式视觉演示")
    
    vision_models = list_available_vision_models()
    if not vision_models:
        logger.error("❌ 没有可用的视觉模型")
        return
    
    # 让用户选择图片
    image_path = input("请输入图片路径 (或按回车使用默认): ").strip()
    if not image_path:
        image_path = "sample_test.jpg"
    
    if not Path(image_path).exists():
        logger.error(f"❌ 图片文件不存在: {image_path}")
        return
    
    if not check_image_support(image_path):
        logger.error(f"❌ 不支持的图片格式: {image_path}")
        return
    
    try:
        # 创建聊天Agent并开始视觉聊天
        agent = ChatAgent()
        logger.info(f"🚀 启动视觉聊天，使用模型: {vision_models[0]}")
        agent.chat_with_image(image_path, vision_models[0])
        
    except Exception as e:
        logger.error(f"❌ 交互式演示失败: {e}")


if __name__ == "__main__":
    # 运行演示
    main()
    
    # 询问是否运行交互式演示
    if input("\n是否运行交互式视觉演示？(y/N): ").lower().startswith('y'):
        interactive_vision_demo()