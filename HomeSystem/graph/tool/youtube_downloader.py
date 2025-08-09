"""
YouTube视频下载工具

基于yt-dlp库实现的视频下载工具，支持多平台视频下载和自定义命名。
专门为论文研究中的视频资源下载优化。
"""

import os
import re
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List, Type
from urllib.parse import urlparse

import yt_dlp
from langchain_core.tools import BaseTool
from langchain_core.tools.base import ArgsSchema
from pydantic import BaseModel, Field, validator


logger = logging.getLogger(__name__)


class YouTubeDownloaderInput(BaseModel):
    """YouTube下载工具输入模型"""
    
    url: str = Field(description="视频URL (支持YouTube、Bilibili等多平台)")
    filename: Optional[str] = Field(default=None, description="自定义文件名(不含扩展名，由大模型确定)")
    format_preference: str = Field(default="mp4", description="首选格式 (mp4, webm, mkv等)")
    quality: str = Field(default="best", description="视频质量 (best, worst, 720p, 1080p等)")
    audio_only: bool = Field(default=False, description="是否只下载音频")
    max_filesize: Optional[str] = Field(default="500M", description="最大文件大小限制 (如 100M, 1G)")
    
    @validator('url')
    def validate_url(cls, v):
        """验证URL格式"""
        if not v or not v.strip():
            raise ValueError("URL不能为空")
        
        parsed = urlparse(v)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError("无效的URL格式")
        
        return v.strip()
    
    @validator('filename')
    def validate_filename(cls, v):
        """验证文件名安全性"""
        if v is None:
            return v
        
        # 清理不安全的字符
        safe_filename = re.sub(r'[<>:"/\\|?*]', '_', v.strip())
        # 限制长度
        if len(safe_filename) > 200:
            safe_filename = safe_filename[:200]
        
        return safe_filename if safe_filename else None
    
    @validator('quality')
    def validate_quality(cls, v):
        """验证质量设置"""
        valid_qualities = ['best', 'worst', '480p', '720p', '1080p', '1440p', '2160p']
        if v not in valid_qualities and not re.match(r'^\d+p?$', v):
            logger.warning(f"非标准质量设置: {v}, 将使用 'best'")
            return 'best'
        return v


class YouTubeDownloaderTool(BaseTool):
    """YouTube视频下载工具"""
    
    name: str = "youtube_downloader"
    description: str = (
        "下载YouTube等平台的视频到指定目录。"
        "支持自定义文件名、格式选择和质量控制。"
        "特别适用于下载论文相关的视频资源。"
    )
    args_schema: ArgsSchema = YouTubeDownloaderInput
    return_direct: bool = False
    
    def __init__(self, download_dir: str, **kwargs):
        """
        初始化YouTube下载工具
        
        Args:
            download_dir: 下载目录路径
            **kwargs: 其他BaseTool参数
        """
        super().__init__(**kwargs)
        
        # 设置下载目录（使用私有属性）
        self._download_dir = Path(download_dir)
        self._download_dir.mkdir(parents=True, exist_ok=True)
        
        # 支持的平台列表(可扩展)
        self._supported_platforms = {
            'youtube.com', 'youtu.be', 'bilibili.com', 'vimeo.com',
            'dailymotion.com', 'twitch.tv', 'tiktok.com'
        }
        
        logger.info(f"YouTube下载工具初始化完成，下载目录: {self._download_dir}")
    
    @property
    def download_dir(self) -> Path:
        """获取下载目录"""
        return self._download_dir
    
    def _run(self, 
             url: str, 
             filename: Optional[str] = None,
             format_preference: str = "mp4",
             quality: str = "best",
             audio_only: bool = False,
             max_filesize: Optional[str] = "500M") -> str:
        """
        执行视频下载
        
        Returns:
            下载结果信息
        """
        try:
            # 验证平台支持 - 仅记录警告，不阻止下载
            if not self._is_supported_platform(url):
                logger.warning(f"平台可能不受支持，尝试使用yt-dlp下载: {url}")
            
            # 检查磁盘空间
            if not self._check_disk_space():
                return "错误: 磁盘空间不足，无法下载"
            
            # 构建yt-dlp配置
            ydl_opts = self._build_ydl_options(
                filename=filename,
                format_preference=format_preference,
                quality=quality,
                audio_only=audio_only,
                max_filesize=max_filesize
            )
            
            # 执行下载
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # 首先获取视频信息
                try:
                    info = ydl.extract_info(url, download=False)
                    video_title = info.get('title', '未知标题')
                    duration = info.get('duration', 0)
                    
                    logger.info(f"准备下载: {video_title} (时长: {duration}秒)")
                    
                    # 执行下载
                    ydl.download([url])
                    
                    # 查找下载的文件
                    downloaded_files = self._find_downloaded_files(video_title, filename)
                    
                    if downloaded_files:
                        file_info = []
                        for file_path in downloaded_files:
                            size = file_path.stat().st_size / (1024 * 1024)  # MB
                            file_info.append(f"{file_path.name} ({size:.1f}MB)")
                        
                        result = (
                            f"下载成功!\n"
                            f"视频: {video_title}\n"
                            f"文件: {', '.join(file_info)}\n"
                            f"保存位置: {self._download_dir}"
                        )
                        logger.info(result)
                        return result
                    else:
                        return f"下载可能成功，但无法找到文件: {video_title}"
                        
                except yt_dlp.DownloadError as e:
                    error_msg = f"下载失败: {str(e)}"
                    logger.error(error_msg)
                    return error_msg
                    
        except Exception as e:
            error_msg = f"下载过程中发生错误: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return error_msg
    
    def _build_ydl_options(self,
                          filename: Optional[str] = None,
                          format_preference: str = "mp4",
                          quality: str = "best",
                          audio_only: bool = False,
                          max_filesize: Optional[str] = None) -> Dict[str, Any]:
        """构建yt-dlp下载配置"""
        
        # 基本输出模板
        if filename:
            outtmpl = str(self._download_dir / f"{filename}.%(ext)s")
        else:
            outtmpl = str(self._download_dir / "%(title)s.%(ext)s")
        
        # 基本配置
        ydl_opts = {
            'outtmpl': outtmpl,
            'format': self._build_format_selector(quality, format_preference, audio_only),
            'noplaylist': True,  # 只下载单个视频，不下载播放列表
            'extractaudio': audio_only,
            'ignoreerrors': False,
            'no_warnings': False,
            'writesubtitles': False,  # 默认不下载字幕
            'writeautomaticsub': False,
        }
        
        # 文件大小限制
        if max_filesize:
            # 确保max_filesize格式正确
            try:
                # 如果是字符串格式如"500M"，转换为数字格式
                if isinstance(max_filesize, str):
                    if max_filesize.upper().endswith('M'):
                        size_value = int(float(max_filesize[:-1]) * 1024 * 1024)
                    elif max_filesize.upper().endswith('G'):
                        size_value = int(float(max_filesize[:-1]) * 1024 * 1024 * 1024)
                    elif max_filesize.upper().endswith('K'):
                        size_value = int(float(max_filesize[:-1]) * 1024)
                    else:
                        size_value = int(max_filesize)
                    ydl_opts['max_filesize'] = size_value
                else:
                    ydl_opts['max_filesize'] = max_filesize
            except (ValueError, TypeError) as e:
                logger.warning(f"无法解析文件大小限制 '{max_filesize}': {e}")
                # 设置默认限制 500MB
                ydl_opts['max_filesize'] = 500 * 1024 * 1024
        
        # 音频专用配置
        if audio_only:
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
        
        # 进度钩子
        ydl_opts['progress_hooks'] = [self._progress_hook]
        
        return ydl_opts
    
    def _build_format_selector(self, quality: str, format_preference: str, audio_only: bool) -> str:
        """构建格式选择器"""
        if audio_only:
            return 'bestaudio/best'
        
        if quality == 'best':
            if format_preference == 'mp4':
                return 'best[ext=mp4]/best'
            else:
                return f'best[ext={format_preference}]/best'
        elif quality == 'worst':
            return 'worst'
        else:
            # 特定质量 (如720p)
            height = quality.replace('p', '')
            if format_preference == 'mp4':
                return f'best[height<={height}][ext=mp4]/best[height<={height}]/best'
            else:
                return f'best[height<={height}][ext={format_preference}]/best[height<={height}]/best'
    
    def _progress_hook(self, d: Dict[str, Any]):
        """下载进度回调"""
        if d['status'] == 'downloading':
            percent = d.get('_percent_str', 'N/A')
            speed = d.get('_speed_str', 'N/A')
            logger.info(f"下载进度: {percent} - 速度: {speed}")
        elif d['status'] == 'finished':
            logger.info(f"下载完成: {d['filename']}")
    
    def _is_supported_platform(self, url: str) -> bool:
        """检查是否为支持的平台"""
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        path = parsed.path.lower()
        
        # 去除www前缀
        if domain.startswith('www.'):
            domain = domain[4:]
        
        # 检查已知平台
        if any(platform in domain for platform in self._supported_platforms):
            return True
        
        # 检查是否为直接视频链接
        video_extensions = ['.mp4', '.webm', '.mkv', '.avi', '.mov', '.flv', '.m4v']
        if any(path.endswith(ext) for ext in video_extensions):
            logger.info(f"检测到直接视频链接: {url}")
            return True
        
        # 检查常见的学术/技术网站
        academic_domains = ['github.io', 'stanford.edu', 'mit.edu', 'berkeley.edu', 'arxiv.org']
        if any(academic_domain in domain for academic_domain in academic_domains):
            return True
            
        return False
    
    def _check_disk_space(self, min_space_mb: int = 1024) -> bool:
        """检查磁盘空间是否足够"""
        try:
            stat = os.statvfs(self._download_dir)
            # 修复属性访问问题
            free_space_mb = (stat.f_frsize * stat.f_bavail) / (1024 * 1024)
            return free_space_mb > min_space_mb
        except Exception as e:
            logger.warning(f"无法检查磁盘空间: {e}")
            return True  # 假设有足够空间
    
    def _find_downloaded_files(self, video_title: str, custom_filename: Optional[str]) -> List[Path]:
        """查找下载的文件"""
        files = []
        
        # 常见的视频和音频扩展名
        extensions = ['.mp4', '.webm', '.mkv', '.avi', '.mp3', '.m4a', '.wav']
        
        for ext in extensions:
            if custom_filename:
                file_path = self._download_dir / f"{custom_filename}{ext}"
            else:
                # 尝试多种可能的文件名变体
                safe_title = re.sub(r'[<>:"/\\|?*]', '_', video_title)
                file_path = self._download_dir / f"{safe_title}{ext}"
            
            if file_path.exists():
                files.append(file_path)
        
        # 如果没找到，列出最近创建的文件
        if not files:
            try:
                all_files = list(self._download_dir.iterdir())
                # 按创建时间排序，取最新的
                recent_files = sorted(all_files, key=lambda x: x.stat().st_mtime, reverse=True)
                for f in recent_files[:3]:  # 最近的3个文件
                    if f.is_file() and any(f.suffix.lower() == ext for ext in extensions):
                        files.append(f)
                        break
            except Exception as e:
                logger.warning(f"查找下载文件时出错: {e}")
        
        return files


def create_youtube_downloader_tool(download_dir: str) -> YouTubeDownloaderTool:
    """
    创建YouTube下载工具实例的工厂函数
    
    Args:
        download_dir: 下载目录路径
        
    Returns:
        配置好的YouTube下载工具实例
    """
    return YouTubeDownloaderTool(download_dir=download_dir)


# 使用示例
if __name__ == "__main__":
    import tempfile
    
    # 创建测试工具
    with tempfile.TemporaryDirectory() as temp_dir:
        tool = create_youtube_downloader_tool(temp_dir)
        
        # 测试下载 (注意：实际使用时需要有效的URL)
        test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # Rick Roll示例
        result = tool.invoke({
            "url": test_url,
            "filename": "test_video",
            "quality": "720p",
            "format_preference": "mp4"
        })
        
        print(f"下载结果: {result}")