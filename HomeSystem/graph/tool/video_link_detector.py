"""
Video Link Extractor Tool

从指定网页中提取所有可用的视频链接和标题。
支持检测iframe嵌入视频、HTML5 video标签和直接视频文件链接。
"""

import re
import requests
from typing import List, Dict, Optional, Any
from urllib.parse import urlparse, urljoin, parse_qs
import json
from bs4 import BeautifulSoup

from langchain_core.tools import BaseTool
from langchain_core.tools.base import ArgsSchema
from pydantic import BaseModel, Field, validator
from loguru import logger


class VideoExtractorInput(BaseModel):
    """视频提取工具输入模型"""
    url: str = Field(description="要提取视频的网页URL")
    include_embeds: bool = Field(default=True, description="包含嵌入式视频(YouTube、Bilibili等)")
    include_direct: bool = Field(default=True, description="包含直接视频文件链接")
    include_video_tags: bool = Field(default=True, description="包含HTML5 video标签")
    
    @validator('url')
    def validate_url(cls, v):
        """验证URL格式"""
        if not v or not v.strip():
            raise ValueError("URL不能为空")
        
        parsed = urlparse(v)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError("无效的URL格式")
        
        return v.strip()


class ExtractedVideo(BaseModel):
    """提取的视频信息模型"""
    video_url: str = Field(description="视频URL")
    title: str = Field(description="视频标题，找不到时为'unknown'")
    platform: str = Field(description="视频平台 (youtube, bilibili, vimeo, direct等)")
    source_type: str = Field(description="来源类型 (embed, direct, video_tag)")
    thumbnail_url: Optional[str] = Field(default=None, description="缩略图URL")
    duration: Optional[str] = Field(default=None, description="视频时长")


class VideoLinkExtractorTool(BaseTool):
    """网页视频链接提取工具"""
    
    name: str = "video_link_extractor"
    description: str = "从指定网页中提取所有视频链接和标题，支持嵌入式视频和直接视频文件"
    args_schema: ArgsSchema = VideoExtractorInput
    return_direct: bool = False
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 初始化requests会话
        object.__setattr__(self, 'session', requests.Session())
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # 支持的视频文件扩展名
        object.__setattr__(self, 'video_extensions', {
            '.mp4', '.webm', '.ogg', '.avi', '.mov', '.mkv', '.flv', '.m4v', '.wmv'
        })
        
        # 视频平台模式
        object.__setattr__(self, 'platform_patterns', {
            'youtube': [
                r'(?:youtube\.com/embed/|youtu\.be/|youtube\.com/watch\?v=)([a-zA-Z0-9_-]{11})',
                r'youtube\.com/embed/([a-zA-Z0-9_-]{11})'
            ],
            'bilibili': [
                r'bilibili\.com/video/(av\d+|BV[a-zA-Z0-9]{10})',
                r'player\.bilibili\.com/player\.html\?.*?(?:aid=(\d+)|bvid=(BV[a-zA-Z0-9]{10}))'
            ],
            'vimeo': [
                r'vimeo\.com/(\d+)',
                r'player\.vimeo\.com/video/(\d+)'
            ],
            'douyin': [
                r'douyin\.com/video/(\d+)',
                r'v\.douyin\.com/[a-zA-Z0-9]+'
            ],
            'kuaishou': [
                r'kuaishou\.com/profile/[^/]+/video/([a-zA-Z0-9]+)',
                r'v\.kuaishou\.com/[a-zA-Z0-9]+'
            ]
        })
    
    def _run(self, 
             url: str, 
             include_embeds: bool = True,
             include_direct: bool = True,
             include_video_tags: bool = True) -> Dict[str, Any]:
        """执行视频提取"""
        try:
            extracted_videos = []
            
            # 获取网页内容
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            base_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
            
            # 检测嵌入式视频
            if include_embeds:
                embed_videos = self._extract_embed_videos(soup, base_url)
                extracted_videos.extend(embed_videos)
            
            # 检测HTML5 video标签
            if include_video_tags:
                video_tag_videos = self._extract_video_tags(soup, base_url)
                extracted_videos.extend(video_tag_videos)
            
            # 检测直接视频文件链接
            if include_direct:
                direct_videos = self._extract_direct_video_links(soup, base_url)
                extracted_videos.extend(direct_videos)
            
            # 去重
            unique_videos = self._deduplicate_videos(extracted_videos)
            
            # 返回结果
            if unique_videos:
                return {
                    "videos": [video.dict() for video in unique_videos],
                    "total_count": len(unique_videos),
                    "platforms_found": list(set([video.platform for video in unique_videos])),
                    "status": "success",
                    "message": f"找到{len(unique_videos)}个视频"
                }
            else:
                return {
                    "videos": [],
                    "total_count": 0,
                    "platforms_found": [],
                    "status": "no_videos_found", 
                    "message": "没有视频"
                }
                
        except Exception as e:
            logger.error(f"视频提取失败 {url}: {e}")
            return {
                "videos": [],
                "total_count": 0,
                "platforms_found": [],
                "status": "error",
                "message": f"提取过程中发生错误: {str(e)}"
            }
    
    def _extract_embed_videos(self, soup: BeautifulSoup, base_url: str) -> List[ExtractedVideo]:
        """提取iframe嵌入视频"""
        videos = []
        
        try:
            iframes = soup.find_all('iframe')
            
            for iframe in iframes:
                src = iframe.get('src', '').strip()
                if not src:
                    continue
                
                # 转换为绝对URL
                if src.startswith('//'):
                    src = 'https:' + src
                elif src.startswith('/'):
                    src = urljoin(base_url, src)
                
                # 检测平台
                platform, video_id = self._detect_platform(src)
                if platform:
                    title = self._extract_iframe_title(iframe, platform, video_id)
                    
                    video = ExtractedVideo(
                        video_url=src,
                        title=title,
                        platform=platform,
                        source_type="embed"
                    )
                    videos.append(video)
                    
        except Exception as e:
            logger.error(f"提取iframe视频失败: {e}")
        
        return videos
    
    def _extract_video_tags(self, soup: BeautifulSoup, base_url: str) -> List[ExtractedVideo]:
        """提取HTML5 video标签"""
        videos = []
        
        try:
            video_tags = soup.find_all('video')
            
            for video_tag in video_tags:
                sources = []
                
                # 获取video标签的src属性
                if video_tag.get('src'):
                    sources.append(video_tag.get('src'))
                
                # 获取source子标签
                source_tags = video_tag.find_all('source')
                for source in source_tags:
                    if source.get('src'):
                        sources.append(source.get('src'))
                
                # 处理每个视频源
                for src in sources:
                    if not src:
                        continue
                    
                    # 转换为绝对URL
                    if src.startswith('/'):
                        src = urljoin(base_url, src)
                    
                    title = self._extract_video_tag_title(video_tag)
                    
                    video = ExtractedVideo(
                        video_url=src,
                        title=title,
                        platform="direct",
                        source_type="video_tag"
                    )
                    videos.append(video)
                    
        except Exception as e:
            logger.error(f"提取video标签失败: {e}")
        
        return videos
    
    def _extract_direct_video_links(self, soup: BeautifulSoup, base_url: str) -> List[ExtractedVideo]:
        """提取直接视频文件链接"""
        videos = []
        
        try:
            # 查找所有链接
            links = soup.find_all('a', href=True)
            
            for link in links:
                href = link.get('href', '').strip()
                if not href:
                    continue
                
                # 转换为绝对URL
                if href.startswith('/'):
                    href = urljoin(base_url, href)
                
                # 检查是否为视频文件
                parsed_url = urlparse(href)
                path_lower = parsed_url.path.lower()
                
                if any(path_lower.endswith(ext) for ext in self.video_extensions):
                    title = self._extract_link_title(link, href)
                    
                    video = ExtractedVideo(
                        video_url=href,
                        title=title,
                        platform="direct",
                        source_type="direct"
                    )
                    videos.append(video)
                    
        except Exception as e:
            logger.error(f"提取直接视频链接失败: {e}")
        
        return videos
    
    def _detect_platform(self, url: str) -> tuple[str, str]:
        """检测视频平台"""
        try:
            for platform, patterns in self.platform_patterns.items():
                for pattern in patterns:
                    match = re.search(pattern, url, re.IGNORECASE)
                    if match:
                        video_id = match.group(1) if match.groups() else "unknown"
                        return platform, video_id
            
            return "unknown", "unknown"
            
        except Exception as e:
            logger.error(f"平台检测失败 {url}: {e}")
            return "unknown", "unknown"
    
    def _extract_iframe_title(self, iframe, platform: str, video_id: str) -> str:
        """提取iframe视频标题"""
        try:
            # 尝试从iframe的title属性获取
            title = iframe.get('title', '').strip()
            if title:
                return title
            
            # 尝试从iframe的data-title属性获取
            data_title = iframe.get('data-title', '').strip()
            if data_title:
                return data_title
            
            # 尝试从周围的文本内容获取
            parent = iframe.parent
            if parent:
                # 查找父级元素中的标题
                title_elements = parent.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'title'])
                for elem in title_elements:
                    text = elem.get_text().strip()
                    if text and len(text) < 200:  # 避免过长的文本
                        return text
            
            return "unknown"
            
        except Exception as e:
            logger.error(f"提取iframe标题失败: {e}")
            return "unknown"
    
    def _extract_video_tag_title(self, video_tag) -> str:
        """提取video标签标题"""
        try:
            # 从title属性获取
            title = video_tag.get('title', '').strip()
            if title:
                return title
            
            # 从data-title属性获取
            data_title = video_tag.get('data-title', '').strip()
            if data_title:
                return data_title
            
            # 从父级元素获取
            parent = video_tag.parent
            if parent:
                title_elements = parent.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
                for elem in title_elements:
                    text = elem.get_text().strip()
                    if text and len(text) < 200:
                        return text
            
            return "unknown"
            
        except Exception as e:
            logger.error(f"提取video标签标题失败: {e}")
            return "unknown"
    
    def _extract_link_title(self, link, href: str) -> str:
        """提取链接标题"""
        try:
            # 从链接文本获取
            link_text = link.get_text().strip()
            if link_text and len(link_text) < 200:
                return link_text
            
            # 从title属性获取
            title = link.get('title', '').strip()
            if title:
                return title
            
            # 从文件名获取
            parsed_url = urlparse(href)
            filename = parsed_url.path.split('/')[-1]
            if filename:
                # 移除文件扩展名
                name_without_ext = filename.rsplit('.', 1)[0]
                if name_without_ext:
                    return name_without_ext
            
            return "unknown"
            
        except Exception as e:
            logger.error(f"提取链接标题失败: {e}")
            return "unknown"
    
    def _deduplicate_videos(self, videos: List[ExtractedVideo]) -> List[ExtractedVideo]:
        """去重视频列表"""
        seen_urls = set()
        unique_videos = []
        
        for video in videos:
            if video.video_url not in seen_urls:
                seen_urls.add(video.video_url)
                unique_videos.append(video)
        
        return unique_videos


def create_video_link_extractor_tool() -> VideoLinkExtractorTool:
    """创建视频链接提取工具实例"""
    return VideoLinkExtractorTool()


# 使用示例
if __name__ == "__main__":
    tool = create_video_link_extractor_tool()
    
    # 测试URL
    test_urls = [
        "https://example.com/page-with-videos",  # 替换为实际测试URL
    ]
    
    for test_url in test_urls:
        try:
            result = tool.invoke({
                "url": test_url,
                "include_embeds": True,
                "include_direct": True,
                "include_video_tags": True
            })
            
            print(f"提取结果 ({test_url}):")
            print(json.dumps(result, indent=2, ensure_ascii=False))
            
        except Exception as e:
            print(f"测试失败 ({test_url}): {e}")