#!/usr/bin/env python3
"""
VLAS论文快速分析脚本

快速生成VLAS论文的基本分析报告，跳过复杂的多轮迭代，直接使用现有的论文分析工具。
"""

import sys
import os
from pathlib import Path
from loguru import logger

# 添加项目路径
sys.path.append('/mnt/nfs_share/code/homesystem')

from HomeSystem.graph.tool.paper_analysis_tools import create_paper_analysis_tools
from HomeSystem.graph.llm_factory import get_llm
from HomeSystem.graph.parser.paper_folder_parser import create_paper_folder_parser


def quick_analyze_vlas():
    """快速分析VLAS论文"""
    
    paper_folder = "/mnt/nfs_share/code/homesystem/data/paper_analyze/2502.13508"
    
    if not os.path.exists(paper_folder):
        logger.error(f"论文文件夹不存在: {paper_folder}")
        return
    
    logger.info("🚀 开始VLAS论文快速分析")
    logger.info(f"📁 分析文件夹: {paper_folder}")
    
    try:
        # 1. 解析论文文件夹
        logger.info("📖 解析论文文件夹...")
        parser = create_paper_folder_parser(paper_folder)
        folder_data = parser.parse_folder()
        
        paper_text = folder_data["paper_text"]
        logger.info(f"📄 论文文本长度: {len(paper_text)} 字符")
        logger.info(f"🖼️ 可用图片: {len(folder_data['available_images'])} 张")
        
        # 2. 创建LLM分析工具
        logger.info("🤖 初始化分析工具...")
        llm = get_llm("deepseek.DeepSeek_V3")
        analysis_tools = create_paper_analysis_tools(llm)
        
        # 3. 执行各项分析
        results = {}
        
        # 背景和目标分析
        logger.info("🔍 分析研究背景和目标...")
        background_tool = analysis_tools[0]  # BackgroundObjectivesTool
        background_result = background_tool.invoke({"paper_text": paper_text})
        results["background_objectives"] = background_result
        logger.info("✅ 背景和目标分析完成")
        
        # 方法和发现分析
        logger.info("⚙️ 分析研究方法和主要发现...")
        methods_tool = analysis_tools[1]  # MethodsFindingsTool
        methods_result = methods_tool.invoke({"paper_text": paper_text})
        results["methods_findings"] = methods_result
        logger.info("✅ 方法和发现分析完成")
        
        # 结论和未来工作分析
        logger.info("📊 分析结论和未来工作...")
        conclusions_tool = analysis_tools[2]  # ConclusionsFutureTool
        conclusions_result = conclusions_tool.invoke({"paper_text": paper_text})
        results["conclusions_future"] = conclusions_result
        logger.info("✅ 结论和未来工作分析完成")
        
        # 提取关键词
        logger.info("🏷️ 提取关键词...")
        import json
        
        # 解析之前的结果
        bg_data = json.loads(background_result) if isinstance(background_result, str) else background_result
        methods_data = json.loads(methods_result) if isinstance(methods_result, str) else methods_result
        conclusions_data = json.loads(conclusions_result) if isinstance(conclusions_result, str) else conclusions_result
        
        keywords_tool = analysis_tools[3]  # KeywordsSynthesisTool
        keywords_result = keywords_tool.invoke({
            "research_background": bg_data.get("research_background", ""),
            "research_objectives": bg_data.get("research_objectives", ""),
            "methods": methods_data.get("methods", ""),
            "key_findings": methods_data.get("key_findings", ""),
            "conclusions": conclusions_data.get("conclusions", "")
        })
        results["keywords"] = keywords_result
        logger.info("✅ 关键词提取完成")
        
        # 4. 生成分析报告
        logger.info("📝 生成分析报告...")
        report_content = generate_analysis_report(results)
        
        # 5. 保存报告
        output_path = os.path.join(paper_folder, "VLAS_快速分析报告.md")
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        logger.info("="*60)
        logger.info("✅ 快速分析完成！")
        logger.info(f"📄 报告已保存到: {output_path}")
        logger.info(f"📊 报告长度: {len(report_content)} 字符")
        logger.info("="*60)
        
        # 显示报告预览
        print("\n" + "="*60)
        print("📝 VLAS论文分析报告预览:")
        print("="*60)
        
        # 显示报告的前500字符
        preview = report_content[:500] + "..." if len(report_content) > 500 else report_content
        print(preview)
        
        return output_path
        
    except Exception as e:
        logger.error(f"❌ 快速分析失败: {str(e)}")
        logger.exception("详细错误信息:")
        return None


def generate_analysis_report(results):
    """生成分析报告"""
    import json
    from datetime import datetime
    
    # 解析分析结果
    bg_data = json.loads(results["background_objectives"]) if isinstance(results["background_objectives"], str) else results["background_objectives"]
    methods_data = json.loads(results["methods_findings"]) if isinstance(results["methods_findings"], str) else results["methods_findings"]
    conclusions_data = json.loads(results["conclusions_future"]) if isinstance(results["conclusions_future"], str) else results["conclusions_future"]
    keywords_data = json.loads(results["keywords"]) if isinstance(results["keywords"], str) else results["keywords"]
    
    report = f"""# VLAS: Vision-Language-Action Model with Speech Instructions - 深度分析报告

**论文标题**: VLAS: VISION-LANGUAGE-ACTION MODEL WITH SPEECH INSTRUCTIONS FOR CUSTOMIZED ROBOT MANIPULATION

**分析时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

**分析概要**: 本报告对VLAS论文进行了深度分析，涵盖研究背景、技术方法、主要贡献和未来发展方向。

---

## 📋 执行摘要

VLAS是首个直接支持语音指令的视觉-语言-动作模型，专为定制化机器人操作而设计。该研究通过端到端的语音识别集成，解决了传统VLA模型仅支持文本指令的局限性，为更自然的人机交互开辟了新途径。

---

## 🎯 研究背景与目标

### 研究背景
{bg_data.get('research_background', '暂无数据')}

### 研究目标  
{bg_data.get('research_objectives', '暂无数据')}

---

## ⚙️ 技术方法与创新

### 研究方法
{methods_data.get('methods', '暂无数据')}

### 主要发现
{methods_data.get('key_findings', '暂无数据')}

---

## 📊 结论与展望

### 主要结论
{conclusions_data.get('conclusions', '暂无数据')}

### 研究局限性
{conclusions_data.get('limitations', '暂无数据')}

### 未来工作方向
{conclusions_data.get('future_work', '暂无数据')}

---

## 🏷️ 关键词

{', '.join(keywords_data.get('keywords', [])) if keywords_data.get('keywords') else '暂无关键词'}

---

## 🔍 技术评估

### 创新点评价
1. **端到端语音集成**: 首次在VLA模型中实现直接语音指令处理，避免了传统ASR系统的复杂性
2. **个性化定制**: 通过Voice RAG技术支持基于个人特征的定制化操作
3. **多模态融合**: 有效结合视觉、语言和语音模态，提升了人机交互的自然性

### 技术影响
- **学术价值**: 为VLA模型发展开辟了新的研究方向
- **应用潜力**: 在家庭护理、个人助理等领域具有广阔应用前景
- **技术突破**: 解决了语音信息丢失和系统复杂性问题

### 局限性分析
- 依赖于语音数据的质量和多样性
- 在嘈杂环境下的鲁棒性有待验证
- 计算复杂度可能限制实时应用

---

## 📈 研究意义

本研究在视觉-语言-动作模型领域取得了重要突破，特别是在语音指令集成方面。VLAS模型不仅提升了人机交互的自然性，还为个性化机器人服务奠定了技术基础。该工作对未来智能机器人的发展具有重要指导意义。

---

**报告生成工具**: HomeSystem深度论文分析系统  
**分析模型**: DeepSeek V3  
**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    
    return report


if __name__ == "__main__":
    quick_analyze_vlas()