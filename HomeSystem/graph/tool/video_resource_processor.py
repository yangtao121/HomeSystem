"""
视频资源处理器 - 处理单个页面的视频资源

从指定网页提取并处理所有视频，支持视频下载、内容分析和智能总结，
并使用Qwen3_30B模型进行精炼标题和专业总结。
"""

import os
import sys
from pathlib import Path
from typing import List, Optional, Type
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
from langchain_core.tools.base import ArgsSchema
from loguru import logger

# 添加HomeSystem路径到sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
homesystem_root = os.path.join(current_dir, '..', '..', '..')
sys.path.append(homesystem_root)

from HomeSystem.graph.llm_factory import llm_factory
from .youtube_downloader import YouTubeDownloaderTool
from .video_analysis_tool import VideoAnalysisTool
from .video_link_detector import VideoLinkExtractorTool


class VideoSummaryResult(BaseModel):
    """单个视频内容总结结果 - 结构化输出"""
    refined_title: str = Field(description="精炼的中文标题，简洁明了，体现核心内容")
    summary: str = Field(description="200-300字专业总结，突出技术要点和学术价值")


class VideoProcessResult(BaseModel):
    """单个视频处理结果"""
    title: str = Field(description="精炼的中文标题") 
    source_url: str = Field(description="原始视频URL")
    local_path: str = Field(description="本地文件相对路径")
    analysis_summary: str = Field(description="内容分析总结")
    file_size_mb: float = Field(description="文件大小MB")


class BatchVideoProcessResult(BaseModel):
    """批量视频处理结果"""
    processed_count: int = Field(description="成功处理的视频数量")
    videos: List[VideoProcessResult] = Field(description="所有处理成功的视频列表")
    failed_downloads: List[str] = Field(description="下载失败的视频URL列表")
    total_size_mb: float = Field(description="所有视频文件总大小MB")
    processing_summary: str = Field(description="处理结果摘要")


class VideoResourceProcessorInput(BaseModel):
    """视频资源处理器输入模型"""
    url: str = Field(description="要处理的网页URL，将提取该页面上的所有视频")
    download_quality: str = Field(default="720p", description="视频下载质量")
    max_videos: int = Field(default=5, description="最多处理的视频数量")


class VideoResourceProcessor(BaseTool):
    """
    视频资源处理器 - 处理单个页面的视频资源
    
    集成video_link_extractor、youtube_downloader、video_analyzer三个工具，
    支持从网页链接提取视频、下载到本地、分析内容并使用Qwen3_30B生成总结。
    """
    
    name: str = "process_video_resources"
    description: str = (
        "从指定网页提取并处理所有视频资源。自动识别页面中的YouTube、Bilibili等视频，"
        "下载到本地，分析内容并生成专业总结。支持多种视频平台和格式。"
    )
    args_schema: ArgsSchema = VideoResourceProcessorInput
    return_direct: bool = False
    
    def __init__(self, 
                 base_folder_path: str,
                 summarization_model: str = "ollama.Qwen3_30B",
                 **kwargs):
        """
        初始化视频资源处理器
        
        Args:
            base_folder_path: 视频文件夹基础路径
            summarization_model: 用于总结的LLM模型名称，默认使用Qwen3_30B
        """
        super().__init__(**kwargs)
        
        self.base_folder_path = base_folder_path
        self.video_download_dir = os.path.join(base_folder_path, "videos")
        
        # 确保视频目录存在
        Path(self.video_download_dir).mkdir(parents=True, exist_ok=True)
        
        # 初始化集成的工具
        self.video_link_extractor = VideoLinkExtractorTool()
        self.video_downloader = YouTubeDownloaderTool(download_dir=self.video_download_dir)
        self.video_analyzer = VideoAnalysisTool(base_folder_path=base_folder_path)
        
        # 初始化总结模型
        self.summarization_model = summarization_model
        try:
            self.base_llm = llm_factory.create_llm(model_name=summarization_model)
            self.structured_llm = self.base_llm.with_structured_output(VideoSummaryResult)
            logger.info(f"VideoResourceProcessor initialized with model: {summarization_model}")
        except Exception as e:
            logger.error(f"Failed to initialize LLM {summarization_model}: {e}")
            self.structured_llm = None
    
    def _run(self, 
             url: str, 
             download_quality: str = "720p",
             max_videos: int = 5) -> str:
        """
        处理视频资源
        
        Args:
            url: 包含视频的网页URL
            download_quality: 视频下载质量
            max_videos: 最多处理的视频数量
            
        Returns:
            str: JSON格式的处理结果
        """
        logger.info(f"开始处理视频资源，页面URL: {url}")
        
        all_processed_videos = []
        failed_downloads = []
        
        try:
            # 1. 从页面提取所有视频链接
            logger.info(f"正在从页面提取视频: {url}")
            extraction_result = self.video_link_extractor.invoke({
                "url": url,
                "include_embeds": True,
                "include_direct": True,
                "include_video_tags": True
            })
            
            # 解析提取结果
            if isinstance(extraction_result, str):
                import json
                extracted_data = json.loads(extraction_result)
            else:
                extracted_data = extraction_result
            
            page_videos = extracted_data.get('videos', [])
            logger.info(f"从页面 {url} 提取到 {len(page_videos)} 个视频")
            
            # 2. 限制处理数量
            videos_to_process = page_videos[:max_videos]
            
            # 3. 处理每个视频
            for video_info in videos_to_process:
                try:
                    video_url = video_info.get('video_url', '')
                    if not video_url:
                        continue
                        
                    logger.info(f"正在处理视频: {video_url}")
                    video_result = self._process_single_video(video_url, download_quality)
                    
                    if video_result:
                        all_processed_videos.append(video_result)
                        logger.info(f"视频处理成功: {video_result.title}")
                    
                except Exception as e:
                    logger.error(f"处理视频失败 {video_info.get('video_url', 'unknown')}: {e}")
                    failed_downloads.append(video_info.get('video_url', 'unknown'))
                    
        except Exception as e:
            logger.error(f"处理页面失败 {url}: {e}")
        
        # 4. 生成处理结果
        total_size = sum(v.file_size_mb for v in all_processed_videos)
        
        result = BatchVideoProcessResult(
            processed_count=len(all_processed_videos),
            videos=all_processed_videos,
            failed_downloads=failed_downloads,
            total_size_mb=total_size,
            processing_summary=f"成功处理{len(all_processed_videos)}个视频，总大小{total_size:.1f}MB"
        )
        
        logger.info(f"处理完成: {result.processing_summary}")
        return result.model_dump_json(indent=2)
    
    def _process_single_video(self, video_url: str, download_quality: str) -> Optional[VideoProcessResult]:
        """
        处理单个视频
        
        Args:
            video_url: 视频URL
            download_quality: 下载质量
            
        Returns:
            VideoProcessResult: 处理结果，失败时返回None
        """
        try:
            # 1. 下载视频
            logger.info(f"开始下载视频: {video_url}")
            download_result = self.video_downloader.invoke({
                "url": video_url,
                "quality": download_quality,
                "format_preference": "mp4",
                "max_filesize": "500M"
            })
            
            # 解析下载结果
            local_path, original_title = self._extract_download_info(download_result)
            logger.info(f"视频下载完成: {original_title} -> {local_path}")
            
            # 2. 视频内容分析
            logger.info(f"开始分析视频内容: {local_path}")
            analysis_result = self.video_analyzer.invoke({
                "analysis_query": "详细分析这个视频的主要内容、关键场景和技术要点",
                "video_path": local_path,
                "frame_count": 5,
                "sampling_method": "sequential"
            })
            
            # 3. 使用Qwen3_30B结构化总结
            logger.info("开始生成视频总结")
            summary_result = self._summarize_with_llm(analysis_result, original_title)
            
            # 4. 生成处理结果
            file_size_mb = self._get_file_size_mb(local_path)
            relative_path = os.path.relpath(local_path, self.base_folder_path)
            
            return VideoProcessResult(
                title=summary_result.refined_title,
                source_url=video_url,
                local_path=relative_path,
                analysis_summary=summary_result.summary,
                file_size_mb=file_size_mb
            )
            
        except Exception as e:
            logger.error(f"处理单个视频失败 {video_url}: {e}")
            return None
    
    def _extract_download_info(self, download_result: str) -> tuple[str, str]:
        """
        从下载结果中提取文件路径和标题
        
        Args:
            download_result: 下载工具的返回结果
            
        Returns:
            tuple: (local_path, original_title)
        """
        try:
            if isinstance(download_result, str):
                import json
                result_data = json.loads(download_result)
            else:
                result_data = download_result
            
            local_path = result_data.get('local_path', '')
            original_title = result_data.get('title', 'Unknown Video')
            
            return local_path, original_title
            
        except Exception as e:
            logger.error(f"解析下载结果失败: {e}")
            raise ValueError(f"无法解析下载结果: {e}")
    
    def _summarize_with_llm(self, video_analysis: str, original_title: str) -> VideoSummaryResult:
        """
        使用Qwen3_30B结构化总结视频内容
        
        Args:
            video_analysis: 视频分析结果
            original_title: 原始视频标题
            
        Returns:
            VideoSummaryResult: 结构化总结结果
        """
        if not self.structured_llm:
            logger.warning("LLM未初始化，使用降级处理")
            return VideoSummaryResult(
                refined_title=original_title,
                summary=video_analysis[:300] + "..." if len(video_analysis) > 300 else video_analysis
            )
        
        prompt = f"""你是一位专业的学术视频内容分析专家。请基于详细的视频分析结果，提取关键信息并生成结构化总结。

**原始视频标题**: {original_title}

**详细视频分析结果**:
{video_analysis}

请提供结构化信息：
- refined_title: 提炼简洁的中文标题，突出核心技术点，长度控制在20字以内
- summary: 200-300字的专业总结，重点突出技术要点和学术价值

要求：
1. refined_title要简洁明了，体现视频核心内容
2. summary要专业准确，突出学术和技术价值
3. 语言风格要适合学术研究参考
4. 重点关注技术创新点和实际应用价值
"""
        
        try:
            result = self.structured_llm.invoke(prompt)
            if isinstance(result, VideoSummaryResult):
                logger.info(f"LLM总结成功: {result.refined_title}")
                return result
            else:
                logger.warning("LLM返回结果格式不正确")
                raise ValueError("Invalid LLM result format")
            
        except Exception as e:
            logger.error(f"LLM总结失败: {e}")
            # 降级处理
            return VideoSummaryResult(
                refined_title=original_title[:20] if len(original_title) > 20 else original_title,
                summary=video_analysis[:300] + "..." if len(video_analysis) > 300 else video_analysis
            )
    
    def _get_file_size_mb(self, file_path: str) -> float:
        """
        获取文件大小（MB）
        
        Args:
            file_path: 文件路径
            
        Returns:
            float: 文件大小（MB）
        """
        try:
            size_bytes = os.path.getsize(file_path)
            size_mb = size_bytes / (1024 * 1024)
            return round(size_mb, 1)
        except Exception as e:
            logger.error(f"获取文件大小失败 {file_path}: {e}")
            return 0.0


def create_video_resource_processor(base_folder_path: str, 
                                  summarization_model: str = "ollama.Qwen3_30B") -> VideoResourceProcessor:
    """
    创建视频资源处理器工具实例
    
    Args:
        base_folder_path: 基础文件夹路径
        summarization_model: 用于总结的LLM模型名称
        
    Returns:
        VideoResourceProcessor: 视频资源处理器实例
    """
    return VideoResourceProcessor(
        base_folder_path=base_folder_path,
        summarization_model=summarization_model
    )