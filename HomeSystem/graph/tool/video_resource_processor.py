"""
视频资源处理器 - 处理单个页面的视频资源

从指定网页提取并处理所有视频，支持视频下载、内容分析和智能总结，
并使用Qwen3_30B模型进行精炼标题和专业总结。
"""

import os
import sys
import re
import json
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
        
        # 使用私有属性避免Pydantic字段验证问题
        self._base_folder_path = os.path.abspath(base_folder_path)  # 转换为绝对路径
        self._video_download_dir = os.path.join(self._base_folder_path, "videos")
        
        # 确保视频目录存在
        Path(self._video_download_dir).mkdir(parents=True, exist_ok=True)
        
        # 初始化集成的工具
        self._video_link_extractor = VideoLinkExtractorTool()
        self._video_downloader = YouTubeDownloaderTool(download_dir=self._video_download_dir)
        self._video_analyzer = VideoAnalysisTool(base_folder_path=base_folder_path)
        
        # 初始化总结模型
        self._summarization_model = summarization_model
        try:
            self._base_llm = llm_factory.create_llm(model_name=summarization_model)
            self._structured_llm = self._base_llm.with_structured_output(VideoSummaryResult)
            logger.info(f"VideoResourceProcessor initialized with model: {summarization_model}")
        except Exception as e:
            logger.error(f"Failed to initialize LLM {summarization_model}: {e}")
            self._structured_llm = None
    
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
            extraction_result = self._video_link_extractor.invoke({
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
                    
                    # 处理相对路径URL，转换为绝对URL
                    if not video_url.startswith(('http://', 'https://')):
                        from urllib.parse import urljoin
                        video_url = urljoin(url, video_url)
                        
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
            download_result = self._video_downloader.invoke({
                "url": video_url,
                "quality": download_quality,
                "format_preference": "mp4",
                "max_filesize": "500M"
            })
            
            # 解析下载结果
            local_path, original_title = self._extract_download_info(download_result, video_url)
            # 标准化路径
            local_path = self._normalize_path(local_path)
            logger.info(f"视频下载完成: {original_title} -> {local_path}")
            
            # 检查文件是否真实存在
            file_exists = os.path.exists(local_path)
            if not file_exists:
                logger.warning(f"下载的视频文件不存在: {local_path}")
                
            # 2. 视频内容分析（如果文件存在）
            analysis_result = ""
            if file_exists:
                logger.info(f"开始分析视频内容: {local_path}")
                analysis_result = self._video_analyzer.invoke({
                    "analysis_query": "详细分析这个视频的主要内容、关键场景和技术要点",
                    "video_path": local_path,
                    "frame_count": 5,
                    "sampling_method": "sequential"
                })
            else:
                # 文件不存在时，生成基于URL的降级分析
                logger.info("文件不存在，生成基于URL的降级分析")
                analysis_result = self._generate_fallback_analysis(video_url, original_title)
            
            # 3. 使用Qwen3_30B结构化总结
            logger.info("开始生成视频总结")
            summary_result = self._summarize_with_llm(analysis_result, original_title)
            
            # 4. 根据精炼标题重命名文件（仅当文件存在时）
            renamed_path = local_path
            if file_exists:
                logger.info(f"根据精炼标题重命名文件: {summary_result.refined_title}")
                renamed_path = self._rename_video_file(local_path, summary_result.refined_title)
            else:
                logger.info("文件不存在，跳过重命名操作")
            
            # 5. 生成处理结果
            file_size_mb = 0.0
            if file_exists:
                file_size_mb = self._get_file_size_mb(renamed_path)
            
            # 使用相对路径
            if file_exists and os.path.exists(renamed_path):
                relative_path = os.path.relpath(renamed_path, self._base_folder_path)
            else:
                # 对于不存在的文件，生成一个虚拟的相对路径用于显示
                relative_path = f"videos/{self._generate_safe_filename(summary_result.refined_title)}.mp4"
            
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
    
    def _extract_download_info(self, download_result: str, video_url: str = "") -> tuple[str, str]:
        """
        从下载结果中提取文件路径和标题
        
        Args:
            download_result: 下载工具的返回结果
            video_url: 原始视频URL，用于生成文件名fallback
            
        Returns:
            tuple: (local_path, original_title)
        """
        try:
            logger.info(f"下载器返回结果类型: {type(download_result)}")
            logger.info(f"下载器返回结果内容: {str(download_result)[:500]}")
            
            if isinstance(download_result, str):
                # 尝试解析JSON
                try:
                    result_data = json.loads(download_result)
                    local_path = result_data.get('local_path', '')
                    original_title = result_data.get('title', 'Unknown Video')
                    return local_path, original_title
                except json.JSONDecodeError:
                    # 如果不是JSON，尝试从字符串中提取信息
                    logger.info("下载结果不是JSON格式，尝试解析字符串")
                    lines = download_result.strip().split('\n')
                    
                    # 查找包含文件路径的行
                    local_path = ""
                    original_title = "Unknown Video"
                    
                    filename_from_file_line = ""
                    
                    for line in lines:
                        if "保存位置:" in line:
                            # 从保存位置行提取目录路径
                            parts = line.split("保存位置:")
                            if len(parts) > 1:
                                potential_path = parts[-1].strip()
                                if potential_path and "/" in potential_path:
                                    # 如果有文件名，组合完整路径
                                    if filename_from_file_line:
                                        local_path = os.path.join(potential_path, filename_from_file_line)
                                    else:
                                        local_path = potential_path
                        elif "文件:" in line:
                            # 从文件行提取文件名
                            parts = line.split("文件:")
                            if len(parts) > 1:
                                file_info = parts[-1].strip()
                                # 提取文件名部分（去除大小信息）
                                file_match = re.search(r'([^,\s]+\.(mp4|webm|mkv|avi|flv))', file_info, re.IGNORECASE)
                                if file_match:
                                    filename_from_file_line = file_match.group(1)
                        elif "视频:" in line:
                            # 从视频行提取标题
                            parts = line.split("视频:")
                            if len(parts) > 1:
                                original_title = parts[1].strip()
                    
                    # 如果找到了目录和文件名，组合完整路径
                    if local_path and filename_from_file_line and not local_path.endswith('.mp4'):
                        local_path = os.path.join(local_path, filename_from_file_line)
                    
                    # 如果仍然没有找到路径，从URL生成预期路径
                    if not local_path:
                        logger.warning("无法从下载结果中提取路径，尝试从URL生成文件名")
                        filename = self._generate_filename_from_url(video_url)
                        local_path = os.path.join(self._video_download_dir, filename)
                        logger.info(f"生成预期文件路径: {local_path}")
                    
                    return local_path, original_title
            else:
                # 如果是字典或其他格式
                result_data = download_result
                local_path = result_data.get('local_path', '')
                original_title = result_data.get('title', 'Unknown Video')
                return local_path, original_title
            
        except Exception as e:
            logger.error(f"解析下载结果失败: {e}")
            logger.error(f"原始结果: {download_result}")
            # 即使解析失败，也尝试从URL生成文件名
            try:
                if video_url:
                    filename = self._generate_filename_from_url(video_url)
                    local_path = os.path.join(self._video_download_dir, filename)
                    logger.warning(f"解析失败，使用URL生成路径: {local_path}")
                    return local_path, "Unknown Video"
            except Exception:
                pass
            raise ValueError(f"无法解析下载结果: {e}")
    
    def _normalize_path(self, path: str) -> str:
        """
        标准化路径，确保路径格式一致
        
        Args:
            path: 输入路径
            
        Returns:
            str: 标准化后的绝对路径
        """
        try:
            # 如果是相对路径，相对于base_folder_path解析
            if not os.path.isabs(path):
                path = os.path.join(self._base_folder_path, path)
            
            # 转换为绝对路径并规范化
            return os.path.abspath(os.path.normpath(path))
        except Exception as e:
            logger.warning(f"路径标准化失败 {path}: {e}")
            return path
    
    def _generate_fallback_analysis(self, video_url: str, original_title: str) -> str:
        """
        当视频文件不存在时，生成基于URL和标题的降级分析
        
        Args:
            video_url: 视频URL
            original_title: 原始标题
            
        Returns:
            str: 降级分析结果
        """
        try:
            from urllib.parse import urlparse
            parsed = urlparse(video_url)
            domain = parsed.netloc.lower()
            path = parsed.path.lower()
            
            # 基于URL和标题推测视频内容
            content_hints = []
            
            # 从URL路径分析内容类型
            if 'medicine' in path or 'medical' in path:
                content_hints.append("医学相关内容")
            if 'target' in path:
                content_hints.append("目标导向的教学内容")
            if 'barrier' in path:
                content_hints.append("障碍或防护相关主题")
            if any(keyword in path for keyword in ['tutorial', 'guide', 'demo', 'example']):
                content_hints.append("教学指导类内容")
            
            # 从文件名分析
            filename = os.path.basename(parsed.path).lower()
            if filename:
                # 提取可能的关键词
                keywords = re.findall(r'[a-zA-Z]{3,}', filename)
                content_hints.extend([f"包含关键词: {keyword}" for keyword in keywords[:3]])
            
            # 生成分析结果
            analysis = f"""基于URL和文件信息的内容分析:

**视频源**: {domain}
**原始标题**: {original_title}
**URL路径**: {parsed.path}

**内容推测**:
"""
            if content_hints:
                for hint in content_hints:
                    analysis += f"- {hint}\n"
            else:
                analysis += "- 未能从URL中识别具体内容类型\n"
            
            analysis += f"""
**技术信息**:
- 视频文件下载失败或不可访问
- 文件预期格式: MP4
- 来源域名: {domain}

**状态**: 文件下载异常，仅提供基于URL的内容推测分析
"""
            
            return analysis
            
        except Exception as e:
            logger.error(f"生成降级分析失败: {e}")
            return f"""降级分析 - 视频文件访问异常

**原始标题**: {original_title}
**视频URL**: {video_url}
**状态**: 文件下载失败，无法进行详细内容分析

这可能是由于网络问题、文件格式不受支持或源站点访问限制导致的。
建议检查URL有效性或尝试使用其他下载方式。
"""
    
    def _generate_filename_from_url(self, url: str) -> str:
        """
        从URL生成文件名
        
        Args:
            url: 视频URL
            
        Returns:
            str: 生成的文件名
        """
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            path = parsed.path
            
            # 提取文件名
            filename = os.path.basename(path)
            
            # 如果文件名为空或没有扩展名，生成一个
            if not filename or '.' not in filename:
                # 从路径中提取最后一个有意义的部分
                path_parts = [part for part in path.split('/') if part]
                if path_parts:
                    base_name = path_parts[-1]
                    # 清理文件名
                    base_name = re.sub(r'[^a-zA-Z0-9_\-\u4e00-\u9fa5]', '_', base_name)
                    filename = f"{base_name}.mp4"
                else:
                    filename = "video.mp4"
            
            # 确保文件名安全
            filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
            
            return filename
        except Exception as e:
            logger.error(f"从URL生成文件名失败 {url}: {e}")
            return "video.mp4"
    
    def _summarize_with_llm(self, video_analysis: str, original_title: str) -> VideoSummaryResult:
        """
        使用Qwen3_30B结构化总结视频内容
        
        Args:
            video_analysis: 视频分析结果
            original_title: 原始视频标题
            
        Returns:
            VideoSummaryResult: 结构化总结结果
        """
        if not self._structured_llm:
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
            result = self._structured_llm.invoke(prompt)
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
    
    def _generate_safe_filename(self, title: str) -> str:
        """
        将标题转换为安全的文件名
        
        Args:
            title: 原始标题
            
        Returns:
            str: 安全的文件名（不包含扩展名）
        """
        # 移除或替换不安全的字符
        safe_title = title.strip()
        
        # 替换不安全的字符为下划线
        safe_title = re.sub(r'[<>:"/\\|?*]', '_', safe_title)
        
        # 移除多余的空格和特殊字符
        safe_title = re.sub(r'\s+', ' ', safe_title).strip()
        
        # 限制文件名长度（保留100个字符，避免路径过长）
        if len(safe_title) > 100:
            safe_title = safe_title[:100].rstrip()
        
        # 确保文件名不为空
        if not safe_title:
            safe_title = "video_file"
        
        return safe_title
    
    def _rename_video_file(self, original_path: str, new_title: str) -> str:
        """
        将视频文件重命名为基于新标题的文件名
        
        Args:
            original_path: 原始文件路径
            new_title: 新的标题
            
        Returns:
            str: 重命名后的文件路径，如果重命名失败则返回原路径
        """
        try:
            original_file = Path(original_path)
            if not original_file.exists():
                logger.warning(f"原始文件不存在: {original_path}")
                return original_path
            
            # 获取文件扩展名
            file_extension = original_file.suffix
            
            # 生成安全的文件名
            safe_filename = self._generate_safe_filename(new_title)
            
            # 构建新的文件路径
            new_filename = f"{safe_filename}{file_extension}"
            new_path = original_file.parent / new_filename
            
            # 处理文件名冲突
            counter = 1
            while new_path.exists() and new_path != original_file:
                new_filename = f"{safe_filename}_{counter}{file_extension}"
                new_path = original_file.parent / new_filename
                counter += 1
                
                # 避免无限循环
                if counter > 999:
                    logger.warning(f"无法找到合适的文件名，使用原文件名: {original_path}")
                    return original_path
            
            # 如果新路径与原路径相同，不需要重命名
            if new_path == original_file:
                logger.info(f"文件名已符合要求，无需重命名: {original_path}")
                return original_path
            
            # 执行重命名
            original_file.rename(new_path)
            logger.info(f"文件重命名成功: {original_file.name} -> {new_path.name}")
            return str(new_path)
            
        except Exception as e:
            logger.error(f"文件重命名失败 {original_path}: {e}")
            return original_path
    
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