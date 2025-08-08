"""
GIF Detection Tool

检测文本中的GIF链接，支持多个平台，提取GIF元数据，并可选择使用LLM分析模糊链接。
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


class GifDetectorInput(BaseModel):
    """GIF detector tool input schema"""
    text: str = Field(description="The text content to search for GIF links")
    extract_metadata: bool = Field(default=True, description="Whether to extract GIF metadata")
    validate_content: bool = Field(default=True, description="Whether to validate that URLs actually contain GIF content")
    use_llm_analysis: bool = Field(default=False, description="Whether to use LLM for ambiguous URL analysis")


class GifInfo(BaseModel):
    """GIF information model"""
    url: str = Field(description="Original GIF URL")
    normalized_url: str = Field(description="Normalized/direct GIF URL if different from original")
    platform: str = Field(description="GIF platform (giphy, tenor, imgur, etc.)")
    gif_id: str = Field(description="Extracted GIF ID")
    title: str = Field(description="GIF title or description")
    tags: List[str] = Field(default=[], description="GIF tags or keywords")
    width: Optional[int] = Field(default=None, description="GIF width in pixels")
    height: Optional[int] = Field(default=None, description="GIF height in pixels")
    file_size: Optional[int] = Field(default=None, description="GIF file size in bytes")
    status: str = Field(description="Detection status: valid, invalid, unknown")
    confidence: float = Field(description="Detection confidence (0.0 - 1.0)")


class GifDetectorTool(BaseTool):
    """GIF detection tool for LangGraph agents"""
    
    name: str = "gif_detector"
    description: str = "Detect GIF links from text content and extract GIF metadata including titles, tags, and properties"
    args_schema: ArgsSchema = GifDetectorInput
    return_direct: bool = False
    
    
    # GIF platform patterns
    PLATFORM_PATTERNS: ClassVar[Dict[str, List[str]]] = {
        'giphy': [
            r'(?:https?:)?(?:\/\/)?(?:www\.)?giphy\.com\/gifs\/[^\/\s]*-([a-zA-Z0-9]+)',
            r'(?:https?:)?(?:\/\/)?gph\.is\/([a-zA-Z0-9]+)',
            r'(?:https?:)?(?:\/\/)?media\.giphy\.com\/media\/([a-zA-Z0-9]+)',
            r'(?:https?:)?(?:\/\/)?giphy\.com\/embed\/([a-zA-Z0-9]+)',
            r'(?:https?:)?(?:\/\/)?i\.giphy\.com\/([a-zA-Z0-9]+)\.gif'
        ],
        'tenor': [
            r'(?:https?:)?(?:\/\/)?(?:www\.)?tenor\.com\/view\/[^\/\s]*-(\d+)',
            r'(?:https?:)?(?:\/\/)?tenor\.com\/(\d+)\.gif',
            r'(?:https?:)?(?:\/\/)?media\.tenor\.com\/[^\/\s]*\/([^\/\s]+)\.gif',
            r'(?:https?:)?(?:\/\/)?c\.tenor\.com\/[^\/\s]*\/([^\/\s]+)\.gif'
        ],
        'imgur': [
            r'(?:https?:)?(?:\/\/)?(?:www\.)?imgur\.com\/([a-zA-Z0-9]+)\.gif',
            r'(?:https?:)?(?:\/\/)?i\.imgur\.com\/([a-zA-Z0-9]+)\.gif',
            r'(?:https?:)?(?:\/\/)?imgur\.com\/gallery\/([a-zA-Z0-9]+)',
            r'(?:https?:)?(?:\/\/)?imgur\.com\/a\/([a-zA-Z0-9]+)'
        ],
        'reddit': [
            r'(?:https?:)?(?:\/\/)?i\.redd\.it\/([^\/\s]+\.gif)',
            r'(?:https?:)?(?:\/\/)?v\.redd\.it\/([a-zA-Z0-9]+)',
            r'(?:https?:)?(?:\/\/)?preview\.redd\.it\/([^\/\s]+\.gif)'
        ],
        'twitter': [
            r'(?:https?:)?(?:\/\/)?pbs\.twimg\.com\/tweet_video\/([^\/\s]+\.gif)',
            r'(?:https?:)?(?:\/\/)?video\.twimg\.com\/tweet_video\/([^\/\s]+\.gif)',
            r'(?:https?:)?(?:\/\/)?pbs\.twimg\.com\/media\/([^\/\s]+\.gif)'
        ],
        'tumblr': [
            r'(?:https?:)?(?:\/\/)?media\.tumblr\.com\/([a-zA-Z0-9]+)\/[^\/\s]*\.gif',
            r'(?:https?:)?(?:\/\/)?[^\.]+\.media\.tumblr\.com\/([a-zA-Z0-9]+)\/[^\/\s]*\.gif'
        ],
        'discord': [
            r'(?:https?:)?(?:\/\/)?cdn\.discordapp\.com\/attachments\/\d+\/\d+\/([^\/\s]+\.gif)',
            r'(?:https?:)?(?:\/\/)?media\.discordapp\.net\/attachments\/\d+\/\d+\/([^\/\s]+\.gif)'
        ],
        'direct': [
            r'(?:https?:)?(?:\/\/)?[^\/\s]+\/[^\/\s]*\.gif(?:\?[^\/\s]*)?'
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
    
    def _run(self, text: str, extract_metadata: bool = True, validate_content: bool = True, use_llm_analysis: bool = False) -> Dict[str, Any]:
        """Run the GIF detection tool"""
        try:
            detected_gifs = []
            
            # Extract all URLs from text
            url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
            urls = re.findall(url_pattern, text)
            
            # Also find potential URLs without protocol
            potential_urls = re.findall(r'(?:www\.)?[a-zA-Z0-9][a-zA-Z0-9-]{1,61}[a-zA-Z0-9]?\.[a-zA-Z]{2,}(?:/[^\s]*)?', text)
            
            # Combine and deduplicate URLs
            all_urls = list(set(urls + [f"https://{url}" for url in potential_urls if not url.startswith('http')]))
            
            for url in all_urls:
                gif_info = self._analyze_url(url, extract_metadata, validate_content, use_llm_analysis)
                if gif_info:
                    detected_gifs.append(gif_info)
            
            return {
                "detected_gifs": [gif.dict() for gif in detected_gifs],
                "total_count": len(detected_gifs),
                "platforms_found": list(set([gif.platform for gif in detected_gifs])),
                "status": "success"
            }
            
        except Exception as e:
            logger.error(f"GIF detection failed: {e}")
            return {
                "detected_gifs": [],
                "total_count": 0,
                "platforms_found": [],
                "status": "error",
                "error": str(e)
            }
    
    def _analyze_url(self, url: str, extract_metadata: bool, validate_content: bool, use_llm_analysis: bool) -> Optional[GifInfo]:
        """Analyze a single URL for GIF content"""
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
                        gif_id = match.group(1) if match.groups() else "unknown"
                        
                        gif_info = GifInfo(
                            url=url,
                            normalized_url=url,
                            platform=platform,
                            gif_id=gif_id,
                            title="Unknown GIF",
                            tags=[],
                            status="detected",
                            confidence=0.9
                        )
                        
                        # Extract metadata if requested
                        if extract_metadata:
                            self._extract_metadata(gif_info, platform, gif_id)
                        
                        # Validate content if requested
                        if validate_content:
                            self._validate_gif_content(gif_info)
                        
                        return gif_info
            
            # If no pattern matches, try LLM analysis
            if use_llm_analysis:
                return self._llm_analyze_url(url)
            
            return None
            
        except Exception as e:
            logger.error(f"URL analysis failed for {url}: {e}")
            return None
    
    def _extract_metadata(self, gif_info: GifInfo, platform: str, gif_id: str) -> None:
        """Extract metadata for a GIF from its platform"""
        try:
            if platform == 'giphy':
                self._extract_giphy_metadata(gif_info, gif_id)
            elif platform == 'tenor':
                self._extract_tenor_metadata(gif_info, gif_id)
            elif platform == 'imgur':
                self._extract_imgur_metadata(gif_info, gif_id)
            elif platform == 'direct':
                self._extract_generic_metadata(gif_info)
            else:
                self._extract_generic_metadata(gif_info)
        except Exception as e:
            logger.error(f"Metadata extraction failed for {gif_info.url}: {e}")
    
    def _extract_giphy_metadata(self, gif_info: GifInfo, gif_id: str) -> None:
        """Extract metadata from Giphy"""
        try:
            response = self.session.get(gif_info.url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Try to get title
            title_elem = soup.find('meta', property='og:title')
            if title_elem:
                gif_info.title = title_elem.get('content', 'Unknown GIF')
            
            # Try to get description/tags
            desc_elem = soup.find('meta', property='og:description')
            if desc_elem:
                desc = desc_elem.get('content', '')
                if desc:
                    # Extract tags from description
                    gif_info.tags = [tag.strip() for tag in desc.split(',') if tag.strip()]
            
            # Try to find dimensions
            try:
                scripts = soup.find_all('script')
                for script in scripts:
                    if script.string and 'width' in script.string and 'height' in script.string:
                        width_match = re.search(r'"width":(\d+)', script.string)
                        height_match = re.search(r'"height":(\d+)', script.string)
                        if width_match and height_match:
                            gif_info.width = int(width_match.group(1))
                            gif_info.height = int(height_match.group(1))
                            break
            except:
                pass
                
        except Exception as e:
            logger.error(f"Giphy metadata extraction failed: {e}")
    
    def _extract_tenor_metadata(self, gif_info: GifInfo, gif_id: str) -> None:
        """Extract metadata from Tenor"""
        try:
            response = self.session.get(gif_info.url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Try to get title
            title_elem = soup.find('meta', property='og:title')
            if title_elem:
                title = title_elem.get('content', '')
                if title and ' GIF' in title:
                    gif_info.title = title.replace(' GIF', '').strip()
                elif title:
                    gif_info.title = title
            
            # Try to get keywords
            keywords_elem = soup.find('meta', attrs={'name': 'keywords'})
            if keywords_elem:
                keywords = keywords_elem.get('content', '')
                if keywords:
                    gif_info.tags = [tag.strip() for tag in keywords.split(',') if tag.strip()]
                    
        except Exception as e:
            logger.error(f"Tenor metadata extraction failed: {e}")
    
    def _extract_imgur_metadata(self, gif_info: GifInfo, gif_id: str) -> None:
        """Extract metadata from Imgur"""
        try:
            response = self.session.get(gif_info.url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Try to get title
            title_elem = soup.find('meta', property='og:title')
            if title_elem:
                gif_info.title = title_elem.get('content', 'Unknown GIF')
            
            # Try to get description
            desc_elem = soup.find('meta', property='og:description')
            if desc_elem:
                desc = desc_elem.get('content', '')
                if desc and desc != gif_info.title:
                    gif_info.tags = [desc.strip()]
                    
        except Exception as e:
            logger.error(f"Imgur metadata extraction failed: {e}")
    
    def _extract_generic_metadata(self, gif_info: GifInfo) -> None:
        """Extract metadata from generic webpage"""
        try:
            response = self.session.get(gif_info.url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Try og:title first
            title_elem = soup.find('meta', property='og:title')
            if title_elem:
                gif_info.title = title_elem.get('content', 'Unknown GIF')
            else:
                # Try title tag
                title_elem = soup.find('title')
                if title_elem:
                    title = title_elem.get_text().strip()
                    if title:
                        gif_info.title = title
                        
        except Exception as e:
            logger.error(f"Generic metadata extraction failed: {e}")
    
    def _validate_gif_content(self, gif_info: GifInfo) -> None:
        """Validate that URL actually contains GIF content and extract file properties"""
        try:
            # Try to get direct GIF URL if possible
            direct_url = self._get_direct_gif_url(gif_info)
            if direct_url:
                gif_info.normalized_url = direct_url
            
            # Make HEAD request to check content type and size
            response = self.session.head(gif_info.normalized_url, timeout=10, allow_redirects=True)
            
            if response.status_code == 200:
                content_type = response.headers.get('content-type', '').lower()
                
                if 'image/gif' in content_type:
                    gif_info.status = "valid"
                    gif_info.confidence = 1.0
                elif 'image/' in content_type:
                    gif_info.status = "image_not_gif"
                    gif_info.confidence = 0.3
                else:
                    gif_info.status = "not_image"
                    gif_info.confidence = 0.1
                
                # Extract file size
                content_length = response.headers.get('content-length')
                if content_length:
                    gif_info.file_size = int(content_length)
                
                # Try to extract dimensions from headers if available
                self._extract_dimensions_from_response(gif_info, response)
            else:
                gif_info.status = "inaccessible"
                gif_info.confidence = 0.2
                
        except Exception as e:
            logger.error(f"GIF validation failed for {gif_info.url}: {e}")
            gif_info.status = "validation_failed"
            gif_info.confidence = 0.5
    
    def _get_direct_gif_url(self, gif_info: GifInfo) -> Optional[str]:
        """Try to get direct GIF URL for better validation"""
        try:
            if gif_info.platform == 'giphy':
                # Convert to media URL
                if gif_info.gif_id != "unknown":
                    return f"https://media.giphy.com/media/{gif_info.gif_id}/giphy.gif"
            elif gif_info.platform == 'tenor':
                # For Tenor, we need to parse the page to get direct URL
                response = self.session.get(gif_info.url, timeout=10)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Look for direct GIF URL in meta tags
                gif_meta = soup.find('meta', property='og:image')
                if gif_meta:
                    gif_url = gif_meta.get('content', '')
                    if gif_url.endswith('.gif'):
                        return gif_url
                        
                # Look for video/gif URLs in script tags
                scripts = soup.find_all('script')
                for script in scripts:
                    if script.string and 'gif' in script.string:
                        gif_match = re.search(r'"gif":\{"url":"([^"]+\.gif)"', script.string)
                        if gif_match:
                            return gif_match.group(1).replace('\\', '')
            
            elif gif_info.platform == 'imgur':
                # Imgur direct URLs
                if gif_info.gif_id != "unknown" and not gif_info.url.endswith('.gif'):
                    return f"https://i.imgur.com/{gif_info.gif_id}.gif"
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get direct GIF URL for {gif_info.url}: {e}")
            return None
    
    def _extract_dimensions_from_response(self, gif_info: GifInfo, response: requests.Response) -> None:
        """Try to extract dimensions from response headers or make partial content request"""
        try:
            # Some servers provide dimensions in custom headers
            width_header = response.headers.get('x-image-width') or response.headers.get('image-width')
            height_header = response.headers.get('x-image-height') or response.headers.get('image-height')
            
            if width_header and height_header:
                gif_info.width = int(width_header)
                gif_info.height = int(height_header)
                return
            
            # If no dimensions in headers and file is reasonably small, download beginning to check
            file_size = gif_info.file_size or 0
            if file_size > 0 and file_size < 5 * 1024 * 1024:  # Less than 5MB
                try:
                    # Download first 1KB to check GIF header
                    partial_response = self.session.get(
                        gif_info.normalized_url, 
                        headers={'Range': 'bytes=0-1023'}, 
                        timeout=10
                    )
                    
                    if partial_response.status_code in [200, 206]:
                        content = partial_response.content
                        if content.startswith(b'GIF'):
                            # Parse GIF header for dimensions
                            if len(content) >= 10:
                                width = int.from_bytes(content[6:8], byteorder='little')
                                height = int.from_bytes(content[8:10], byteorder='little')
                                if width > 0 and height > 0:
                                    gif_info.width = width
                                    gif_info.height = height
                except:
                    pass  # Ignore errors in partial download
                    
        except Exception as e:
            logger.error(f"Failed to extract dimensions from response: {e}")
    
    def _llm_analyze_url(self, url: str) -> Optional[GifInfo]:
        """Use LLM to analyze potentially ambiguous URLs for GIF content"""
        try:
            if not self.llm_factory:
                return None
            
            if not hasattr(self.llm_factory, 'available_llm_models') or not self.llm_factory.available_llm_models:
                return None
            
            # Get first available LLM model
            model_name = list(self.llm_factory.available_llm_models.keys())[0]
            llm = self.llm_factory.create_chat_model(model_name)
            
            prompt = f"""
            分析以下URL是否为GIF链接，如果是，请识别平台类型：
            
            URL: {url}
            
            请回答：
            1. 这是GIF链接吗？(是/否)
            2. 如果是，属于哪个平台？(giphy/tenor/imgur/reddit/twitter/tumblr/discord/direct/其他)
            3. 可信度评分 (0.0-1.0)
            4. 如果能识别，请提供GIF标题或描述
            
            只需要用JSON格式回答：
            {{"is_gif": true/false, "platform": "platform_name", "confidence": 0.0-1.0, "title": "gif_title_or_description"}}
            """
            
            response = llm.invoke(prompt)
            result = json.loads(response.content)
            
            if result.get('is_gif') and result.get('confidence', 0) > 0.5:
                return GifInfo(
                    url=url,
                    normalized_url=url,
                    platform=result.get('platform', 'unknown'),
                    gif_id='llm_detected',
                    title=result.get('title', 'Unknown GIF'),
                    tags=[],
                    status='llm_detected',
                    confidence=result.get('confidence', 0.5)
                )
            
            return None
            
        except Exception as e:
            logger.error(f"LLM analysis failed for {url}: {e}")
            return None


def create_gif_detector_tool(llm_factory: Optional[LLMFactory] = None) -> GifDetectorTool:
    """Create a GIF detector tool instance
    
    Args:
        llm_factory: Optional LLM factory for advanced URL analysis. 
                    If not provided, only pattern matching will be used.
    """
    return GifDetectorTool(llm_factory=llm_factory)