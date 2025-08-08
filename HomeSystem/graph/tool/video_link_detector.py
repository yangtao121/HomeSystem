"""
Video Link Detection Tool

检测文本中的视频链接，支持多个平台，提取视频标题，并可选择使用LLM分析模糊链接。
"""

import re
import requests
from typing import List, Dict, Optional, Any, ClassVar
from urllib.parse import urlparse, parse_qs
import json
from bs4 import BeautifulSoup

from langchain_core.tools import BaseTool
from langchain_core.tools.base import ArgsSchema
from pydantic import BaseModel, Field
from loguru import logger

from ..llm_factory import LLMFactory


class VideoLinkDetectorInput(BaseModel):
    """Video link detector tool input schema"""
    text: str = Field(description="The text content to search for video links")
    extract_titles: bool = Field(default=True, description="Whether to extract video titles")
    use_llm_analysis: bool = Field(default=False, description="Whether to use LLM for ambiguous URL analysis")


class VideoInfo(BaseModel):
    """Video information model"""
    url: str = Field(description="Original video URL")
    platform: str = Field(description="Video platform (youtube, bilibili, etc.)")
    video_id: str = Field(description="Extracted video ID")
    title: str = Field(description="Video title or 'Unknown video link' if not found")
    status: str = Field(description="Detection status: valid, invalid, unknown")
    confidence: float = Field(description="Detection confidence (0.0 - 1.0)")


class VideoLinkDetectorTool(BaseTool):
    """Video link detection tool for LangGraph agents"""
    
    name: str = "video_link_detector"
    description: str = "Detect video links from text content and extract video information including titles"
    args_schema: ArgsSchema = VideoLinkDetectorInput
    return_direct: bool = False
    
    
    # Video platform patterns
    PLATFORM_PATTERNS: ClassVar[Dict[str, List[str]]] = {
        'youtube': [
            r'(?:https?:)?(?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:embed\/|v\/|watch\?v=|watch\?.+&v=)|youtu\.be\/|youtube\.googleapis\.com\/v\/)([^#\&\?\n\s]{11})',
            r'(?:https?:)?(?:\/\/)?(?:www\.)?youtube\.com\/watch\?(?:[^&\n\s]*&)*v=([^#\&\?\n\s]{11})',
            r'(?:https?:)?(?:\/\/)?youtu\.be\/([^#\&\?\n\s]{11})'
        ],
        'bilibili': [
            r'(?:https?:)?(?:\/\/)?(?:www\.)?bilibili\.com\/video\/(av\d+|BV[a-zA-Z0-9]{10})',
            r'(?:https?:)?(?:\/\/)?(?:www\.)?bilibili\.com\/video\/(av\d+)',
            r'(?:https?:)?(?:\/\/)?(?:www\.)?bilibili\.com\/video\/(BV[a-zA-Z0-9]{10})',
            r'(?:https?:)?(?:\/\/)?b23\.tv\/[a-zA-Z0-9]+'
        ],
        'vimeo': [
            r'(?:https?:)?(?:\/\/)?(?:www\.)?vimeo\.com\/(\d+)',
            r'(?:https?:)?(?:\/\/)?vimeo\.com\/channels\/[^\/]+\/(\d+)',
            r'(?:https?:)?(?:\/\/)?player\.vimeo\.com\/video\/(\d+)'
        ],
        'douyin': [
            r'(?:https?:)?(?:\/\/)?(?:www\.)?douyin\.com\/video\/(\d+)',
            r'(?:https?:)?(?:\/\/)?v\.douyin\.com\/[a-zA-Z0-9]+',
            r'(?:https?:)?(?:\/\/)?iesdouyin\.com\/share\/video\/(\d+)'
        ],
        'kuaishou': [
            r'(?:https?:)?(?:\/\/)?(?:www\.)?kuaishou\.com\/profile\/[^\/]+\/video\/([a-zA-Z0-9]+)',
            r'(?:https?:)?(?:\/\/)?v\.kuaishou\.com\/[a-zA-Z0-9]+',
            r'(?:https?:)?(?:\/\/)?kslive\.kuaishou\.com\/u\/[^\/]+\/[a-zA-Z0-9]+'
        ],
        'weibo': [
            r'(?:https?:)?(?:\/\/)?(?:www\.)?weibo\.com\/tv\/show\/(\d+:\w+)',
            r'(?:https?:)?(?:\/\/)?video\.weibo\.com\/show\?fid=(\d+:\w+)',
            r'(?:https?:)?(?:\/\/)?m\.weibo\.cn\/status\/(\d+)'
        ],
        'dailymotion': [
            r'(?:https?:)?(?:\/\/)?(?:www\.)?dailymotion\.com\/video\/([a-zA-Z0-9]+)',
            r'(?:https?:)?(?:\/\/)?dai\.ly\/([a-zA-Z0-9]+)'
        ],
        'twitch': [
            r'(?:https?:)?(?:\/\/)?(?:www\.)?twitch\.tv\/videos\/(\d+)',
            r'(?:https?:)?(?:\/\/)?(?:www\.)?twitch\.tv\/[^\/]+\/clip\/([a-zA-Z0-9_-]+)',
            r'(?:https?:)?(?:\/\/)?clips\.twitch\.tv\/([a-zA-Z0-9_-]+)'
        ]
    }
    
    def __init__(self, llm_factory: Optional[LLMFactory] = None):
        super().__init__()
        # Initialize as instance variables (not Pydantic fields)
        object.__setattr__(self, 'llm_factory', llm_factory)
        object.__setattr__(self, 'session', requests.Session())
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def _run(self, text: str, extract_titles: bool = True, use_llm_analysis: bool = False) -> Dict[str, Any]:
        """Run the video link detection tool"""
        try:
            detected_videos = []
            
            # Extract all URLs from text
            url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
            urls = re.findall(url_pattern, text)
            
            # Also find potential URLs without protocol
            potential_urls = re.findall(r'(?:www\.)?[a-zA-Z0-9][a-zA-Z0-9-]{1,61}[a-zA-Z0-9]?\.[a-zA-Z]{2,}(?:/[^\s]*)?', text)
            
            # Combine and deduplicate URLs
            all_urls = list(set(urls + [f"https://{url}" for url in potential_urls if not url.startswith('http')]))
            
            for url in all_urls:
                video_info = self._analyze_url(url, extract_titles, use_llm_analysis)
                if video_info:
                    detected_videos.append(video_info)
            
            return {
                "detected_videos": [video.dict() for video in detected_videos],
                "total_count": len(detected_videos),
                "platforms_found": list(set([video.platform for video in detected_videos])),
                "status": "success"
            }
            
        except Exception as e:
            logger.error(f"Video link detection failed: {e}")
            return {
                "detected_videos": [],
                "total_count": 0,
                "platforms_found": [],
                "status": "error",
                "error": str(e)
            }
    
    def _analyze_url(self, url: str, extract_titles: bool, use_llm_analysis: bool) -> Optional[VideoInfo]:
        """Analyze a single URL for video content"""
        try:
            # Clean URL
            url = url.strip()
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            
            # Check against platform patterns
            for platform, patterns in self.PLATFORM_PATTERNS.items():
                for pattern in patterns:
                    match = re.search(pattern, url, re.IGNORECASE)
                    if match:
                        video_id = match.group(1) if match.groups() else "unknown"
                        
                        video_info = VideoInfo(
                            url=url,
                            platform=platform,
                            video_id=video_id,
                            title="Unknown video link",
                            status="detected",
                            confidence=0.9
                        )
                        
                        if extract_titles:
                            video_info.title = self._extract_title(url, platform, video_id)
                        
                        return video_info
            
            # If no pattern matches, try LLM analysis
            if use_llm_analysis:
                return self._llm_analyze_url(url)
            
            return None
            
        except Exception as e:
            logger.error(f"URL analysis failed for {url}: {e}")
            return None
    
    def _extract_title(self, url: str, platform: str, video_id: str) -> str:
        """Extract video title from URL"""
        try:
            if platform == 'youtube':
                return self._extract_youtube_title(video_id)
            elif platform == 'bilibili':
                return self._extract_bilibili_title(url, video_id)
            elif platform == 'vimeo':
                return self._extract_vimeo_title(video_id)
            else:
                return self._extract_generic_title(url)
        except Exception as e:
            logger.error(f"Title extraction failed for {url}: {e}")
            return "Unknown video link"
    
    def _extract_youtube_title(self, video_id: str) -> str:
        """Extract YouTube video title"""
        try:
            # Try to extract from webpage since API requires key
            url = f"https://www.youtube.com/watch?v={video_id}"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Try different methods to find title
            title_elem = soup.find('meta', property='og:title')
            if title_elem:
                title = title_elem.get('content', '').strip()
                if title and title != 'YouTube':
                    return title
            
            # Try to find title in page title tag
            title_elem = soup.find('title')
            if title_elem:
                title = title_elem.get_text().strip()
                if title and title != 'YouTube' and ' - YouTube' in title:
                    clean_title = title.replace(' - YouTube', '').strip()
                    if clean_title:
                        return clean_title
            
            # Try to find title in JSON-LD data
            scripts = soup.find_all('script', type='application/ld+json')
            for script in scripts:
                try:
                    data = json.loads(script.string)
                    if isinstance(data, dict) and 'name' in data:
                        title = data['name'].strip()
                        if title:
                            return title
                except:
                    continue
            
            # Try to find in ytInitialPlayerResponse
            for script in soup.find_all('script'):
                script_text = script.string
                if script_text and 'ytInitialPlayerResponse' in script_text:
                    try:
                        # Look for title in the script
                        import re
                        title_match = re.search(r'"title":"([^"]+)"', script_text)
                        if title_match:
                            title = title_match.group(1).strip()
                            # Decode unicode sequences
                            title = title.encode().decode('unicode_escape')
                            if title and len(title) > 5:  # Filter out very short matches
                                return title
                    except:
                        continue
            
            return "Unknown video link"
            
        except Exception as e:
            logger.error(f"YouTube title extraction failed: {e}")
            return "Unknown video link"
    
    def _extract_bilibili_title(self, url: str, video_id: str) -> str:
        """Extract Bilibili video title"""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Try different methods
            title_elem = soup.find('meta', property='og:title')
            if title_elem:
                return title_elem.get('content', 'Unknown video link')
            
            title_elem = soup.find('title')
            if title_elem:
                title = title_elem.get_text().strip()
                if title and '哔哩哔哩' not in title:
                    return title.split('_')[0].strip()
            
            # Try to find h1 title
            h1_elem = soup.find('h1', {'data-title': True})
            if h1_elem:
                return h1_elem.get('data-title', 'Unknown video link')
            
            return "Unknown video link"
            
        except Exception as e:
            logger.error(f"Bilibili title extraction failed: {e}")
            return "Unknown video link"
    
    def _extract_vimeo_title(self, video_id: str) -> str:
        """Extract Vimeo video title"""
        try:
            url = f"https://vimeo.com/{video_id}"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            title_elem = soup.find('meta', property='og:title')
            if title_elem:
                return title_elem.get('content', 'Unknown video link')
            
            return "Unknown video link"
            
        except Exception as e:
            logger.error(f"Vimeo title extraction failed: {e}")
            return "Unknown video link"
    
    def _extract_generic_title(self, url: str) -> str:
        """Extract title from generic webpage"""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Try og:title first
            title_elem = soup.find('meta', property='og:title')
            if title_elem:
                return title_elem.get('content', 'Unknown video link')
            
            # Try title tag
            title_elem = soup.find('title')
            if title_elem:
                title = title_elem.get_text().strip()
                if title and len(title) > 0:
                    return title
            
            return "Unknown video link"
            
        except Exception as e:
            logger.error(f"Generic title extraction failed: {e}")
            return "Unknown video link"
    
    def _llm_analyze_url(self, url: str) -> Optional[VideoInfo]:
        """Use LLM to analyze potentially ambiguous URLs"""
        try:
            if not self.llm_factory:
                return None
            
            if not hasattr(self.llm_factory, 'available_llm_models') or not self.llm_factory.available_llm_models:
                return None
            
            # Get first available LLM model
            model_name = list(self.llm_factory.available_llm_models.keys())[0]
            llm = self.llm_factory.create_chat_model(model_name)
            
            prompt = f"""
            分析以下URL是否为视频链接，如果是，请识别平台类型：
            
            URL: {url}
            
            请回答：
            1. 这是视频链接吗？(是/否)
            2. 如果是，属于哪个平台？(youtube/bilibili/douyin/kuaishou/weibo/vimeo/dailymotion/twitch/其他)
            3. 可信度评分 (0.0-1.0)
            
            只需要用JSON格式回答：
            {{"is_video": true/false, "platform": "platform_name", "confidence": 0.0-1.0}}
            """
            
            response = llm.invoke(prompt)
            result = json.loads(response.content)
            
            if result.get('is_video') and result.get('confidence', 0) > 0.5:
                return VideoInfo(
                    url=url,
                    platform=result.get('platform', 'unknown'),
                    video_id='llm_detected',
                    title='Unknown video link',
                    status='llm_detected',
                    confidence=result.get('confidence', 0.5)
                )
            
            return None
            
        except Exception as e:
            logger.error(f"LLM analysis failed for {url}: {e}")
            return None


def create_video_link_detector_tool(llm_factory: Optional[LLMFactory] = None) -> VideoLinkDetectorTool:
    """Create a video link detector tool instance
    
    Args:
        llm_factory: Optional LLM factory for advanced URL analysis. 
                    If not provided, only pattern matching will be used.
    """
    return VideoLinkDetectorTool(llm_factory=llm_factory)