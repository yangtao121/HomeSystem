#!/usr/bin/env python3
"""
翻译质量对比测试脚本
对比本地模型（Ollama）和云端模型（DeepSeek）的翻译效果
"""

import sys
import os
import time
import asyncio
from pathlib import Path

# 添加路径以导入HomeSystem模块
sys.path.append(str(Path(__file__).parent.parent))

from HomeSystem.workflow.paper_gather_task.llm_config import TranslationLLM
from HomeSystem.graph.llm_factory import llm_factory
from loguru import logger

# 配置日志
logger.remove()
logger.add(sys.stdout, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}")


class TranslationComparison:
    """翻译对比测试类"""
    
    def __init__(self):
        # 初始化本地模型和云端模型
        self.local_model = "ollama.Qwen3_30B"  # 本地模型
        self.cloud_model = "deepseek.DeepSeek_V3"  # 云端模型
        
        logger.info("初始化翻译对比测试...")
        
    def create_translators(self):
        """创建翻译器实例"""
        try:
            # 创建本地翻译器
            logger.info(f"创建本地翻译器: {self.local_model}")
            self.local_translator = TranslationLLM(model_name=self.local_model)
            
            # 创建云端翻译器
            logger.info(f"创建云端翻译器: {self.cloud_model}")
            self.cloud_translator = TranslationLLM(model_name=self.cloud_model)
            
            logger.info("翻译器创建成功")
            return True
            
        except Exception as e:
            logger.error(f"翻译器创建失败: {e}")
            return False
    
    def get_test_texts(self):
        """获取测试文本（模拟论文字段内容）"""
        return [
            {
                "field": "research_background",
                "text": "Machine learning has revolutionized various domains, including computer vision, natural language processing, and robotics. However, the interpretability of deep neural networks remains a significant challenge. Recent advances in explainable AI have focused on developing methods to understand and visualize the decision-making process of complex models."
            },
            {
                "field": "research_objectives", 
                "text": "This study aims to develop a novel framework for enhancing the interpretability of convolutional neural networks in image classification tasks. We propose a gradient-based attribution method that can identify the most influential regions in input images that contribute to the model's predictions."
            },
            {
                "field": "methods",
                "text": "We implement a multi-scale gradient analysis approach combined with attention mechanisms. The method involves computing gradients at multiple layers of the CNN, applying Gaussian filters for noise reduction, and using attention weights to highlight salient features. We evaluate our approach on three benchmark datasets: CIFAR-10, ImageNet, and a custom medical imaging dataset."
            },
            {
                "field": "key_findings",
                "text": "Our experimental results demonstrate that the proposed method achieves 15% improvement in interpretability metrics compared to existing techniques such as GradCAM and LIME. The method successfully identifies relevant image regions with 92% accuracy on the medical imaging dataset, significantly outperforming baseline approaches."
            },
            {
                "field": "conclusions",
                "text": "The proposed gradient-based attribution framework provides more accurate and reliable explanations for CNN decisions in image classification. This advancement has important implications for safety-critical applications such as medical diagnosis and autonomous driving, where model interpretability is crucial for trust and adoption."
            }
        ]
    
    async def compare_single_translation(self, test_item):
        """对比单个文本的翻译效果"""
        field = test_item["field"]
        text = test_item["text"]
        
        logger.info(f"\n{'='*80}")
        logger.info(f"🔍 正在翻译字段: {field}")
        logger.info(f"📝 原文:")
        logger.info(f"{text}")
        logger.info(f"{'='*80}")
        
        results = {}
        
        # 本地模型翻译
        try:
            logger.info(f"🖥️  使用本地模型翻译 ({self.local_model})")
            local_start = time.time()
            local_result = self.local_translator.translate_text(text)
            local_time = time.time() - local_start
            
            results["local"] = {
                "model": self.local_model,
                "result": local_result,
                "time": local_time
            }
            
            logger.info(f"✅ 本地翻译完成，耗时: {local_time:.2f}秒")
            
        except Exception as e:
            logger.error(f"❌ 本地模型翻译失败: {e}")
            results["local"] = {"error": str(e)}
        
        # 云端模型翻译
        try:
            logger.info(f"☁️  使用云端模型翻译 ({self.cloud_model})")
            cloud_start = time.time()
            cloud_result = self.cloud_translator.translate_text(text)
            cloud_time = time.time() - cloud_start
            
            results["cloud"] = {
                "model": self.cloud_model,
                "result": cloud_result,
                "time": cloud_time
            }
            
            logger.info(f"✅ 云端翻译完成，耗时: {cloud_time:.2f}秒")
            
        except Exception as e:
            logger.error(f"❌ 云端模型翻译失败: {e}")
            results["cloud"] = {"error": str(e)}
        
        # 显示翻译结果对比
        self.display_comparison(field, text, results)
        
        return results
    
    def display_comparison(self, field, original_text, results):
        """显示翻译结果对比"""
        print(f"\n{'🔍 翻译结果对比':<30}")
        print("=" * 100)
        print(f"📋 字段: {field}")
        print(f"📝 原文: {original_text[:100]}{'...' if len(original_text) > 100 else ''}")
        print("-" * 100)
        
        # 本地模型结果
        if "local" in results and "result" in results["local"]:
            local_result = results["local"]["result"]
            local_time = results["local"]["time"]
            print(f"🖥️  本地模型 ({self.local_model}):")
            print(f"   ⏱️  翻译时间: {local_time:.2f}秒")
            print(f"   🎯 翻译质量: {local_result.translation_quality}")
            print(f"   📖 中文翻译:")
            print(f"   {local_result.translated_text}")
            if local_result.notes:
                print(f"   📝 翻译注释: {local_result.notes}")
        elif "local" in results:
            print(f"🖥️  本地模型 ({self.local_model}): ❌ 翻译失败 - {results['local'].get('error', '未知错误')}")
        
        print("-" * 50)
        
        # 云端模型结果
        if "cloud" in results and "result" in results["cloud"]:
            cloud_result = results["cloud"]["result"]
            cloud_time = results["cloud"]["time"]
            print(f"☁️  云端模型 ({self.cloud_model}):")
            print(f"   ⏱️  翻译时间: {cloud_time:.2f}秒")
            print(f"   🎯 翻译质量: {cloud_result.translation_quality}")
            print(f"   📖 中文翻译:")
            print(f"   {cloud_result.translated_text}")
            if cloud_result.notes:
                print(f"   📝 翻译注释: {cloud_result.notes}")
        elif "cloud" in results:
            print(f"☁️  云端模型 ({self.cloud_model}): ❌ 翻译失败 - {results['cloud'].get('error', '未知错误')}")
        
        # 性能对比
        if ("local" in results and "cloud" in results and 
            "result" in results["local"] and "result" in results["cloud"]):
            
            local_time = results["local"]["time"]
            cloud_time = results["cloud"]["time"]
            
            print("-" * 50)
            print("📊 性能对比:")
            if local_time < cloud_time:
                speedup = cloud_time / local_time
                print(f"   🚀 本地模型更快 {speedup:.2f}x")
            else:
                speedup = local_time / cloud_time
                print(f"   ☁️  云端模型更快 {speedup:.2f}x")
            
            print(f"   📈 时间差: {abs(local_time - cloud_time):.2f}秒")
        
        print("=" * 100)
    
    async def run_comparison(self):
        """运行完整的翻译对比测试"""
        logger.info("🚀 开始翻译质量对比测试")
        
        # 创建翻译器
        if not self.create_translators():
            logger.error("翻译器创建失败，退出测试")
            return
        
        # 获取测试文本
        test_texts = self.get_test_texts()
        logger.info(f"📚 准备测试 {len(test_texts)} 个字段的翻译")
        
        all_results = []
        total_start_time = time.time()
        
        # 逐个进行翻译对比
        for i, test_item in enumerate(test_texts, 1):
            logger.info(f"\n🔄 进行第 {i}/{len(test_texts)} 个翻译对比...")
            result = await self.compare_single_translation(test_item)
            all_results.append({
                "field": test_item["field"],
                "original": test_item["text"],
                "results": result
            })
            
            # 添加间隔，避免API调用过快
            if i < len(test_texts):
                await asyncio.sleep(1)
        
        total_time = time.time() - total_start_time
        
        # 生成总结报告
        self.generate_summary_report(all_results, total_time)
    
    def generate_summary_report(self, all_results, total_time):
        """生成总结报告"""
        print(f"\n{'📊 翻译对比总结报告':<50}")
        print("=" * 120)
        
        local_successes = 0
        cloud_successes = 0
        local_total_time = 0
        cloud_total_time = 0
        quality_comparison = {"local": [], "cloud": []}
        
        for item in all_results:
            results = item["results"]
            
            # 统计成功率
            if "local" in results and "result" in results["local"]:
                local_successes += 1
                local_total_time += results["local"]["time"]
                quality_comparison["local"].append(results["local"]["result"].translation_quality)
            
            if "cloud" in results and "result" in results["cloud"]:
                cloud_successes += 1
                cloud_total_time += results["cloud"]["time"]
                quality_comparison["cloud"].append(results["cloud"]["result"].translation_quality)
        
        total_tests = len(all_results)
        
        print(f"📈 性能统计:")
        print(f"   🖥️  本地模型 ({self.local_model}):")
        print(f"      ✅ 成功率: {local_successes}/{total_tests} ({local_successes/total_tests*100:.1f}%)")
        if local_successes > 0:
            print(f"      ⏱️  平均时间: {local_total_time/local_successes:.2f}秒")
            local_quality_dist = {q: quality_comparison['local'].count(q) for q in set(quality_comparison['local'])}
            print(f"      🎯 质量分布: {local_quality_dist}")
        
        print(f"   ☁️  云端模型 ({self.cloud_model}):")
        print(f"      ✅ 成功率: {cloud_successes}/{total_tests} ({cloud_successes/total_tests*100:.1f}%)")
        if cloud_successes > 0:
            print(f"      ⏱️  平均时间: {cloud_total_time/cloud_successes:.2f}秒")
            cloud_quality_dist = {q: quality_comparison['cloud'].count(q) for q in set(quality_comparison['cloud'])}
            print(f"      🎯 质量分布: {cloud_quality_dist}")
        
        # 整体对比
        if local_successes > 0 and cloud_successes > 0:
            avg_local_time = local_total_time / local_successes
            avg_cloud_time = cloud_total_time / cloud_successes
            
            print(f"\n🏆 整体对比:")
            if avg_local_time < avg_cloud_time:
                speedup = avg_cloud_time / avg_local_time
                print(f"   🚀 本地模型平均速度更快 {speedup:.2f}x")
            else:
                speedup = avg_local_time / avg_cloud_time
                print(f"   ☁️  云端模型平均速度更快 {speedup:.2f}x")
        
        print(f"\n⏱️  总测试时间: {total_time:.2f}秒")
        print(f"📊 测试完成: {total_tests} 个字段翻译对比")
        print("=" * 120)


async def main():
    """主函数"""
    try:
        logger.info("🎯 启动翻译质量对比测试")
        
        # 检查模型可用性
        logger.info("🔍 检查可用模型...")
        available_models = llm_factory.get_available_llm_models()
        logger.info(f"📋 可用模型: {available_models}")
        
        # 创建对比测试实例
        comparison = TranslationComparison()
        
        # 运行对比测试
        await comparison.run_comparison()
        
        logger.info("✅ 翻译对比测试完成")
        
    except KeyboardInterrupt:
        logger.info("❌ 用户中断测试")
    except Exception as e:
        logger.error(f"❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # 运行异步主函数
    asyncio.run(main())