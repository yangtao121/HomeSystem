#!/usr/bin/env python3
"""
快速翻译对比测试脚本
"""

import sys
import os
import time
import asyncio
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from HomeSystem.workflow.paper_gather_task.llm_config import TranslationLLM

# 测试文本（简短版本）
TEST_TEXT = """Deep learning models have achieved remarkable success in various computer vision tasks. However, their black-box nature makes it difficult to understand the reasoning behind their predictions. This limitation is particularly concerning in safety-critical applications such as medical diagnosis and autonomous driving."""

async def compare_translation():
    """快速对比翻译效果"""
    print("🔍 翻译对比测试")
    print("=" * 80)
    print(f"📝 原文:")
    print(f"{TEST_TEXT}")
    print("=" * 80)
    
    # 本地模型
    print("\n🖥️  本地模型翻译 (ollama.Qwen3_30B):")
    try:
        local_translator = TranslationLLM(model_name="ollama.Qwen3_30B")
        local_start = time.time()
        local_result = local_translator.translate_text(TEST_TEXT)
        local_time = time.time() - local_start
        
        print(f"⏱️  翻译时间: {local_time:.2f}秒")
        print(f"🎯 翻译质量: {local_result.translation_quality}")
        print(f"📖 中文翻译:")
        print(f"{local_result.translated_text}")
        if local_result.notes:
            print(f"📝 注释: {local_result.notes}")
        
    except Exception as e:
        print(f"❌ 本地模型翻译失败: {e}")
        local_time = 0
    
    print("-" * 80)
    
    # 云端模型
    print("\n☁️  云端模型翻译 (deepseek.DeepSeek_V3):")
    try:
        cloud_translator = TranslationLLM(model_name="deepseek.DeepSeek_V3")
        cloud_start = time.time()
        cloud_result = cloud_translator.translate_text(TEST_TEXT)
        cloud_time = time.time() - cloud_start
        
        print(f"⏱️  翻译时间: {cloud_time:.2f}秒")
        print(f"🎯 翻译质量: {cloud_result.translation_quality}")
        print(f"📖 中文翻译:")
        print(f"{cloud_result.translated_text}")
        if cloud_result.notes:
            print(f"📝 注释: {cloud_result.notes}")
            
    except Exception as e:
        print(f"❌ 云端模型翻译失败: {e}")
        cloud_time = 0
    
    # 对比结果
    if local_time > 0 and cloud_time > 0:
        print("\n" + "=" * 80)
        print("📊 对比结果:")
        if local_time < cloud_time:
            speedup = cloud_time / local_time
            print(f"🚀 本地模型更快 {speedup:.2f}x ({local_time:.2f}s vs {cloud_time:.2f}s)")
        else:
            speedup = local_time / cloud_time
            print(f"☁️  云端模型更快 {speedup:.2f}x ({cloud_time:.2f}s vs {local_time:.2f}s)")
        print("=" * 80)

if __name__ == "__main__":
    asyncio.run(compare_translation())