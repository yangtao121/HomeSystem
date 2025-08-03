"""
Markdown格式化器 - 基于结构化状态生成专业的markdown报告

根据DeepPaperAnalysisState生成完整的学术论文分析报告，
保持LaTeX公式、图片引用格式，支持中英文双语输出。
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from loguru import logger


class MarkdownFormatter:
    """基于结构化状态生成Markdown报告的格式化器"""
    
    def __init__(self, 
                 output_language: str = "zh",
                 include_metadata: bool = True,
                 preserve_image_refs: bool = True):
        """
        初始化Markdown格式化器
        
        Args:
            output_language: 输出语言 ("zh" 或 "en")
            include_metadata: 是否包含元数据信息
            preserve_image_refs: 是否保持图片引用完整
        """
        self.output_language = output_language
        self.include_metadata = include_metadata
        self.preserve_image_refs = preserve_image_refs
        
        # 语言特定的标题模板
        self.titles = {
            "zh": {
                "main_title": "# 论文深度分析报告",
                "contributions": "## 主要贡献",
                "background": "## 研究背景",
                "methodology": "## 研究方法",
                "results": "## 实验结果",
                "image_analysis": "## 图像分析",
                "analysis_metadata": "## 分析信息",
                "errors": "## 分析过程中的问题"
            },
            "en": {
                "main_title": "# Deep Paper Analysis Report",
                "contributions": "## Main Contributions",
                "background": "## Research Background", 
                "methodology": "## Research Methodology",
                "results": "## Experimental Results",
                "image_analysis": "## Image Analysis",
                "analysis_metadata": "## Analysis Metadata",
                "errors": "## Analysis Issues"
            }
        }
        
        logger.info(f"MarkdownFormatter initialized for {output_language} output")
    
    def format_analysis_report(self, state: Dict[str, Any]) -> str:
        """
        根据状态结构生成完整的markdown报告
        
        Args:
            state: DeepPaperAnalysisState状态字典
            
        Returns:
            str: 完整的markdown报告
        """
        logger.info("开始生成markdown分析报告...")
        
        sections = []
        
        # 主标题和概述
        sections.append(self._format_title_and_overview(state))
        
        # 主要贡献部分
        if self._has_translated_content(state, "translated_contributions"):
            sections.append(self._format_contributions(state["translated_contributions"]))
        elif self._has_content(state, "main_contributions"):
            sections.append(self._format_contributions(state["main_contributions"]))
        
        # 研究背景部分
        if self._has_translated_content(state, "translated_background"):
            sections.append(self._format_background(state["translated_background"]))
        elif self._has_content(state, "background_analysis"):
            sections.append(self._format_background(state["background_analysis"]))
        
        # 研究方法部分
        if self._has_translated_content(state, "translated_methodology"):
            sections.append(self._format_methodology(state["translated_methodology"]))
        elif self._has_content(state, "methodology_analysis"):
            sections.append(self._format_methodology(state["methodology_analysis"]))
        
        # 实验结果部分
        if self._has_translated_content(state, "translated_results"):
            sections.append(self._format_results(state["translated_results"]))
        elif self._has_content(state, "experimental_results"):
            sections.append(self._format_results(state["experimental_results"]))
        
        # 图像分析部分
        if self._has_content(state, "analyzed_images"):
            sections.append(self._format_image_analysis(state["analyzed_images"]))
        
        # 元数据部分
        if self.include_metadata:
            sections.append(self._format_metadata(state))
        
        # 错误信息部分
        if state.get("analysis_errors"):
            sections.append(self._format_errors(state["analysis_errors"]))
        
        # 组合所有部分
        full_report = "\n\n".join(sections)
        
        logger.info(f"Markdown报告生成完成，总长度: {len(full_report)} 字符")
        return full_report
    
    def _has_content(self, state: Dict[str, Any], key: str) -> bool:
        """检查状态中是否有指定内容"""
        content = state.get(key)
        return content is not None and content != {}
    
    def _has_translated_content(self, state: Dict[str, Any], key: str) -> bool:
        """检查是否有翻译后的内容"""
        return (self.output_language == "zh" and 
                self._has_content(state, key))
    
    def _format_title_and_overview(self, state: Dict[str, Any]) -> str:
        """格式化标题和概述部分"""
        titles = self.titles[self.output_language]
        
        sections = [titles["main_title"]]
        
        if self.output_language == "zh":
            overview = f"""
本报告基于深度学习技术对学术论文进行全面分析，包括主要贡献、研究背景、方法论和实验结果的深入解读。

**分析概况:**
- 分析文件夹: `{state.get('base_folder_path', 'Unknown')}`
- 论文文本长度: {len(state.get('paper_text', ''))} 字符
- 可用图片数量: {len(state.get('available_images', []))} 张
- 已分析图片: {len(state.get('analyzed_images', {}))} 张
- 分析轮次: {state.get('analysis_iteration', 0)} 轮
"""
        else:
            overview = f"""
This report provides comprehensive analysis of an academic paper using deep learning technologies, including in-depth interpretation of main contributions, research background, methodology, and experimental results.

**Analysis Overview:**
- Analysis folder: `{state.get('base_folder_path', 'Unknown')}`
- Paper text length: {len(state.get('paper_text', ''))} characters
- Available images: {len(state.get('available_images', []))} images
- Analyzed images: {len(state.get('analyzed_images', {}))} images
- Analysis iterations: {state.get('analysis_iteration', 0)} rounds
"""
        
        sections.append(overview)
        return "\n".join(sections)
    
    def _format_contributions(self, contributions_data: Dict[str, Any]) -> str:
        """格式化主要贡献部分"""
        titles = self.titles[self.output_language]
        sections = [titles["contributions"]]
        
        if "contributions" in contributions_data:
            contributions = contributions_data["contributions"]
            
            for contrib in contributions:
                contrib_id = contrib.get("id", "")
                title = contrib.get("title", "")
                description = contrib.get("description", "")
                
                sections.append(f"### {contrib_id}. {title}")
                sections.append(description)
                
                # 添加其他字段（如果存在）
                if "novelty_aspect" in contrib:
                    if self.output_language == "zh":
                        sections.append(f"**创新点:** {contrib['novelty_aspect']}")
                    else:
                        sections.append(f"**Novelty Aspect:** {contrib['novelty_aspect']}")
                
                if "significance" in contrib:
                    if self.output_language == "zh":
                        sections.append(f"**重要性:** {contrib['significance']}")
                    else:
                        sections.append(f"**Significance:** {contrib['significance']}")
        
        # 添加整体评估
        if "overall_innovation_level" in contributions_data:
            if self.output_language == "zh":
                sections.append(f"**整体创新水平:** {contributions_data['overall_innovation_level']}")
            else:
                sections.append(f"**Overall Innovation Level:** {contributions_data['overall_innovation_level']}")
        
        return "\n\n".join(sections)
    
    def _format_background(self, background_data: Dict[str, Any]) -> str:
        """格式化研究背景部分"""
        titles = self.titles[self.output_language]
        sections = [titles["background"]]
        
        # 问题背景
        if "problem_context" in background_data:
            context = background_data["problem_context"]
            if self.output_language == "zh":
                sections.append("### 问题背景")
            else:
                sections.append("### Problem Context")
            
            if isinstance(context, dict):
                if "problem_statement" in context:
                    sections.append(context["problem_statement"])
                if "problem_significance" in context:
                    sections.append(context["problem_significance"])
            else:
                sections.append(str(context))
        
        # 研究动机
        if "research_motivation" in background_data:
            motivation = background_data["research_motivation"]
            if self.output_language == "zh":
                sections.append("### 研究动机")
            else:
                sections.append("### Research Motivation")
            
            if isinstance(motivation, dict):
                if "driving_factors" in motivation:
                    factors = motivation["driving_factors"]
                    if isinstance(factors, list):
                        for factor in factors:
                            sections.append(f"- {factor}")
                    else:
                        sections.append(str(factors))
            else:
                sections.append(str(motivation))
        
        # 相关工作
        if "related_work" in background_data:
            related = background_data["related_work"]
            if self.output_language == "zh":
                sections.append("### 相关工作")
            else:
                sections.append("### Related Work")
            
            if isinstance(related, dict):
                if "positioning" in related:
                    sections.append(related["positioning"])
            else:
                sections.append(str(related))
        
        return "\n\n".join(sections)
    
    def _format_methodology(self, methodology_data: Dict[str, Any]) -> str:
        """格式化方法论部分，支持层次结构"""
        titles = self.titles[self.output_language]
        sections = [titles["methodology"]]
        
        # 整体方法
        if "overall_approach" in methodology_data:
            approach = methodology_data["overall_approach"]
            if self.output_language == "zh":
                sections.append("### 整体方法")
            else:
                sections.append("### Overall Approach")
            
            if isinstance(approach, dict):
                if "framework" in approach:
                    sections.append(approach["framework"])
            else:
                sections.append(str(approach))
        
        # 技术方法（支持子章节）
        if "technical_methods" in methodology_data:
            methods = methodology_data["technical_methods"]
            if self.output_language == "zh":
                sections.append("### 技术方法")
            else:
                sections.append("### Technical Methods")
            
            if isinstance(methods, dict) and "subsections" in methods:
                for subsection in methods["subsections"]:
                    if isinstance(subsection, dict):
                        title = subsection.get("title", "")
                        content = subsection.get("content", "")
                        
                        sections.append(f"#### {title}")
                        sections.append(content)
                        
                        # 处理图片引用
                        if "image_references" in subsection and self.preserve_image_refs:
                            for img_ref in subsection["image_references"]:
                                if isinstance(img_ref, dict):
                                    path = img_ref.get("path", "")
                                    desc = img_ref.get("description", "")
                                    sections.append(f"![{desc}]({path})")
            else:
                sections.append(str(methods))
        
        # 实现细节
        if "implementation_details" in methodology_data:
            impl = methodology_data["implementation_details"]
            if self.output_language == "zh":
                sections.append("### 实现细节")
            else:
                sections.append("### Implementation Details")
            
            if isinstance(impl, dict):
                if "algorithms" in impl:
                    algorithms = impl["algorithms"]
                    if isinstance(algorithms, list):
                        for algo in algorithms:
                            sections.append(f"- {algo}")
                    else:
                        sections.append(str(algorithms))
            else:
                sections.append(str(impl))
        
        return "\n\n".join(sections)
    
    def _format_results(self, results_data: Dict[str, Any]) -> str:
        """格式化实验结果部分"""
        titles = self.titles[self.output_language]
        sections = [titles["results"]]
        
        # 实验设计
        if "experimental_design" in results_data:
            design = results_data["experimental_design"]
            if self.output_language == "zh":
                sections.append("### 实验设计")
            else:
                sections.append("### Experimental Design")
            
            if isinstance(design, dict):
                if "datasets_used" in design:
                    datasets = design["datasets_used"]
                    if isinstance(datasets, list):
                        if self.output_language == "zh":
                            sections.append("**使用的数据集:**")
                        else:
                            sections.append("**Datasets Used:**")
                        for dataset in datasets:
                            sections.append(f"- {dataset}")
            else:
                sections.append(str(design))
        
        # 关键结果
        if "key_results" in results_data:
            results = results_data["key_results"]
            if self.output_language == "zh":
                sections.append("### 关键结果")
            else:
                sections.append("### Key Results")
            
            if isinstance(results, dict):
                # 定量结果
                if "quantitative_results" in results:
                    quant_results = results["quantitative_results"]
                    if isinstance(quant_results, list):
                        if self.output_language == "zh":
                            sections.append("**定量结果:**")
                        else:
                            sections.append("**Quantitative Results:**")
                        
                        for result in quant_results:
                            if isinstance(result, dict):
                                metric = result.get("metric", "")
                                value = result.get("value", "")
                                improvement = result.get("improvement", "")
                                
                                result_line = f"- **{metric}**: {value}"
                                if improvement:
                                    result_line += f" ({improvement})"
                                sections.append(result_line)
                
                # 定性发现
                if "qualitative_findings" in results:
                    qual_findings = results["qualitative_findings"]
                    if isinstance(qual_findings, list):
                        if self.output_language == "zh":
                            sections.append("**定性发现:**")
                        else:
                            sections.append("**Qualitative Findings:**")
                        for finding in qual_findings:
                            sections.append(f"- {finding}")
            else:
                sections.append(str(results))
        
        return "\n\n".join(sections)
    
    def _format_image_analysis(self, analyzed_images: Dict[str, Any]) -> str:
        """格式化图像分析部分"""
        titles = self.titles[self.output_language]
        sections = [titles["image_analysis"]]
        
        for image_path, analysis_data in analyzed_images.items():
            # 图片标题
            sections.append(f"### {image_path}")
            
            if isinstance(analysis_data, dict):
                # 分析查询
                if "analysis_query" in analysis_data:
                    if self.output_language == "zh":
                        sections.append(f"**分析要求:** {analysis_data['analysis_query']}")
                    else:
                        sections.append(f"**Analysis Query:** {analysis_data['analysis_query']}")
                
                # 分析结果
                if "analysis_result" in analysis_data:
                    if self.output_language == "zh":
                        sections.append("**分析结果:**")
                    else:
                        sections.append("**Analysis Result:**")
                    sections.append(analysis_data["analysis_result"])
                
                # 显示图片（如果保持引用）
                if self.preserve_image_refs:
                    sections.append(f"![{image_path}]({image_path})")
            else:
                sections.append(str(analysis_data))
        
        return "\n\n".join(sections)
    
    def _format_metadata(self, state: Dict[str, Any]) -> str:
        """格式化分析元数据"""
        titles = self.titles[self.output_language]
        sections = [titles["analysis_metadata"]]
        
        metadata_info = []
        
        # 分析时间
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if self.output_language == "zh":
            metadata_info.append(f"**报告生成时间:** {current_time}")
            metadata_info.append(f"**分析轮次:** {state.get('analysis_iteration', 0)}")
            metadata_info.append(f"**完成任务数:** {len(state.get('completed_tasks', []))}")
        else:
            metadata_info.append(f"**Report Generated:** {current_time}")
            metadata_info.append(f"**Analysis Iterations:** {state.get('analysis_iteration', 0)}")
            metadata_info.append(f"**Completed Tasks:** {len(state.get('completed_tasks', []))}")
        
        # 分析状态
        analysis_complete = state.get('is_analysis_complete', False)
        translation_complete = state.get('is_translation_complete', False)
        
        if self.output_language == "zh":
            metadata_info.append(f"**分析完成状态:** {'✅ 已完成' if analysis_complete else '❌ 未完成'}")
            metadata_info.append(f"**翻译完成状态:** {'✅ 已完成' if translation_complete else '❌ 未完成'}")
        else:
            metadata_info.append(f"**Analysis Complete:** {'✅ Yes' if analysis_complete else '❌ No'}")
            metadata_info.append(f"**Translation Complete:** {'✅ Yes' if translation_complete else '❌ No'}")
        
        # 完成的任务列表
        completed_tasks = state.get('completed_tasks', [])
        if completed_tasks:
            if self.output_language == "zh":
                metadata_info.append("**已完成的任务:**")
            else:
                metadata_info.append("**Completed Tasks:**")
            for task in completed_tasks:
                metadata_info.append(f"- {task}")
        
        sections.extend(metadata_info)
        return "\n\n".join(sections)
    
    def _format_errors(self, errors: List[str]) -> str:
        """格式化错误信息"""
        titles = self.titles[self.output_language]
        sections = [titles["errors"]]
        
        if self.output_language == "zh":
            sections.append("以下是分析过程中遇到的问题：")
        else:
            sections.append("The following issues were encountered during analysis:")
        
        for error in errors:
            sections.append(f"- {error}")
        
        return "\n\n".join(sections)
    
    def save_report(self, report_content: str, output_path: str) -> bool:
        """
        保存报告到文件
        
        Args:
            report_content: 报告内容
            output_path: 输出文件路径
            
        Returns:
            bool: 是否保存成功
        """
        try:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(report_content)
            
            logger.info(f"报告已保存到: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"报告保存失败: {e}")
            return False


def create_markdown_formatter(output_language: str = "zh") -> MarkdownFormatter:
    """创建Markdown格式化器的便捷函数"""
    return MarkdownFormatter(output_language=output_language)


# 测试代码
if __name__ == "__main__":
    # 测试格式化器
    formatter = create_markdown_formatter("zh")
    
    # 模拟状态数据
    test_state = {
        "base_folder_path": "/test/paper",
        "paper_text": "Test paper content...",
        "available_images": ["img1.jpg", "img2.jpg"],
        "analyzed_images": {
            "img1.jpg": {
                "analysis_query": "Analyze this diagram",
                "analysis_result": "This is a system architecture diagram..."
            }
        },
        "main_contributions": {
            "contributions": [
                {
                    "id": 1,
                    "title": "Novel approach",
                    "description": "This paper introduces a novel approach..."
                }
            ]
        },
        "analysis_iteration": 3,
        "completed_tasks": ["init", "analysis", "translation"],
        "is_analysis_complete": True,
        "is_translation_complete": True
    }
    
    report = formatter.format_analysis_report(test_state)
    print(f"测试报告生成成功，长度: {len(report)} 字符")
    print("前500字符:")
    print(report[:500])