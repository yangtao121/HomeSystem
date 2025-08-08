"""
GIF下载工具

基于requests和PIL实现的GIF下载工具，支持多平台GIF下载、自定义命名和质量控制。
专门为GIF资源收集和管理优化。
"""

import os
import re
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple, ClassVar
from urllib.parse import urlparse, parse_qs
import time

import requests
from PIL import Image
from langchain_core.tools import BaseTool
from langchain_core.tools.base import ArgsSchema
from pydantic import BaseModel, Field, validator
from bs4 import BeautifulSoup


logger = logging.getLogger(__name__)


class GifDownloaderInput(BaseModel):
    """GIF下载工具输入模型"""
    
    url: str = Field(description="GIF URL (支持Giphy、Tenor、Imgur等多平台)")
    filename: Optional[str] = Field(default=None, description="自定义文件名(不含扩展名)")
    quality: str = Field(default="original", description="GIF质量 (original, compressed, small)")
    max_filesize: Optional[str] = Field(default="50M", description="最大文件大小限制 (如 10M, 100M)")
    extract_metadata: bool = Field(default=True, description="是否提取GIF元数据")
    
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
        valid_qualities = ['original', 'compressed', 'small']
        if v not in valid_qualities:
            logger.warning(f"非标准质量设置: {v}, 将使用 'original'")
            return 'original'
        return v


class GifDownloaderTool(BaseTool):
    """GIF下载工具"""
    
    name: str = "gif_downloader"
    description: str = (
        "下载GIF动图到指定目录。"
        "支持多平台GIF下载、自定义文件名和质量控制。"
        "特别适用于收集和管理GIF资源。"
    )
    args_schema: ArgsSchema = GifDownloaderInput
    return_direct: bool = False
    
    # 支持的GIF平台URL模式
    PLATFORM_PATTERNS: ClassVar[Dict[str, List[str]]] = {
        'giphy': [
            r'(?:https?:)?(?:\/\/)?(?:www\.)?giphy\.com\/gifs\/[^\/\s]*-([a-zA-Z0-9]+)',
            r'(?:https?:)?(?:\/\/)?gph\.is\/([a-zA-Z0-9]+)',
            r'(?:https?:)?(?:\/\/)?media\.giphy\.com\/media\/([a-zA-Z0-9]+)',
            r'(?:https?:)?(?:\/\/)?i\.giphy\.com\/([a-zA-Z0-9]+)\.gif'
        ],
        'tenor': [
            r'(?:https?:)?(?:\/\/)?(?:www\.)?tenor\.com\/view\/[^\/\s]*-(\d+)',
            r'(?:https?:)?(?:\/\/)?media\.tenor\.com\/[^\/\s]*\/([^\/\s]+)\.gif',
            r'(?:https?:)?(?:\/\/)?c\.tenor\.com\/[^\/\s]*\/([^\/\s]+)\.gif'
        ],
        'imgur': [
            r'(?:https?:)?(?:\/\/)?(?:www\.)?imgur\.com\/([a-zA-Z0-9]+)\.gif',
            r'(?:https?:)?(?:\/\/)?i\.imgur\.com\/([a-zA-Z0-9]+)\.gif'
        ],
        'reddit': [
            r'(?:https?:)?(?:\/\/)?i\.redd\.it\/([^\/\s]+\.gif)',
            r'(?:https?:)?(?:\/\/)?preview\.redd\.it\/([^\/\s]+\.gif)'
        ],
        'twitter': [
            r'(?:https?:)?(?:\/\/)?pbs\.twimg\.com\/tweet_video\/([^\/\s]+\.gif)',
            r'(?:https?:)?(?:\/\/)?pbs\.twimg\.com\/media\/([^\/\s]+\.gif)'
        ],
        'discord': [
            r'(?:https?:)?(?:\/\/)?cdn\.discordapp\.com\/attachments\/\d+\/\d+\/([^\/\s]+\.gif)'
        ],
        'tumblr': [
            r'(?:https?:)?(?:\/\/)?media\.tumblr\.com\/([a-zA-Z0-9]+)\/[^\/\s]*\.gif'
        ],
        'direct': [
            r'(?:https?:)?(?:\/\/)?[^\/\s]+\/[^\/\s]*\.gif(?:\?[^\/\s]*)?'
        ]
    }
    
    def __init__(self, download_dir: str, **kwargs):
        """
        初始化GIF下载工具
        
        Args:
            download_dir: 下载目录路径
            **kwargs: 其他BaseTool参数
        """
        super().__init__(**kwargs)
        
        # 设置下载目录（使用私有属性）
        self._download_dir = Path(download_dir)
        self._download_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化requests会话
        self._session = requests.Session()
        self._session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # 支持的平台列表
        self._supported_platforms = set(self.PLATFORM_PATTERNS.keys())
        
        logger.info(f"GIF下载工具初始化完成，下载目录: {self._download_dir}")
    
    @property
    def download_dir(self) -> Path:
        """获取下载目录"""
        return self._download_dir
    
    def _run(self, 
             url: str,
             filename: Optional[str] = None,
             quality: str = "original",
             max_filesize: Optional[str] = "50M",
             extract_metadata: bool = True) -> str:
        """
        执行GIF下载
        
        Returns:
            下载结果信息
        """
        try:
            # 分析URL和平台
            platform, gif_id, direct_url = self._analyze_url(url)
            
            if not direct_url:
                return f"错误: 无法解析GIF URL: {url}"
            
            # 检查磁盘空间
            if not self._check_disk_space():
                return "错误: 磁盘空间不足，无法下载"
            
            # 验证文件大小限制
            max_size_bytes = self._parse_size_limit(max_filesize) if max_filesize else None
            
            # 执行下载
            download_result = self._download_gif(
                direct_url, filename, quality, max_size_bytes, extract_metadata
            )
            
            if download_result['success']:
                result = (
                    f"下载成功!\n"
                    f"平台: {platform}\n"
                    f"文件: {download_result['filename']}\n"
                    f"大小: {download_result['size_mb']:.2f}MB"
                )
                
                if download_result['metadata']:
                    metadata = download_result['metadata']
                    result += f"\n尺寸: {metadata['width']}x{metadata['height']}"
                    result += f"\n帧数: {metadata['frames']}"
                
                result += f"\n保存位置: {self._download_dir}"
                logger.info(result)
                return result
            else:
                return f"下载失败: {download_result['error']}"
                
        except Exception as e:
            error_msg = f"下载过程中发生错误: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return error_msg
    
    def _analyze_url(self, url: str) -> Tuple[str, str, Optional[str]]:
        """
        分析URL，识别平台和提取直接GIF URL
        
        Returns:
            Tuple[platform, gif_id, direct_url]
        """
        try:
            # 清理URL
            url = url.strip()
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            
            # 检查直接GIF URL (but check platform patterns first)
            # 检查各平台模式
            for platform, patterns in self.PLATFORM_PATTERNS.items():
                if platform == 'direct':  # Skip direct pattern for now
                    continue
                for pattern in patterns:
                    match = re.search(pattern, url, re.IGNORECASE)
                    if match:
                        gif_id = match.group(1) if match.groups() else "unknown"
                        direct_url = self._get_direct_url(platform, gif_id, url)
                        return platform, gif_id, direct_url
            
            # If no specific platform matches, check if it's a direct GIF URL
            if url.lower().endswith('.gif'):
                return 'direct', 'unknown', url
            
            # 如果没有匹配，尝试从页面提取
            direct_url = self._extract_from_page(url)
            return 'unknown', 'unknown', direct_url
            
        except Exception as e:
            logger.error(f"URL分析失败 {url}: {e}")
            return 'unknown', 'unknown', None
    
    def _get_direct_url(self, platform: str, gif_id: str, original_url: str) -> Optional[str]:
        """获取直接GIF URL"""
        try:
            if platform == 'giphy':
                if gif_id != "unknown":
                    return f"https://media.giphy.com/media/{gif_id}/giphy.gif"
                else:
                    # 从页面提取
                    return self._extract_from_giphy_page(original_url)
            
            elif platform == 'tenor':
                if gif_id != "unknown":
                    # Tenor需要从页面获取直接链接
                    return self._extract_from_tenor_page(original_url)
            
            elif platform == 'imgur':
                if gif_id != "unknown":
                    return f"https://i.imgur.com/{gif_id}.gif"
            
            elif platform in ['reddit', 'twitter', 'discord', 'tumblr']:
                # 这些平台通常直接包含GIF URL
                return original_url
            
            elif platform == 'direct':
                return original_url
            
            return None
            
        except Exception as e:
            logger.error(f"获取直接URL失败 {platform}/{gif_id}: {e}")
            return None
    
    def _extract_from_page(self, url: str) -> Optional[str]:
        """从页面HTML中提取GIF URL"""
        try:
            response = self._session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 查找常见的GIF元标签
            og_image = soup.find('meta', property='og:image')
            if og_image:
                gif_url = og_image.get('content', '')
                if gif_url.lower().endswith('.gif'):
                    return gif_url
            
            # 查找img标签中的GIF
            img_tags = soup.find_all('img', src=lambda x: x and x.lower().endswith('.gif'))
            if img_tags:
                return img_tags[0]['src']
            
            return None
            
        except Exception as e:
            logger.error(f"从页面提取GIF失败 {url}: {e}")
            return None
    
    def _extract_from_giphy_page(self, url: str) -> Optional[str]:
        """从Giphy页面提取GIF URL"""
        try:
            response = self._session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 查找meta标签中的GIF URL
            og_image = soup.find('meta', property='og:image')
            if og_image:
                gif_url = og_image.get('content', '')
                if '.gif' in gif_url:
                    return gif_url
            
            # 在脚本中查找GIF URL
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string and 'gif' in script.string:
                    gif_match = re.search(r'"url":"([^"]+\.gif)"', script.string)
                    if gif_match:
                        return gif_match.group(1).replace('\\/', '/')
            
            return None
            
        except Exception as e:
            logger.error(f"Giphy页面提取失败 {url}: {e}")
            return None
    
    def _extract_from_tenor_page(self, url: str) -> Optional[str]:
        """从Tenor页面提取GIF URL"""
        try:
            response = self._session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 查找meta标签
            og_image = soup.find('meta', property='og:image')
            if og_image:
                gif_url = og_image.get('content', '')
                if '.gif' in gif_url:
                    return gif_url
            
            # 在脚本中查找
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string and 'gif' in script.string:
                    gif_match = re.search(r'"gif":\{"url":"([^"]+)"', script.string)
                    if gif_match:
                        return gif_match.group(1).replace('\\/', '/')
            
            return None
            
        except Exception as e:
            logger.error(f"Tenor页面提取失败 {url}: {e}")
            return None
    
    def _download_gif(self, 
                      url: str, 
                      filename: Optional[str], 
                      quality: str,
                      max_size_bytes: Optional[int],
                      extract_metadata: bool) -> Dict[str, Any]:
        """下载GIF文件"""
        try:
            # 首先检查文件大小
            head_response = self._session.head(url, timeout=10)
            if head_response.status_code != 200:
                # 如果HEAD请求失败，尝试GET但限制大小
                head_response = None
            
            content_length = None
            if head_response:
                content_length = head_response.headers.get('content-length')
                if content_length:
                    content_length = int(content_length)
                    if max_size_bytes and content_length > max_size_bytes:
                        return {
                            'success': False,
                            'error': f'文件太大: {content_length / (1024*1024):.1f}MB，超过限制 {max_size_bytes / (1024*1024):.1f}MB'
                        }
            
            # 下载文件
            logger.info(f"开始下载GIF: {url}")
            response = self._session.get(url, timeout=30, stream=True)
            response.raise_for_status()
            
            # 验证内容类型
            content_type = response.headers.get('content-type', '').lower()
            if 'image/gif' not in content_type and 'image/' not in content_type:
                logger.warning(f"内容类型可能不是GIF: {content_type}")
            
            # 生成文件名
            if filename:
                final_filename = f"{filename}.gif"
            else:
                # 从URL提取文件名
                parsed_url = urlparse(url)
                url_filename = os.path.basename(parsed_url.path)
                if url_filename and url_filename.endswith('.gif'):
                    final_filename = url_filename
                else:
                    # 生成时间戳文件名
                    timestamp = int(time.time())
                    final_filename = f"gif_{timestamp}.gif"
            
            file_path = self._download_dir / final_filename
            
            # 写入文件并跟踪进度
            downloaded_size = 0
            chunk_size = 8192
            
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        
                        # 检查大小限制
                        if max_size_bytes and downloaded_size > max_size_bytes:
                            f.close()
                            file_path.unlink()  # 删除部分下载的文件
                            return {
                                'success': False,
                                'error': f'下载中断: 文件超过大小限制 {max_size_bytes / (1024*1024):.1f}MB'
                            }
                        
                        # 进度日志
                        if downloaded_size % (1024*1024) == 0:  # 每MB记录一次
                            logger.info(f"已下载: {downloaded_size / (1024*1024):.1f}MB")
            
            logger.info(f"下载完成: {file_path} ({downloaded_size / (1024*1024):.2f}MB)")
            
            # 验证GIF文件
            gif_metadata = None
            if extract_metadata:
                gif_metadata = self._extract_gif_metadata(file_path)
                if not gif_metadata:
                    logger.warning("无法提取GIF元数据，文件可能损坏")
            
            # 根据质量设置处理GIF
            if quality != 'original' and gif_metadata:
                processed_path = self._process_gif_quality(file_path, quality, gif_metadata)
                if processed_path and processed_path != file_path:
                    file_path = processed_path
                    final_filename = file_path.name
                    # 重新获取文件大小
                    downloaded_size = file_path.stat().st_size
            
            return {
                'success': True,
                'filename': final_filename,
                'file_path': str(file_path),
                'size_mb': downloaded_size / (1024*1024),
                'metadata': gif_metadata
            }
            
        except requests.exceptions.RequestException as e:
            return {'success': False, 'error': f'网络错误: {str(e)}'}
        except Exception as e:
            return {'success': False, 'error': f'下载错误: {str(e)}'}
    
    def _extract_gif_metadata(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """提取GIF元数据"""
        try:
            with Image.open(file_path) as gif:
                if not getattr(gif, 'is_animated', False):
                    # 静态图像
                    return {
                        'width': gif.width,
                        'height': gif.height,
                        'frames': 1,
                        'duration': 0,
                        'format': gif.format,
                        'mode': gif.mode
                    }
                
                # 动画GIF
                frames = 0
                total_duration = 0
                
                try:
                    while True:
                        frames += 1
                        duration = gif.info.get('duration', 100)  # 默认100ms
                        total_duration += duration
                        gif.seek(gif.tell() + 1)
                except EOFError:
                    pass  # 到达最后一帧
                
                return {
                    'width': gif.width,
                    'height': gif.height,
                    'frames': frames,
                    'duration': total_duration,
                    'format': gif.format,
                    'mode': gif.mode
                }
                
        except Exception as e:
            logger.error(f"提取GIF元数据失败 {file_path}: {e}")
            return None
    
    def _process_gif_quality(self, 
                           file_path: Path, 
                           quality: str, 
                           metadata: Dict[str, Any]) -> Optional[Path]:
        """根据质量设置处理GIF"""
        try:
            if quality == 'original':
                return file_path
            
            # 确定新尺寸
            width, height = metadata['width'], metadata['height']
            
            if quality == 'compressed':
                # 压缩质量：减少50%尺寸
                new_width = int(width * 0.7)
                new_height = int(height * 0.7)
            elif quality == 'small':
                # 小尺寸：减少70%尺寸
                new_width = int(width * 0.5)
                new_height = int(height * 0.5)
            else:
                return file_path
            
            # 生成新文件名
            stem = file_path.stem
            new_path = file_path.parent / f"{stem}_{quality}.gif"
            
            # 处理GIF
            with Image.open(file_path) as gif:
                frames = []
                durations = []
                
                try:
                    while True:
                        # 调整帧大小
                        frame = gif.copy()
                        frame = frame.resize((new_width, new_height), Image.Resampling.LANCZOS)
                        frames.append(frame)
                        
                        duration = gif.info.get('duration', 100)
                        durations.append(duration)
                        
                        gif.seek(gif.tell() + 1)
                except EOFError:
                    pass
                
                # 保存处理后的GIF
                if frames:
                    frames[0].save(
                        new_path,
                        save_all=True,
                        append_images=frames[1:],
                        duration=durations,
                        loop=0,
                        optimize=True
                    )
                    
                    # 删除原文件
                    file_path.unlink()
                    
                    logger.info(f"GIF质量处理完成: {new_path}")
                    return new_path
            
            return file_path
            
        except Exception as e:
            logger.error(f"GIF质量处理失败 {file_path}: {e}")
            return file_path
    
    def _parse_size_limit(self, size_str: str) -> int:
        """解析大小限制字符串为字节数"""
        if not size_str:
            return 0
        
        size_str = size_str.upper().strip()
        
        if size_str.endswith('KB'):
            return int(float(size_str[:-2]) * 1024)
        elif size_str.endswith('MB') or size_str.endswith('M'):
            unit_str = size_str[:-2] if size_str.endswith('MB') else size_str[:-1]
            return int(float(unit_str) * 1024 * 1024)
        elif size_str.endswith('GB') or size_str.endswith('G'):
            unit_str = size_str[:-2] if size_str.endswith('GB') else size_str[:-1]
            return int(float(unit_str) * 1024 * 1024 * 1024)
        else:
            # 假设是字节
            return int(float(size_str))
    
    def _check_disk_space(self, min_space_mb: int = 100) -> bool:
        """检查磁盘空间是否足够"""
        try:
            stat = os.statvfs(self._download_dir)
            free_space_mb = (stat.f_frsize * stat.f_avail) / (1024 * 1024)
            return free_space_mb > min_space_mb
        except Exception as e:
            logger.warning(f"无法检查磁盘空间: {e}")
            return True  # 假设有足够空间


def create_gif_downloader_tool(download_dir: str) -> GifDownloaderTool:
    """
    创建GIF下载工具实例的工厂函数
    
    Args:
        download_dir: 下载目录路径
        
    Returns:
        配置好的GIF下载工具实例
    """
    return GifDownloaderTool(download_dir=download_dir)


# 使用示例
if __name__ == "__main__":
    import tempfile
    
    # 创建测试工具
    with tempfile.TemporaryDirectory() as temp_dir:
        tool = create_gif_downloader_tool(temp_dir)
        
        # 测试下载直接GIF链接
        test_urls = [
            "https://media.giphy.com/media/3o7abKhOpu0NwenH3O/giphy.gif",
            "https://i.imgur.com/example.gif",
            "https://example.com/sample.gif"
        ]
        
        for test_url in test_urls:
            try:
                result = tool.invoke({
                    "url": test_url,
                    "filename": "test_gif",
                    "quality": "compressed",
                    "max_filesize": "10M",
                    "extract_metadata": True
                })
                
                print(f"下载结果 ({test_url}): {result}")
            except Exception as e:
                print(f"测试失败 ({test_url}): {e}")