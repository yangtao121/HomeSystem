# 移除 langchain_community 依赖，直接使用 ArXiv API
from loguru import logger
import pprint
from tqdm import tqdm
import os
import re
from datetime import datetime
import io
from typing import Optional
from enum import Enum

import requests
import xml.etree.ElementTree as ET
import urllib.parse
import time
import feedparser

# 基础PDF处理导入
import fitz  # PyMuPDF - 基础包，肯定有的

# OCR 相关导入
try:
    from paddleocr import PPStructureV3
    from PIL import Image
    import numpy as np
    OCR_AVAILABLE = True
except ImportError:
    # OCR 功能不可用，但不影响基本功能
    OCR_AVAILABLE = False
    pass

from pathlib import Path


class ArxivSearchMode(Enum):
    """ArXiv搜索模式枚举"""
    LATEST = "latest"                    # 最新论文 (按提交日期降序)
    MOST_RELEVANT = "most_relevant"      # 最相关 (按相关性排序)
    RECENTLY_UPDATED = "recently_updated" # 最近更新 (按更新日期降序)
    DATE_RANGE = "date_range"            # 指定年份范围
    AFTER_YEAR = "after_year"            # 某年之后的论文


class ArxivData:
    def __init__(self, result: Optional[dict] = None):
        """
        用于存储单条arxiv 的搜索结果。
        输入的 result 可以包含的 key 如下：
        - title: 标题
        - link: 链接
        - snippet: 摘要
        - categories: 分类
        :param result: 单条搜索结果，可以为None
        :type result: dict or None
        """
        self.title = None
        self.link = None
        self.snippet = None
        self.categories = None
        self.authors = None

        if result is not None:
            for key, value in result.items():
                setattr(self, key, value)

        # 获取pdf链接
        self.pdf_link = self.link.replace("abs", "pdf") if self.link else ""

        self.pdf = None

        self.pdf_path = None

        # 论文的tag
        self.tag: list[str] = []
        
        # OCR识别结果
        self.ocr_result: Optional[str] = None
        
        # PaddleOCR结构化识别结果
        self.paddle_ocr_result: Optional[str] = None
        self.paddle_ocr_images: dict = {}
        
        # 结构化摘要字段
        self.research_background: Optional[str] = None
        self.research_objectives: Optional[str] = None
        self.methods: Optional[str] = None
        self.key_findings: Optional[str] = None
        self.conclusions: Optional[str] = None
        self.limitations: Optional[str] = None
        self.future_work: Optional[str] = None
        self.keywords: Optional[str] = None
        
        # 论文分析相关字段
        self.abstract_is_relevant: bool = False
        self.abstract_relevance_score: float = 0.0
        self.abstract_analysis_justification: Optional[str] = None
        self.full_paper_analyzed: bool = False
        self.full_paper_is_relevant: Optional[bool] = None
        self.full_paper_relevance_score: Optional[float] = None
        self.full_paper_analysis_justification: Optional[str] = None
        self.paper_summarized: bool = False
        self.paper_summary: Optional[dict] = None
        self.final_is_relevant: bool = False
        self.final_relevance_score: float = 0.0
        self.search_query: Optional[str] = None
        
        # 提取ArXiv ID和发布时间
        self.arxiv_id = self._extract_arxiv_id()
        self.published_date = self._extract_published_date()

    def set_pdf_path(self, pdf_path: str, extract_metadata: bool = True):
        """
        设置PDF文件路径，用于从现有PDF文件创建ArxivData对象
        可选择是否自动提取论文标题、作者和摘要
        
        :param pdf_path: PDF文件的路径
        :type pdf_path: str
        :param extract_metadata: 是否自动提取元数据（标题、作者、摘要），默认True
        :type extract_metadata: bool
        :return: 返回self以支持链式调用
        :rtype: ArxivData
        """
        self.pdf_path = pdf_path
        
        # 尝试从文件名提取arxiv_id（如果当前没有的话）
        if not self.arxiv_id or self.arxiv_id == "":
            import os
            filename = os.path.basename(pdf_path)
            # 尝试匹配ArXiv ID格式：YYMM.NNNN
            arxiv_match = re.search(r'(\d{4}\.\d{4,5})', filename)
            if arxiv_match:
                self.arxiv_id = arxiv_match.group(1)
                # 更新发布日期
                self.published_date = self._extract_published_date()
                logger.info(f"从文件名提取ArXiv ID: {self.arxiv_id}")
        
        # 加载PDF到内存用于OCR
        try:
            with open(pdf_path, 'rb') as f:
                self.pdf = f.read()
            logger.info(f"成功加载PDF文件: {pdf_path}")
            
            # 根据参数决定是否执行OCR和元数据提取
            if extract_metadata:
                self._extract_metadata_from_pdf()
            else:
                logger.info("跳过自动元数据提取（extract_metadata=False）")
            
        except Exception as e:
            logger.error(f"加载PDF文件失败: {pdf_path}, 错误: {e}")
        
        return self
    
    def _extract_metadata_from_pdf(self):
        """
        从PDF中提取元数据（标题、作者、摘要）
        使用OCR + LLM的方式，支持远程OCR服务
        """
        if not self.pdf:
            logger.warning("PDF内容为空，跳过元数据提取")
            return
        
        try:
            logger.info("开始从PDF提取元数据...")
            
            # 检查是否配置了远程OCR服务
            remote_endpoint = os.getenv('REMOTE_OCR_ENDPOINT')
            use_remote_ocr = bool(remote_endpoint)
            
            # 根据OCR类型决定处理页数
            if use_remote_ocr:
                # 从环境变量获取配置的最大页数
                ocr_max_pages = int(os.getenv('REMOTE_OCR_MAX_PAGES', '25'))
                logger.info(f"🌐 元数据提取使用远程OCR服务: {remote_endpoint} (最大页数: {ocr_max_pages})")
            else:
                # 本地OCR限制页数以节省资源
                ocr_max_pages = 3
                logger.info("🔍 元数据提取使用本地PaddleOCR (限制3页)")
            
            # 执行OCR，使用配置的页数和OCR方法
            ocr_result, ocr_status = self.performOCR(
                max_pages=ocr_max_pages, 
                use_paddleocr=True, 
                use_remote_ocr=use_remote_ocr
            )
            
            if not ocr_result:
                logger.warning("OCR提取失败，跳过元数据提取")
                return
            
            logger.info(f"OCR提取成功，文本长度: {len(ocr_result)}")
            
            # 使用LLM提取元数据
            try:
                from .paper_metadata_extractor import PaperMetadataLLM
                
                extractor = PaperMetadataLLM()
                if not extractor.is_available():
                    logger.warning("LLM不可用，跳过元数据提取")
                    return
                
                metadata = extractor.extract_metadata(ocr_result)
                
                # 设置提取的元数据到对象属性
                if metadata.title:
                    self.title = metadata.title
                    logger.info(f"提取到标题: {metadata.title[:100]}...")
                
                if metadata.authors:
                    self.authors = metadata.authors
                    logger.info(f"提取到作者: {metadata.authors}")
                
                if metadata.abstract:
                    self.snippet = metadata.abstract
                    logger.info(f"提取到摘要: {metadata.abstract[:200]}...")
                
                logger.info("元数据提取完成")
                
            except ImportError as e:
                logger.error(f"导入PaperMetadataLLM失败: {e}")
            except Exception as e:
                logger.error(f"LLM元数据提取失败: {e}")
            
        except Exception as e:
            logger.error(f"元数据提取过程中出错: {e}")
        
        # 清理临时OCR结果，只保留PDF
        self.paddle_ocr_result = None
        self.paddle_ocr_images = {}

    def load_from_pdf(self):
        """
        从设置的PDF路径加载PDF内容到内存
        
        :return: 是否加载成功
        :rtype: bool
        """
        if not self.pdf_path:
            logger.error("未设置PDF路径，无法加载")
            return False
        
        try:
            with open(self.pdf_path, 'rb') as f:
                self.pdf = f.read()
            logger.info(f"成功从 {self.pdf_path} 加载PDF内容")
            return True
        except Exception as e:
            logger.error(f"从 {self.pdf_path} 加载PDF失败: {e}")
            return False

    def fetch_metadata_from_link(self, link: str = None) -> bool:
        """
        从ArXiv链接获取论文元数据并填充对象属性
        
        :param link: ArXiv论文链接，如果为None则使用self.link
        :type link: str
        :return: 是否成功获取元数据
        :rtype: bool
        """
        # 使用提供的链接或自身的链接
        arxiv_link = link or self.link
        if not arxiv_link:
            logger.error("没有提供ArXiv链接")
            return False
        
        # 从链接中提取ArXiv ID
        arxiv_id = self._extract_arxiv_id_from_link(arxiv_link)
        if not arxiv_id:
            logger.error(f"无法从链接中提取ArXiv ID: {arxiv_link}")
            return False
        
        logger.info(f"从ArXiv链接获取元数据: {arxiv_link} (ID: {arxiv_id})")
        
        try:
            # 使用ArXiv API获取论文信息
            base_url = "http://export.arxiv.org/api/query"
            params = {
                "search_query": f"id:{arxiv_id}",
                "start": 0,
                "max_results": 1
            }
            
            response = requests.get(base_url, params=params, timeout=30)
            response.raise_for_status()
            
            # 解析RSS/Atom格式响应
            import feedparser
            feed = feedparser.parse(response.content)
            
            if not feed.entries:
                logger.error(f"ArXiv API未找到论文: {arxiv_id}")
                return False
            
            entry = feed.entries[0]
            
            # 提取分类
            categories = []
            if hasattr(entry, 'tags'):
                categories = [tag.term for tag in entry.tags]
            elif hasattr(entry, 'arxiv_primary_category'):
                categories = [entry.arxiv_primary_category.get('term', '')]
            
            # 提取作者信息
            authors = []
            if hasattr(entry, 'authors'):
                authors = [author.name for author in entry.authors]
            elif hasattr(entry, 'author'):
                authors = [entry.author]
            
            # 填充对象属性
            self.title = entry.title.strip() if hasattr(entry, 'title') else None
            self.link = entry.link if hasattr(entry, 'link') else arxiv_link
            self.snippet = entry.summary.strip() if hasattr(entry, 'summary') else None
            self.categories = ', '.join(categories) if categories else 'Unknown'
            
            # 设置PDF链接
            if self.link:
                self.pdf_link = self.link.replace("abs", "pdf")
            
            # 更新ArXiv ID和发布日期
            self.arxiv_id = arxiv_id
            self.published_date = self._extract_published_date()
            
            # 如果有作者信息，保存到authors属性（如果没有这个属性则添加）
            if authors:
                self.authors = ', '.join(authors)
            
            logger.info(f"成功获取论文元数据: {self.title}")
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"ArXiv API请求失败: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"解析ArXiv API响应失败: {str(e)}")
            return False

    def _extract_arxiv_id_from_link(self, link: str) -> str:
        """
        从ArXiv链接中提取论文ID
        支持的格式:
        - https://arxiv.org/abs/2503.21460
        - http://arxiv.org/abs/2503.21460v1
        - arxiv.org/abs/2503.21460
        
        :param link: ArXiv链接
        :type link: str
        :return: ArXiv ID，如果解析失败返回空字符串
        :rtype: str
        """
        if not link:
            return ""
        
        # 匹配ArXiv链接中的ID
        # 支持格式: YYMM.NNNN 或 subject-class/YYMMnnn
        patterns = [
            r'arxiv\.org/abs/([0-9]{4}\.[0-9]{4,5})',  # 新格式: 2503.21460
            r'arxiv\.org/abs/([a-z-]+/[0-9]{7})',      # 旧格式: math-ph/0309045
            r'arxiv\.org/abs/([0-9]{4}\.[0-9]{4,5}v[0-9]+)',  # 带版本号: 2503.21460v1
        ]
        
        for pattern in patterns:
            match = re.search(pattern, link)
            if match:
                arxiv_id = match.group(1)
                # 去掉版本号（如果有的话）
                if 'v' in arxiv_id and not '/' in arxiv_id:
                    arxiv_id = re.sub(r'v[0-9]+$', '', arxiv_id)
                return arxiv_id
        
        return ""

    @classmethod
    def from_arxiv_link(cls, link: str) -> 'ArxivData':
        """
        从ArXiv链接创建ArxivData对象并获取元数据
        
        :param link: ArXiv论文链接
        :type link: str
        :return: 填充了元数据的ArxivData对象
        :rtype: ArxivData
        :raises ValueError: 当链接无效或获取元数据失败时抛出
        """
        # 创建空对象
        paper = cls()
        
        # 获取元数据
        success = paper.fetch_metadata_from_link(link)
        if not success:
            raise ValueError(f"无法从ArXiv链接获取元数据: {link}")
        
        return paper

    def setTag(self, tag: list[str]):
        """
        设置论文的tag
        """

        if not isinstance(tag, list):
            logger.error(
                f"The tag of the paper is not a list, but a {type(tag)}.")
            return
        self.tag = tag

    def _extract_arxiv_id(self) -> str:
        """
        从链接中提取ArXiv ID
        """
        if not self.link:
            return ""
        
        # ArXiv链接格式: http://arxiv.org/abs/1909.03550v1
        match = re.search(r'arxiv\.org/abs/([0-9]{4}\.[0-9]{4,5})', self.link)
        if match:
            return match.group(1)
        return ""

    def _extract_published_date(self) -> str:
        """
        从ArXiv ID中提取发布日期
        ArXiv ID格式说明:
        - 2007年3月前: 格式如 math.GT/0309136 (subject-class/YYMMnnn)
        - 2007年4月后: 格式如 0704.0001 或 1909.03550 (YYMM.NNNN)
        """
        if not self.arxiv_id:
            return "未知日期"
        
        try:
            # 新格式 (2007年4月后): YYMM.NNNN
            if '.' in self.arxiv_id and len(self.arxiv_id.split('.')[0]) == 4:
                year_month = self.arxiv_id.split('.')[0]
                year = int(year_month[:2])
                month = int(year_month[2:4])
                
                # 处理年份 (07-99 表示 2007-2099, 00-06 表示 2000-2006)
                if year >= 7:
                    full_year = 2000 + year
                else:
                    full_year = 2000 + year
                
                # 调整年份逻辑：92-99是1992-1999, 00-06是2000-2006, 07-91是2007-2091
                if year >= 92:
                    full_year = 1900 + year
                elif year <= 6:
                    full_year = 2000 + year
                else:
                    full_year = 2000 + year
                
                return f"{full_year}年{month:02d}月"
            else:
                return "日期格式不支持"
        except (ValueError, IndexError):
            return "日期解析失败"

    def get_formatted_info(self) -> str:
        """
        获取格式化的论文信息，包含时间
        """
        return f"标题: {self.title}\n发布时间: {self.published_date}\n链接: {self.link}\n摘要: {self.snippet}"

    def downloadPdf(self, save_path: Optional[str] = None, use_standard_path: bool = False, check_existing: bool = False):
        """
        下载PDF并保存到指定路径

        Args:
            save_path: PDF保存路径（优先级最高）
            use_standard_path: 是否使用标准目录结构（当save_path为None时生效）
            check_existing: 是否检查文件已存在（避免重复下载）
        Returns:
            bytes: PDF内容
        Raises:
            RequestException: 当下载失败时抛出
            IOError: 当文件保存失败时抛出
        """
        if not self.pdf_link:
            raise ValueError("PDF链接不能为空")

        # 决定实际的保存路径
        actual_save_path = None
        pdf_path = None
        
        if save_path is not None:
            # 优先使用用户指定的路径（保持原有行为）
            actual_save_path = save_path
            # 去除标题中的非法字符
            pdf_title = (self.title or '无标题').replace("/", "_")
            pdf_title = pdf_title.replace(":", "_")
            pdf_title = pdf_title.replace("*", "_")
            pdf_title = pdf_title.replace("?", "_")
            pdf_title = pdf_title.replace("\\", "_")
            pdf_title = pdf_title.replace("<", "_")
            pdf_title = pdf_title.replace(">", "_")
            pdf_title = pdf_title.replace("|", "_")
            pdf_path = os.path.join(actual_save_path, pdf_title + ".pdf")
        elif use_standard_path:
            # 使用标准目录结构
            try:
                pdf_path = self.get_default_pdf_path()
                actual_save_path = pdf_path.parent
                # 确保目录存在
                actual_save_path.mkdir(parents=True, exist_ok=True)
                pdf_path = str(pdf_path)  # 转换为字符串路径
            except ValueError as e:
                logger.error(f"无法使用标准路径: {e}")
                actual_save_path = None
        
        # 检查文件是否已存在
        if check_existing and pdf_path and os.path.exists(pdf_path):
            logger.info(f"PDF文件已存在，跳过下载: {pdf_path}")
            # 读取现有文件并返回内容
            try:
                with open(pdf_path, 'rb') as f:
                    self.pdf = f.read()
                    self.pdf_path = pdf_path
                    return self.pdf
            except Exception as e:
                logger.warning(f"读取现有PDF文件失败: {e}，将重新下载")

        try:
            # 发送HEAD请求获取文件大小
            head = requests.head(self.pdf_link)
            total_size = int(head.headers.get('content-length', 0))

            # 使用流式请求下载
            response = requests.get(self.pdf_link, stream=True)
            response.raise_for_status()  # 检查响应状态

            # 初始化进度条
            progress = 0
            chunk_size = 1024  # 1KB

            content = bytearray()

            # 如果没有保存路径，则只下载到内存
            if actual_save_path is None:
                with tqdm(total=total_size, desc="Downloading PDF", unit='B', unit_scale=True) as pbar:
                    for chunk in response.iter_content(chunk_size=chunk_size):
                        if chunk:
                            content.extend(chunk)
                            progress += len(chunk)
                            pbar.update(len(chunk))
            else:
                # 同时下载到内存和保存到文件
                self.pdf_path = pdf_path

                if pdf_path:
                    with open(pdf_path, 'wb') as f, \
                            tqdm(total=total_size, desc="Downloading PDF", unit='B', unit_scale=True) as pbar:
                        for chunk in response.iter_content(chunk_size=chunk_size):
                            if chunk:
                                content.extend(chunk)
                                f.write(chunk)
                                progress += len(chunk)
                                pbar.update(len(chunk))

                    logger.info(f"PDF已保存到: {pdf_path}")

            self.pdf = bytes(content)

            return self.pdf

        except requests.exceptions.RequestException as e:
            raise Exception(f"PDF下载失败: {str(e)}")
        except IOError as e:
            raise Exception(f"PDF保存失败: {str(e)}")

    def clearPdf(self):
        """
        清空PDF内容, 释放内存
        """
        self.pdf = None
    
    def performOCR(self, max_pages: int = 25, use_paddleocr: bool = False, use_remote_ocr: bool = False, auto_save: bool = False, save_path: Optional[str] = None) -> tuple[Optional[str], dict]:
        """
        对PDF进行OCR文字识别，支持本地PyMuPDF/PaddleOCR或远程PaddleOCR服务
        
        Args:
            max_pages: 最大处理页数，默认25页（涵盖大部分正常论文）
            use_paddleocr: 是否使用本地PaddleOCR进行结构化识别，默认False使用PyMuPDF
            use_remote_ocr: 是否使用远程PaddleOCR服务，默认False
            auto_save: 是否自动保存OCR结果到标准目录（当save_path为None时生效）
            save_path: 指定OCR结果保存目录（优先级高于auto_save）
            
        Returns:
            tuple: (OCR识别结果文本, 状态信息字典)
                - str: OCR识别结果文本，如果失败返回None
                - dict: 包含状态信息的字典，包含以下键：
                    - 'total_pages': 总页数
                    - 'processed_pages': 实际处理页数
                    - 'is_oversized': 是否超过页数限制（可能是毕业论文等长文档）
                    - 'char_count': 实际提取的字符数
                    - 'method': 使用的OCR方法 ('pymupdf', 'paddleocr', 或 'remote_paddleocr')
                    - 'saved_files': 保存的文件路径列表（当启用保存时）
            
        Raises:
            ValueError: 当PDF内容为空时抛出
            Exception: 当OCR处理失败时抛出
        """
        if self.pdf is None:
            raise ValueError("PDF内容为空，请先调用downloadPdf方法下载PDF")
        
        # 决定保存目录
        ocr_save_path = None
        if save_path is not None:
            # 用户指定了保存路径
            ocr_save_path = save_path
        elif auto_save:
            # 自动保存到标准目录
            try:
                paper_dir = self.get_paper_directory()
                paper_dir.mkdir(parents=True, exist_ok=True)
                ocr_save_path = str(paper_dir)
            except ValueError as e:
                logger.warning(f"无法使用标准保存路径: {e}")
        
        # 选择OCR方法：远程PaddleOCR > 本地PaddleOCR > 本地PyMuPDF
        if use_remote_ocr:
            # 使用远程PaddleOCR服务
            ocr_result, status_info = self._performOCR_remote(max_pages, ocr_save_path)
        elif use_paddleocr:
            # 使用本地PaddleOCR
            ocr_result, status_info = self._performOCR_paddleocr(max_pages, ocr_save_path)
        else:
            # 使用本地PyMuPDF（默认）
            try:
                ocr_result, status_info = self._performOCR_pymupdf(max_pages)
                # 如果需要保存PyMuPDF结果
                if ocr_save_path and ocr_result:
                    saved_files = self._save_pymupdf_result(ocr_result, ocr_save_path)
                    status_info['saved_files'] = saved_files
            except Exception as e:
                logger.warning(f"PyMuPDF OCR失败: {str(e)}，回退到PaddleOCR")
                ocr_result, status_info = self._performOCR_paddleocr(max_pages, ocr_save_path)
        
        return ocr_result, status_info
    
    def _save_pymupdf_result(self, ocr_result: str, save_path: str) -> list:
        """
        保存PyMuPDF OCR结果到文件
        
        Args:
            ocr_result: OCR识别结果文本
            save_path: 保存目录路径
            
        Returns:
            list: 保存的文件路径列表
        """
        saved_files = []
        try:
            if not self.arxiv_id or self.arxiv_id == "":
                logger.warning("ArXiv ID为空，无法生成标准文件名")
                return saved_files
            
            save_dir = Path(save_path)
            save_dir.mkdir(parents=True, exist_ok=True)
            
            # 生成文件名
            text_file = save_dir / f"{self.arxiv_id}_ocr.txt"
            
            # 保存文本文件
            with open(text_file, 'w', encoding='utf-8') as f:
                f.write(ocr_result)
            
            saved_files.append(str(text_file))
            logger.info(f"PyMuPDF OCR结果已保存到: {text_file}")
            
        except Exception as e:
            logger.error(f"保存PyMuPDF OCR结果失败: {e}")
        
        return saved_files
    
    def _performOCR_pymupdf(self, max_pages: int = 25) -> tuple[Optional[str], dict]:
        """
        使用PyMuPDF进行快速文本提取（默认方法）
        """
        import tempfile
        
        logger.info(f"开始使用PyMuPDF进行文本提取，最大处理{max_pages}页")
        
        try:
            # 创建临时目录
            with tempfile.TemporaryDirectory() as temp_dir:
                # 保存PDF到临时文件
                tmp_pdf_path = os.path.join(temp_dir, 'input.pdf')
                with open(tmp_pdf_path, 'wb') as f:
                    f.write(self.pdf)
                
                # 打开PDF文档
                pdf_document = fitz.open(tmp_pdf_path)
                total_pages = len(pdf_document)
                
                logger.info(f"PDF总页数: {total_pages}")
                
                # 检查是否为超长文档
                is_oversized = total_pages > max_pages
                if is_oversized:
                    logger.warning(f"文档页数({total_pages})超过限制({max_pages})，将只处理前{max_pages}页")
                
                # 决定处理的页数
                pages_to_process = min(max_pages, total_pages)
                
                # 提取文本
                all_content = []
                total_chars = 0
                
                for page_num in range(pages_to_process):
                    try:
                        page = pdf_document[page_num]
                        # 兼容不同版本的PyMuPDF
                        if hasattr(page, 'get_text'):
                            text = page.get_text()
                        elif hasattr(page, 'getText'):
                            text = page.getText()
                        else:
                            text = ""
                        
                        if text.strip():
                            # 清理文本
                            clean_text = text.strip()
                            clean_text = re.sub(r'\n\s*\n', '\n\n', clean_text)  # 规范化空行
                            clean_text = re.sub(r'[ \t]+', ' ', clean_text)  # 合并多余空格
                            
                            if clean_text:
                                all_content.append(f"=== 第{page_num + 1}页 ===\n{clean_text}")
                                total_chars += len(clean_text)
                                
                    except Exception as e:
                        logger.warning(f"处理第{page_num + 1}页失败: {e}")
                        continue
                
                pdf_document.close()
                
                # 构建状态信息
                status_info = {
                    'total_pages': total_pages,
                    'processed_pages': pages_to_process,
                    'is_oversized': is_oversized,
                    'char_count': total_chars,
                    'method': 'pymupdf'
                }
                
                if all_content:
                    self.ocr_result = "\n\n".join(all_content)
                    
                    status_msg = f"PyMuPDF文本提取完成，处理了 {pages_to_process}/{total_pages} 页，提取文本 {total_chars} 个字符"
                    if is_oversized:
                        status_msg += f" (文档超长，可能是毕业论文或书籍)"
                    
                    logger.info(status_msg)
                    return self.ocr_result, status_info
                else:
                    logger.warning("PyMuPDF未提取到任何文本")
                    self.ocr_result = ""
                    return self.ocr_result, status_info
                    
        except Exception as e:
            error_msg = f"PyMuPDF处理失败: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)
    
    def _performOCR_remote(self, max_pages: int = 25, output_path: Optional[str] = None) -> tuple[Optional[str], dict]:
        """
        使用远程PaddleOCR服务进行结构化文档解析
        
        Args:
            max_pages: 最大处理页数，默认25页
            output_path: 输出目录路径，用于保存结果
            
        Returns:
            tuple: (Markdown文本, 状态信息字典)
        """
        import tempfile
        import json
        
        logger.info(f"开始使用远程PaddleOCR服务进行结构化文档解析，最大处理{max_pages}页")
        
        # 获取远程OCR服务配置
        remote_endpoint = os.getenv('REMOTE_OCR_ENDPOINT')
        if not remote_endpoint:
            error_msg = "远程OCR服务未配置，请设置REMOTE_OCR_ENDPOINT环境变量"
            logger.error(error_msg)
            return None, {
                'error': error_msg,
                'total_pages': 0,
                'processed_pages': 0,
                'is_oversized': False,
                'char_count': 0,
                'method': 'remote_paddleocr',
                'saved_files': []
            }
        
        remote_timeout = int(os.getenv('REMOTE_OCR_TIMEOUT', '300'))
        api_key = os.getenv('REMOTE_OCR_API_KEY')
        
        try:
            # 准备请求数据
            files = {'file': ('paper.pdf', self.pdf, 'application/pdf')}
            data = {
                'max_pages': max_pages,
                'arxiv_id': self.arxiv_id or 'unknown'
            }
            
            # 准备请求头
            headers = {}
            if api_key:
                headers['X-API-Key'] = api_key
            
            # 发送请求到远程服务（支持重试机制）
            import time
            
            max_retries = 3
            base_retry_delay = 10  # 基础延迟10秒
            response = None
            
            for attempt in range(max_retries):
                try:
                    logger.info(f"发送请求到远程OCR服务: {remote_endpoint} (尝试 {attempt + 1}/{max_retries})")
                    response = requests.post(
                        f"{remote_endpoint.rstrip('/')}/api/ocr/process",
                        files=files,
                        data=data,
                        headers=headers,
                        timeout=remote_timeout
                    )
                    
                    # 如果请求成功，跳出重试循环
                    if response.status_code == 200:
                        break
                    else:
                        logger.warning(f"远程OCR服务返回状态码: {response.status_code}")
                        if attempt < max_retries - 1:
                            # 指数退避：10秒、20秒、40秒
                            retry_delay = base_retry_delay * (2 ** attempt)
                            logger.info(f"等待{retry_delay}秒后重试...")
                            time.sleep(retry_delay)
                            # 重新准备files（因为文件流可能已被消耗）
                            files = {'file': ('paper.pdf', self.pdf, 'application/pdf')}
                            
                except requests.exceptions.ConnectionError as e:
                    error_type = "连接被拒绝" if "Connection refused" in str(e) else "连接中断"
                    
                    if attempt < max_retries - 1:
                        # 不是最后一次，等待后继续
                        retry_delay = base_retry_delay * (2 ** attempt)
                        logger.warning(f"{error_type}，{retry_delay}秒后重试... (尝试 {attempt + 1}/{max_retries})")
                        time.sleep(retry_delay)
                        # 重新准备files（因为文件流可能已被消耗）
                        files = {'file': ('paper.pdf', self.pdf, 'application/pdf')}
                    else:
                        # 是最后一次了，记录详细错误后抛出
                        logger.error(f"{error_type}，已尝试{max_retries}次，放弃: {str(e)}")
                        raise
                except Exception as e:
                    if attempt < max_retries - 1:
                        # 不是最后一次，等待后继续
                        retry_delay = base_retry_delay * (2 ** attempt)
                        logger.warning(f"请求异常，{retry_delay}秒后重试... (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                        time.sleep(retry_delay)
                        # 重新准备files（因为文件流可能已被消耗）
                        files = {'file': ('paper.pdf', self.pdf, 'application/pdf')}
                    else:
                        # 是最后一次了，记录详细错误后抛出
                        logger.error(f"请求异常，已尝试{max_retries}次，放弃: {str(e)}")
                        raise
                        
            # 如果没有response对象（不应该发生，但防御性编程）
            if response is None:
                raise Exception("无法获取远程OCR服务响应")
            
            if response.status_code == 200:
                result = response.json()
                
                if result.get('success', False):
                    ocr_result = result.get('ocr_result')
                    status_info = result.get('status_info', {})
                    
                    # 更新方法标识
                    status_info['method'] = 'remote_paddleocr'
                    
                    # 如果指定了保存路径，保存结果到本地
                    if output_path and ocr_result:
                        try:
                            from pathlib import Path
                            save_dir = Path(output_path)
                            save_dir.mkdir(parents=True, exist_ok=True)
                            
                            # 保存主要结果文件（使用paddleocr命名保持一致性）
                            result_file = save_dir / f"{self.arxiv_id or 'unknown'}_paddleocr.md"
                            with open(result_file, 'w', encoding='utf-8') as f:
                                f.write(ocr_result)
                            
                            # 保存图片（如果远程服务返回了图片）
                            local_saved_files = [str(result_file)]
                            images_data = result.get('images', {})
                            
                            if images_data:
                                # 创建imgs目录
                                imgs_dir = save_dir / "imgs"
                                imgs_dir.mkdir(exist_ok=True)
                                
                                # 保存每张图片
                                for img_name, img_base64 in images_data.items():
                                    try:
                                        import base64
                                        img_data = base64.b64decode(img_base64)
                                        img_path = imgs_dir / img_name
                                        with open(img_path, 'wb') as f:
                                            f.write(img_data)
                                        local_saved_files.append(str(img_path))
                                    except Exception as e:
                                        logger.warning(f"保存图片失败 {img_name}: {e}")
                                
                                logger.info(f"远程OCR保存了 {len(images_data)} 张图片到 {imgs_dir}")
                            
                            # 更新保存文件列表和图片数量
                            status_info['saved_files'] = local_saved_files
                            status_info['images_count'] = len(images_data)
                            
                            logger.info(f"远程OCR结果已保存到本地: {result_file} (包含 {len(images_data)} 张图片)")
                            
                        except Exception as e:
                            logger.warning(f"保存远程OCR结果到本地失败: {str(e)}")
                    
                    logger.info(f"远程OCR处理成功，提取字符数: {status_info.get('char_count', 0)}")
                    return ocr_result, status_info
                    
                else:
                    error_msg = result.get('error', '远程OCR服务处理失败')
                    logger.error(f"远程OCR处理失败: {error_msg}")
                    return None, {
                        'error': error_msg,
                        'total_pages': 0,
                        'processed_pages': 0,
                        'is_oversized': False,
                        'char_count': 0,
                        'method': 'remote_paddleocr',
                        'saved_files': []
                    }
                    
            else:
                error_msg = f"远程OCR服务请求失败: HTTP {response.status_code}"
                logger.error(error_msg)
                return None, {
                    'error': error_msg,
                    'total_pages': 0,
                    'processed_pages': 0,
                    'is_oversized': False,
                    'char_count': 0,
                    'method': 'remote_paddleocr',
                    'saved_files': []
                }
                
        except requests.exceptions.Timeout:
            error_msg = f"远程OCR服务请求超时 (>{remote_timeout}秒)"
            logger.error(error_msg)
            return None, {
                'error': error_msg,
                'total_pages': 0,
                'processed_pages': 0,
                'is_oversized': False,
                'char_count': 0,
                'method': 'remote_paddleocr',
                'saved_files': []
            }
            
        except requests.exceptions.ConnectionError:
            error_msg = f"无法连接到远程OCR服务: {remote_endpoint}"
            logger.error(error_msg)
            return None, {
                'error': error_msg,
                'total_pages': 0,
                'processed_pages': 0,
                'is_oversized': False,
                'char_count': 0,
                'method': 'remote_paddleocr',
                'saved_files': []
            }
            
        except Exception as e:
            error_msg = f"远程OCR处理异常: {str(e)}"
            logger.error(error_msg)
            return None, {
                'error': error_msg,
                'total_pages': 0,
                'processed_pages': 0,
                'is_oversized': False,
                'char_count': 0,
                'method': 'remote_paddleocr',
                'saved_files': []
            }

    def _performOCR_paddleocr(self, max_pages: int = 25, output_path: Optional[str] = None) -> tuple[Optional[str], dict]:
        """
        使用PaddleOCR 3.0 PPStructureV3进行结构化文档解析
        
        Args:
            max_pages: 最大处理页数，默认25页
            output_path: 输出目录路径，默认为临时目录
            
        Returns:
            tuple: (Markdown文本, 状态信息字典)
        """
        import tempfile
        import shutil
        
        logger.info(f"开始使用PaddleOCR 3.0进行结构化文档解析，最大处理{max_pages}页")
        
        try:
            # 创建临时目录
            with tempfile.TemporaryDirectory() as temp_dir:
                # 保存PDF到临时文件
                tmp_pdf_path = os.path.join(temp_dir, 'input.pdf')
                with open(tmp_pdf_path, 'wb') as f:
                    f.write(self.pdf)
                
                # 使用PyMuPDF检查总页数
                pdf_document = fitz.open(tmp_pdf_path)
                total_pages = len(pdf_document)
                pdf_document.close()
                
                logger.info(f"PDF总页数: {total_pages}")
                
                # 检查是否为超长文档
                is_oversized = total_pages > max_pages
                if is_oversized:
                    logger.warning(f"文档页数({total_pages})超过限制({max_pages})，将只处理前{max_pages}页")
                
                # 决定处理的页数
                pages_to_process = min(max_pages, total_pages)
                
                # 检查OCR功能是否可用
                if not OCR_AVAILABLE:
                    logger.error("OCR功能不可用，缺少必要的依赖包")
                    raise Exception("OCR功能不可用，请安装 paddleocr 和相关依赖")
                
                # 初始化PaddleOCR PPStructureV3
                try:
                    pipeline = PPStructureV3()
                    logger.info("PaddleOCR PPStructureV3初始化成功")
                except Exception as e:
                    logger.error(f"PaddleOCR初始化失败: {e}")
                    raise Exception(f"PaddleOCR初始化失败: {e}")
                
                # 执行结构化识别
                logger.info("开始执行结构化文档识别...")
                output = pipeline.predict(input=tmp_pdf_path)
                
                # 设置输出目录
                if output_path is None:
                    output_md_dir = os.path.join(temp_dir, 'output')
                else:
                    output_md_dir = Path(output_path)
                
                output_md_dir = Path(output_md_dir)
                output_md_dir.mkdir(parents=True, exist_ok=True)
                
                # 处理结果并提取markdown和图片
                markdown_list = []
                markdown_images = []
                
                for res in output:
                    if hasattr(res, 'markdown'):
                        md_info = res.markdown
                        markdown_list.append(md_info)
                        markdown_images.append(md_info.get("markdown_images", {}))
                
                # 合并markdown页面
                if hasattr(pipeline, 'concatenate_markdown_pages'):
                    markdown_texts = pipeline.concatenate_markdown_pages(markdown_list)
                else:
                    # 备用方法：手动合并
                    markdown_texts = "\n\n".join([str(md) for md in markdown_list if md])
                
                # 保存markdown文件
                if output_path is None:
                    # 临时模式，将结果存储在属性中
                    self.paddle_ocr_result = markdown_texts
                    self.paddle_ocr_images = {}
                    for item in markdown_images:
                        if item:
                            self.paddle_ocr_images.update(item)
                else:
                    # 保存到指定目录，使用标准化文件名
                    saved_files = []
                    
                    # 使用 arxiv_id 作为文件名（如果可用）
                    base_filename = self.arxiv_id if (self.arxiv_id and self.arxiv_id != "") else Path(tmp_pdf_path).stem
                    mkd_file_path = output_md_dir / f"{base_filename}_paddleocr.md"
                    
                    with open(mkd_file_path, "w", encoding="utf-8") as f:
                        f.write(markdown_texts)
                    saved_files.append(str(mkd_file_path))
                    
                    # 保存图片到标准化的图片目录
                    images_dir = output_md_dir 
                    for item in markdown_images:
                        if item:
                            for path, image in item.items():
                                file_path = images_dir / path
                                file_path.parent.mkdir(parents=True, exist_ok=True)
                                image.save(file_path)
                                saved_files.append(str(file_path))
                    
                    logger.info(f"Markdown文件和图片已保存到: {output_md_dir}")
                
                # 构建状态信息
                total_chars = len(markdown_texts) if markdown_texts else 0
                status_info = {
                    'total_pages': total_pages,
                    'processed_pages': pages_to_process,
                    'is_oversized': is_oversized,
                    'char_count': total_chars,
                    'method': 'paddleocr',
                    'images_count': len(self.paddle_ocr_images) if hasattr(self, 'paddle_ocr_images') else 0
                }
                
                # 添加保存文件列表（如果保存了文件）
                if output_path is not None and 'saved_files' in locals():
                    status_info['saved_files'] = saved_files
                
                if markdown_texts:
                    self.ocr_result = markdown_texts
                    
                    status_msg = f"PaddleOCR结构化识别完成，处理了 {pages_to_process}/{total_pages} 页，提取Markdown文本 {total_chars} 个字符"
                    if status_info['images_count'] > 0:
                        status_msg += f"，提取图片 {status_info['images_count']} 张"
                    if is_oversized:
                        status_msg += f" (文档超长，可能是毕业论文或书籍)"
                    
                    logger.info(status_msg)
                    return self.ocr_result, status_info
                else:
                    logger.warning("PaddleOCR未提取到任何内容")
                    self.ocr_result = ""
                    return self.ocr_result, status_info
                
        except Exception as e:
            error_msg = f"PaddleOCR处理失败: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)
    
    def getOcrResult(self) -> Optional[str]:
        """
        获取OCR识别结果
        
        Returns:
            str: OCR识别结果，如果未进行OCR识别则返回None
        """
        return self.ocr_result
    
    def clearOcrResult(self):
        """
        清空OCR识别结果，释放内存
        """
        self.ocr_result = None
    
    def getPaddleOcrResult(self) -> Optional[str]:
        """
        获取PaddleOCR结构化识别的Markdown结果
        
        Returns:
            str: PaddleOCR识别的Markdown文本，如果未进行识别则返回None
        """
        return getattr(self, 'paddle_ocr_result', None)
    
    def getPaddleOcrImages(self) -> dict:
        """
        获取PaddleOCR提取的图片字典
        
        Returns:
            dict: 图片路径到PIL Image对象的映射，如果未进行识别则返回空字典
        """
        return getattr(self, 'paddle_ocr_images', {})
    
    def clearPaddleOcrResult(self):
        """
        清空PaddleOCR识别结果，释放内存
        """
        self.paddle_ocr_result = None
        if hasattr(self, 'paddle_ocr_images') and self.paddle_ocr_images:
            self.paddle_ocr_images.clear()
    
    def savePaddleOcrToFile(self, output_path: Optional[str] = None, use_standard_path: bool = False) -> bool:
        """
        将PaddleOCR结果保存到文件
        
        Args:
            output_path: 输出目录路径（优先级高于use_standard_path）
            use_standard_path: 是否使用标准目录结构（当output_path为None时生效）
            
        Returns:
            bool: 保存是否成功
        """
        try:
            if not self.paddle_ocr_result:
                logger.warning("没有PaddleOCR结果可以保存")
                return False
            
            # 确定输出目录
            if output_path is not None:
                # 用户指定了保存路径
                output_dir = Path(output_path)
            elif use_standard_path:
                # 使用标准目录结构
                try:
                    output_dir = self.get_paper_directory()
                except ValueError as e:
                    logger.error(f"无法使用标准路径: {e}")
                    return False
            else:
                # 没有指定路径且不使用标准路径
                logger.error("必须指定output_path或设置use_standard_path=True")
                return False
            
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # 保存markdown文件，使用标准化文件名
            filename = f"{self.arxiv_id}_paddleocr.md" if (self.arxiv_id and self.arxiv_id != "") else "unknown_paddleocr.md"
            markdown_file = output_dir / filename
            with open(markdown_file, 'w', encoding='utf-8') as f:
                f.write(self.paddle_ocr_result)
            
            # 保存图片到标准化的图片目录
            if hasattr(self, 'paddle_ocr_images') and self.paddle_ocr_images:
                images_dir = output_dir 
                for path, image in self.paddle_ocr_images.items():
                    image_path = images_dir / path
                    image_path.parent.mkdir(parents=True, exist_ok=True)
                    image.save(image_path)
            
            logger.info(f"PaddleOCR结果已保存到: {output_dir}")
            return True
            
        except Exception as e:
            logger.error(f"保存PaddleOCR结果失败: {e}")
            return False

    def get_paper_directory(self) -> Path:
        """
        获取论文的标准目录路径
        
        Returns:
            Path: 论文目录路径 - data/paper_analyze/{arxiv_id}/
        """
        if not self.arxiv_id or self.arxiv_id == "":
            raise ValueError("无法创建目录：ArXiv ID 为空")
        
        # 使用相对路径，基于项目根目录
        project_root = Path(__file__).parent.parent.parent.parent  # 回到项目根目录
        base_dir = project_root / "data" / "paper_analyze"
        paper_dir = base_dir / self.arxiv_id
        
        return paper_dir
    
    def get_default_pdf_path(self) -> Path:
        """
        获取 PDF 文件的默认保存路径
        
        Returns:
            Path: PDF 文件路径 - {paper_directory}/{arxiv_id}.pdf
        """
        if not self.arxiv_id or self.arxiv_id == "":
            raise ValueError("无法生成 PDF 路径：ArXiv ID 为空")
        
        paper_dir = self.get_paper_directory()
        return paper_dir / f"{self.arxiv_id}.pdf"
    
    def get_default_ocr_paths(self) -> dict:
        """
        获取 OCR 结果文件的默认保存路径
        
        Returns:
            dict: 包含各种 OCR 文件路径的字典
                - 'pymupdf_text': PyMuPDF 文本结果路径
                - 'paddleocr_markdown': PaddleOCR Markdown 结果路径
                - 'paddleocr_images_dir': PaddleOCR 图片目录路径
        """
        if not self.arxiv_id or self.arxiv_id == "":
            raise ValueError("无法生成 OCR 路径：ArXiv ID 为空")
        
        paper_dir = self.get_paper_directory()
        
        return {
            'pymupdf_text': paper_dir / f"{self.arxiv_id}_ocr.txt",
            'paddleocr_markdown': paper_dir / f"{self.arxiv_id}_paddleocr.md",
            'paddleocr_images_dir': paper_dir / "images"
        }
    
    def save_ocr_to_standard_path(self) -> dict:
        """
        将所有OCR结果保存到标准目录的便捷方法
        
        Returns:
            dict: 保存操作的结果信息
                - 'success': bool - 是否成功
                - 'saved_files': list - 保存的文件路径列表
                - 'errors': list - 错误信息列表
        """
        result = {
            'success': False,
            'saved_files': [],
            'errors': []
        }
        
        try:
            if not self.arxiv_id or self.arxiv_id == "":
                result['errors'].append("ArXiv ID为空，无法保存到标准路径")
                return result
            
            # 确保标准目录存在
            paper_dir = self.get_paper_directory()
            paper_dir.mkdir(parents=True, exist_ok=True)
            
            # 保存PyMuPDF OCR结果
            if self.ocr_result:
                try:
                    saved_files = self._save_pymupdf_result(self.ocr_result, str(paper_dir))
                    result['saved_files'].extend(saved_files)
                except Exception as e:
                    result['errors'].append(f"保存PyMuPDF结果失败: {e}")
            
            # 保存PaddleOCR结果
            if hasattr(self, 'paddle_ocr_result') and self.paddle_ocr_result:
                try:
                    success = self.savePaddleOcrToFile(use_standard_path=True)
                    if success:
                        # 添加预期的文件路径到结果中
                        paddle_paths = self.get_default_ocr_paths()
                        result['saved_files'].append(str(paddle_paths['paddleocr_markdown']))
                        
                        # 如果有图片，添加图片目录
                        if hasattr(self, 'paddle_ocr_images') and self.paddle_ocr_images:
                            result['saved_files'].append(str(paddle_paths['paddleocr_images_dir']))
                    else:
                        result['errors'].append("PaddleOCR结果保存失败")
                except Exception as e:
                    result['errors'].append(f"保存PaddleOCR结果失败: {e}")
            
            # 判断整体成功状态
            result['success'] = len(result['saved_files']) > 0 and len(result['errors']) == 0
            
            if result['success']:
                logger.info(f"OCR结果已保存到标准路径: {paper_dir}")
            elif result['saved_files']:
                logger.warning(f"部分OCR结果保存成功，但有错误: {result['errors']}")
            else:
                logger.error(f"OCR结果保存失败: {result['errors']}")
                
        except Exception as e:
            result['errors'].append(f"保存操作失败: {e}")
            logger.error(f"保存OCR结果到标准路径失败: {e}")
        
        return result

    def cleanup(self):
        """
        清理ArxivData对象的所有内部数据，释放内存
        包括PDF数据、OCR结果、结构化分析字段等所有大内存占用的属性
        """
        # 清理PDF相关数据
        self.pdf = None
        self.pdf_path = None
        
        # 清理OCR结果
        self.ocr_result = None
        
        # 清理PaddleOCR结果
        self.paddle_ocr_result = None
        if hasattr(self, 'paddle_ocr_images') and self.paddle_ocr_images:
            self.paddle_ocr_images.clear()
        
        # 清理结构化摘要字段
        self.research_background = None
        self.research_objectives = None
        self.methods = None
        self.key_findings = None
        self.conclusions = None
        self.limitations = None
        self.future_work = None
        self.keywords = None
        
        # 清理分析结果
        self.abstract_analysis_justification = None
        self.full_paper_analysis_justification = None
        self.paper_summary = None
        
        # 清理标签和其他列表数据
        if hasattr(self, 'tag') and self.tag:
            self.tag.clear()
        
        # 强制垃圾回收
        import gc
        gc.collect()
        
        logger.debug(f"ArxivData对象已清理: {self.title[:50] if self.title else 'unknown'}...")

    def clear_invalid_characters(self, string: str) -> str:
        """
        去除字符串中的非法字符
        """
        invalid_characters = ['/', ':', '*', '?',
                              '\\', '<', '>', '|', ' ', '"', "'"]
        for char in invalid_characters:
            string = string.replace(char, '_')
        return string


class ArxivResult:

    def __init__(self, results: list[dict]):
        """
        搜索结果的保存类。

        :param results: 搜索结果
        :type results: list[dict]
        """
        self.results = [ArxivData(result) for result in results]

        self.num_results = len(self.results)

    def __iter__(self):
        """
        实现迭代器协议
        """
        return iter(self.results)
    
    def display_results(self, display_range: str = "all", max_display: int = 10, 
                       show_details: bool = True, show_summary: bool = True):
        """
        结构化显示搜索结果
        
        :param display_range: 显示范围 "all" 或 "limited"
        :type display_range: str
        :param max_display: 当display_range为"limited"时的最大显示数量
        :type max_display: int  
        :param show_details: 是否显示详细信息
        :type show_details: bool
        :param show_summary: 是否显示摘要统计
        :type show_summary: bool
        """
        if self.num_results == 0:
            print("📋 未找到相关论文")
            return
            
        # 确定显示数量
        if display_range == "all":
            display_count = self.num_results
            range_text = "全部"
        else:
            display_count = min(max_display, self.num_results)
            range_text = f"前 {display_count}"
            
        # 显示标题
        print("=" * 80)
        print(f"📚 ArXiv 搜索结果 - {range_text} {display_count} 篇论文")
        print("=" * 80)
        
        # 显示详细结果
        if show_details:
            for i, paper in enumerate(self.results[:display_count], 1):
                self._display_single_paper(i, paper)
                if i < display_count:  # 不是最后一个则显示分隔线
                    print("-" * 80)
        
        # 显示摘要统计
        if show_summary:
            self._display_summary(display_count)
    
    def _display_single_paper(self, index: int, paper: ArxivData):
        """显示单个论文的详细信息"""
        print(f"\n📄 论文 {index}")
        print(f"📌 标题: {paper.title}")
        print(f"🔗 ArXiv ID: {paper.arxiv_id or '未知'}")
        print(f"📅 发布时间: {paper.published_date}")
        print(f"🏷️  分类: {paper.categories}")
        print(f"🌐 链接: {paper.link}")
        if paper.snippet:
            print(f"📝 摘要: {paper.snippet[:200]}..." if len(paper.snippet) > 200 else f"📝 摘要: {paper.snippet}")
        else:
            print("📝 摘要: 无")
        print(f"📥 PDF: {paper.pdf_link}")
        
        # 显示标签（如果有）
        if paper.tag:
            print(f"🏷️  标签: {', '.join(paper.tag)}")
    
    def _display_summary(self, displayed_count: int):
        """显示摘要统计信息"""
        print("\n" + "=" * 80)
        print("📊 搜索摘要")
        print("=" * 80)
        print(f"📋 总结果数: {self.num_results}")
        print(f"🖥️  已显示: {displayed_count}")
        
        if displayed_count < self.num_results:
            print(f"⚠️  剩余未显示: {self.num_results - displayed_count}")
        
        # 发布时间统计
        if self.num_results > 0:
            date_counts = {}
            for paper in self.results:
                date = paper.published_date
                if date and date != "未知日期":
                    date_counts[date] = date_counts.get(date, 0) + 1
            
            if date_counts:
                print(f"\n📈 发布时间分布 (前5):")
                sorted_dates = sorted(date_counts.items(), key=lambda x: x[1], reverse=True)[:5]
                for date, count in sorted_dates:
                    print(f"   {date}: {count} 篇")
        
        # 分类统计  
        if self.num_results > 0:
            category_counts = {}
            for paper in self.results:
                categories = paper.categories.split(', ') if paper.categories else ['Unknown']
                for cat in categories:
                    category_counts[cat] = category_counts.get(cat, 0) + 1
            
            if category_counts:
                print(f"\n🏷️  分类分布 (前5):")
                sorted_cats = sorted(category_counts.items(), key=lambda x: x[1], reverse=True)[:5]
                for cat, count in sorted_cats:
                    print(f"   {cat}: {count} 篇")
        
        print("=" * 80)
    
    def display_brief(self, max_display: int = 5):
        """简洁显示模式，只显示标题和基本信息"""
        if self.num_results == 0:
            print("📋 未找到相关论文")
            return
            
        display_count = min(max_display, self.num_results)
        
        print("=" * 60)
        print(f"📚 ArXiv 搜索结果概览 - 前 {display_count} 篇")
        print("=" * 60)
        
        for i, paper in enumerate(self.results[:display_count], 1):
            print(f"{i:2d}. {paper.published_date} | {(paper.title or '无标题')[:60]}...")
            print(f"    🔗 {paper.arxiv_id or '未知ID'} | 🏷️ {paper.categories or '无分类'}")
            print()
        
        if display_count < self.num_results:
            print(f"... 还有 {self.num_results - display_count} 篇论文未显示")
        print("=" * 60)
    
    def display_titles_only(self, max_display: int = None):
        """仅显示标题列表"""
        if self.num_results == 0:
            print("📋 未找到相关论文")
            return
            
        display_count = max_display if max_display else self.num_results
        display_count = min(display_count, self.num_results)
        
        print(f"📜 论文标题列表 ({display_count}/{self.num_results}):")
        print("-" * 50)
        
        for i, paper in enumerate(self.results[:display_count], 1):
            print(f"{i:3d}. {paper.title or '无标题'}")
        
        if display_count < self.num_results:
            print(f"\n... 还有 {self.num_results - display_count} 篇论文")
    
    def get_papers_by_date_range(self, start_year: int = None, end_year: int = None):
        """根据发布年份筛选论文"""
        filtered_papers = []
        
        for paper in self.results:
            if paper.published_date and paper.published_date != "未知日期":
                # 提取年份
                try:
                    year_match = re.search(r'(\d{4})年', paper.published_date)
                    if year_match:
                        year = int(year_match.group(1))
                        
                        # 检查年份范围
                        if start_year and year < start_year:
                            continue
                        if end_year and year > end_year:
                            continue
                        
                        filtered_papers.append(paper)
                except:
                    continue
        
        # 创建新的结果对象
        filtered_results = []
        for paper in filtered_papers:
            result_dict = {
                'title': paper.title,
                'link': paper.link, 
                'snippet': paper.snippet,
                'categories': paper.categories
            }
            filtered_results.append(result_dict)
        
        return ArxivResult(filtered_results)


class ArxivTool:
    def __init__(self, search_host: str = None):
        """
        直接使用 ArXiv API 进行搜索，不再依赖 SearxNG。

        :param search_host: 保留参数以兼容现有代码，但不再使用
        :type search_host: str
        """
        # 保留参数但不再使用，避免破坏现有调用代码
        self.search_host = search_host
        
        # 大规模搜索的默认配置
        self.default_chunk_size = 2000  # 每批次大小
        self.default_delay_seconds = 1.0  # 请求间延时（秒）
        self.default_max_retries = 3  # 重试次数

    def _paginated_search(self, query: str, total_results: int,
                         sort_by: str = "relevance", order: str = "descending",
                         chunk_size: int = None, delay_seconds: float = None,
                         max_retries: int = None, show_progress: bool = False) -> ArxivResult:
        """
        内部分页搜索方法，透明处理大量结果获取
        
        :param query: 搜索查询
        :param total_results: 总目标结果数量
        :param sort_by: 排序方式
        :param order: 排序顺序
        :param chunk_size: 每批次大小，默认使用self.default_chunk_size
        :param delay_seconds: 请求间延时，默认使用self.default_delay_seconds
        :param max_retries: 重试次数，默认使用self.default_max_retries
        :param show_progress: 是否显示进度条
        :return: 合并的搜索结果
        """
        # 使用默认配置
        if chunk_size is None:
            chunk_size = self.default_chunk_size
        if delay_seconds is None:
            delay_seconds = self.default_delay_seconds
        if max_retries is None:
            max_retries = self.default_max_retries
        
        # 确保chunk_size不超过ArXiv API限制
        chunk_size = min(chunk_size, 2000)
        
        logger.info(f"开始分页搜索，目标: {total_results} 篇，分块大小: {chunk_size}")
        
        all_results = []
        total_fetched = 0
        
        # 初始化进度条
        progress_bar = None
        if show_progress:
            try:
                progress_bar = tqdm(total=total_results, desc="ArXiv搜索进度", unit="篇")
            except:
                # 如果tqdm不可用，忽略进度条
                pass
        
        try:
            # 分批获取结果
            while total_fetched < total_results:
                # 计算当前批次大小
                current_chunk = min(chunk_size, total_results - total_fetched)
                
                # 尝试获取当前批次
                retry_count = 0
                batch_results = None
                
                while retry_count <= max_retries:
                    try:
                        # 构建API请求
                        base_url = "http://export.arxiv.org/api/query"
                        sort_map = {
                            "relevance": "relevance",
                            "lastUpdatedDate": "lastUpdatedDate", 
                            "submittedDate": "submittedDate"
                        }
                        
                        params = {
                            "search_query": query,
                            "start": total_fetched,
                            "max_results": current_chunk,
                            "sortBy": sort_map.get(sort_by, "relevance"),
                            "sortOrder": order
                        }
                        
                        logger.debug(f"请求批次: start={total_fetched}, max_results={current_chunk}")
                        
                        # 发起请求
                        response = requests.get(base_url, params=params, timeout=30)
                        response.raise_for_status()
                        
                        # 解析响应
                        feed = feedparser.parse(response.content)
                        
                        if not feed.entries:
                            logger.warning(f"批次 {total_fetched}-{total_fetched+current_chunk} 无结果，可能已到达结果集末尾")
                            break
                        
                        # 转换结果格式
                        batch_results = []
                        for entry in feed.entries:
                            # 提取分类
                            categories = []
                            if hasattr(entry, 'tags'):
                                categories = [tag.term for tag in entry.tags]
                            elif hasattr(entry, 'arxiv_primary_category'):
                                categories = [entry.arxiv_primary_category['term']]
                            
                            # 提取作者信息
                            authors = []
                            if hasattr(entry, 'authors'):
                                authors = [author.name for author in entry.authors]
                            elif hasattr(entry, 'author'):
                                authors = [entry.author]
                            
                            result = {
                                'title': entry.title,
                                'link': entry.link,
                                'snippet': entry.summary,
                                'categories': ', '.join(categories) if categories else 'Unknown',
                                'authors': ', '.join(authors) if authors else 'Unknown'
                            }
                            batch_results.append(result)
                        
                        # 成功获取批次，跳出重试循环
                        break
                        
                    except requests.exceptions.RequestException as e:
                        retry_count += 1
                        if retry_count <= max_retries:
                            logger.warning(f"请求失败，重试 {retry_count}/{max_retries}: {str(e)}")
                            time.sleep(delay_seconds * retry_count)  # 递增延时
                        else:
                            logger.error(f"批次请求失败，已达最大重试次数: {str(e)}")
                            raise Exception(f"分页搜索失败: {str(e)}")
                    except Exception as e:
                        retry_count += 1
                        if retry_count <= max_retries:
                            logger.warning(f"解析失败，重试 {retry_count}/{max_retries}: {str(e)}")
                            time.sleep(delay_seconds * retry_count)
                        else:
                            logger.error(f"批次解析失败，已达最大重试次数: {str(e)}")
                            raise Exception(f"分页搜索解析失败: {str(e)}")
                
                # 如果没有获取到结果，可能已到达结果集末尾
                if not batch_results:
                    logger.info(f"已获取所有可用结果，总计: {total_fetched} 篇")
                    break
                
                # 添加到总结果集
                all_results.extend(batch_results)
                total_fetched += len(batch_results)
                
                # 更新进度条
                if progress_bar:
                    progress_bar.update(len(batch_results))
                
                logger.debug(f"已获取 {total_fetched}/{total_results} 篇文章")
                
                # 如果获取的结果少于请求数量，可能已到达结果集末尾
                if len(batch_results) < current_chunk:
                    logger.info(f"结果集已耗尽，总计获取: {total_fetched} 篇")
                    break
                
                # 请求间延时（除了最后一次请求）
                if total_fetched < total_results and delay_seconds > 0:
                    time.sleep(delay_seconds)
            
            logger.info(f"分页搜索完成，总计获取: {len(all_results)} 篇文章")
            return ArxivResult(all_results)
            
        finally:
            # 关闭进度条
            if progress_bar:
                progress_bar.close()

    def arxivSearch(self, query: str,
                    num_results: int = 20,
                    sort_by: str = "relevance",
                    order: str = "desc",
                    max_results: int = None,
                    kwargs: dict = None,
                    use_direct_api: bool = True,
                    chunk_size: int = None,
                    delay_seconds: float = None,
                    max_retries: int = None,
                    show_progress: bool = False
                    ) -> ArxivResult:
        """
        使用 ArXiv API 直接搜索，现在支持大规模搜索（1000+/10000+篇文章）

        :param query: 搜索的查询
        :type query: str
        :param num_results: 返回的结果数量（无上限，自动分页处理）
        :type num_results: int
        :param sort_by: 排序方式，可选 "relevance", "lastUpdatedDate", "submittedDate"
        :type sort_by: str
        :param order: 排序顺序，可选 "asc" (升序) 或 "desc" (降序)
        :type order: str
        :param max_results: 保留参数以兼容现有代码，但不再使用
        :type max_results: int
        :param kwargs: 保留参数以兼容现有代码，但不再使用
        :type kwargs: dict
        :param use_direct_api: 保留参数以兼容现有代码，总是使用直接API
        :type use_direct_api: bool
        :param chunk_size: 分页块大小，仅在大规模搜索时使用
        :type chunk_size: int
        :param delay_seconds: 请求间延时，仅在大规模搜索时使用
        :type delay_seconds: float
        :param max_retries: 重试次数，仅在大规模搜索时使用
        :type max_retries: int
        :param show_progress: 是否显示进度条，大规模搜索时推荐启用
        :type show_progress: bool
        :return: 搜索结果
        :rtype: ArxivResult
        """
        
        # 现在总是使用直接ArXiv API，支持大规模搜索
        logger.info(f"使用直接ArXiv API搜索: {query} ({num_results}篇)")
        
        return self.directArxivSearch(
            query=query,
            num_results=num_results,
            sort_by=sort_by,
            order="descending" if order == "desc" else "ascending",
            chunk_size=chunk_size,
            delay_seconds=delay_seconds,
            max_retries=max_retries,
            show_progress=show_progress
        )

    # 移除分页搜索方法，直接API支持大量结果

    def getLatestPapers(self, query: str, num_results: int = 20) -> ArxivResult:
        """
        获取最新的论文，按提交日期降序排列
        
        :param query: 搜索的查询
        :type query: str
        :param num_results: 返回的结果数量
        :type num_results: int
        :return: 搜索结果
        :rtype: ArxivResult
        """
        return self.arxivSearch(query=query, 
                               num_results=num_results,
                               sort_by="submittedDate", 
                               order="desc")

    def getRecentlyUpdated(self, query: str, num_results: int = 20) -> ArxivResult:
        """
        获取最近更新的论文，按更新日期降序排列
        
        :param query: 搜索的查询
        :type query: str
        :param num_results: 返回的结果数量
        :type num_results: int
        :return: 搜索结果
        :rtype: ArxivResult
        """
        return self.arxivSearch(query=query, 
                               num_results=num_results,
                               sort_by="lastUpdatedDate", 
                               order="desc")

    def searchWithHighLimit(self, query: str, num_results: int = 50, 
                           sort_by: str = "relevance", order: str = "desc",
                           max_single_request: int = 20,
                           chunk_size: int = None,
                           delay_seconds: float = None,
                           max_retries: int = None,
                           show_progress: bool = True) -> ArxivResult:
        """
        高限制搜索方法，专门优化大规模搜索（1000+/10000+篇文章）
        
        :param query: 搜索查询
        :param num_results: 目标结果数量（无上限，自动分页处理）
        :param sort_by: 排序方式
        :param order: 排序顺序
        :param max_single_request: 保留参数以兼容现有代码，但不再使用
        :param chunk_size: 分页块大小，默认使用优化后的大块（1500）
        :param delay_seconds: 请求间延时，默认使用更短延时（0.5秒）
        :param max_retries: 重试次数，默认更多重试（5次）
        :param show_progress: 是否显示进度条，默认开启
        :return: 搜索结果
        """
        # 为大规模搜索优化的默认配置
        if chunk_size is None:
            chunk_size = 1500  # 更大的分页块，减少请求次数
        if delay_seconds is None:
            delay_seconds = 0.5  # 更短的延时，提高效率
        if max_retries is None:
            max_retries = 5  # 更多重试，确保稳定性
        
        logger.info(f"高限制搜索模式，目标: {num_results} 篇文章")
        
        return self.arxivSearch(
            query=query, 
            num_results=num_results,
            sort_by=sort_by,
            order=order,
            chunk_size=chunk_size,
            delay_seconds=delay_seconds,
            max_retries=max_retries,
            show_progress=show_progress
        )

    def directArxivSearch(self, query: str, num_results: int = 20,
                         sort_by: str = "relevance", order: str = "descending",
                         chunk_size: int = None, delay_seconds: float = None,
                         max_retries: int = None, show_progress: bool = False) -> ArxivResult:
        """
        直接使用ArXiv API进行搜索，获取最新数据
        现在支持大规模搜索（1000+/10000+篇文章）
        
        :param query: 搜索查询
        :param num_results: 结果数量（无上限，自动分页处理）
        :param sort_by: 排序方式 ("relevance", "lastUpdatedDate", "submittedDate")
        :param order: 排序顺序 ("ascending", "descending")
        :param chunk_size: 分页块大小，默认使用类配置
        :param delay_seconds: 请求间延时，默认使用类配置
        :param max_retries: 重试次数，默认使用类配置
        :param show_progress: 是否显示进度条（大规模搜索时推荐）
        :return: 搜索结果
        """
        # 判断是否需要分页搜索
        if num_results > 2000:
            logger.info(f"检测到大规模搜索请求({num_results}篇)，启用分页模式")
            return self._paginated_search(
                query=query,
                total_results=num_results,
                sort_by=sort_by,
                order=order,
                chunk_size=chunk_size,
                delay_seconds=delay_seconds,
                max_retries=max_retries,
                show_progress=show_progress
            )
        
        # 标准单次请求（<=2000篇）
        base_url = "http://export.arxiv.org/api/query"
        
        # 映射排序参数
        sort_map = {
            "relevance": "relevance",
            "lastUpdatedDate": "lastUpdatedDate", 
            "submittedDate": "submittedDate"
        }
        
        params = {
            "search_query": query,
            "start": 0,
            "max_results": min(num_results, 2000),  # ArXiv API单次限制
            "sortBy": sort_map.get(sort_by, "relevance"),
            "sortOrder": order
        }
        
        try:
            logger.info(f"直接调用ArXiv API搜索: {query} (单次请求，{num_results}篇)")
            response = requests.get(base_url, params=params, timeout=30)
            response.raise_for_status()
            
            # 解析RSS/Atom格式响应
            feed = feedparser.parse(response.content)
            
            if not feed.entries:
                logger.warning("ArXiv API未返回结果")
                return ArxivResult([])
            
            # 转换为标准格式
            results = []
            for entry in feed.entries[:num_results]:
                # 提取分类
                categories = []
                if hasattr(entry, 'tags'):
                    categories = [tag.term for tag in entry.tags]
                elif hasattr(entry, 'arxiv_primary_category'):
                    categories = [entry.arxiv_primary_category['term']]
                
                # 提取作者信息
                authors = []
                if hasattr(entry, 'authors'):
                    authors = [author.name for author in entry.authors]
                elif hasattr(entry, 'author'):
                    authors = [entry.author]
                
                result = {
                    'title': entry.title,
                    'link': entry.link,
                    'snippet': entry.summary,
                    'categories': ', '.join(categories) if categories else 'Unknown',
                    'authors': ', '.join(authors) if authors else 'Unknown'
                }
                results.append(result)
            
            logger.info(f"ArXiv API返回 {len(results)} 个结果")
            return ArxivResult(results)
            
        except requests.exceptions.RequestException as e:
            logger.error(f"ArXiv API请求失败: {str(e)}")
            # 回退到SearxNG搜索
            logger.info("回退到SearxNG搜索")
            return self.arxivSearch(query, num_results, sort_by, "desc" if order == "descending" else "asc")
        except Exception as e:
            logger.error(f"ArXiv API解析失败: {str(e)}")
            return self.arxivSearch(query, num_results, sort_by, "desc" if order == "descending" else "asc")

    def getLatestPapersDirectly(self, query: str, num_results: int = 20) -> ArxivResult:
        """
        直接从ArXiv API获取最新论文
        """
        return self.directArxivSearch(query, num_results, "submittedDate", "descending")

    def getMostRelevantPapers(self, query: str, num_results: int = 20) -> ArxivResult:
        """
        获取最相关的论文，按相关性排序
        
        :param query: 搜索的查询
        :type query: str
        :param num_results: 返回的结果数量
        :type num_results: int
        :return: 搜索结果
        :rtype: ArxivResult
        """
        return self.directArxivSearch(query, num_results, "relevance", "descending")

    def searchPapersByDateRange(self, query: str, start_year: int, end_year: int, num_results: int = 20) -> ArxivResult:
        """
        搜索指定年份范围内的论文
        
        :param query: 搜索的查询
        :type query: str
        :param start_year: 开始年份
        :type start_year: int
        :param end_year: 结束年份
        :type end_year: int
        :param num_results: 返回的结果数量
        :type num_results: int
        :return: 搜索结果
        :rtype: ArxivResult
        """
        # 构造带年份范围的查询
        # ArXiv API支持submittedDate范围查询
        date_query = f"{query} AND submittedDate:[{start_year}0101* TO {end_year}1231*]"
        
        logger.info(f"搜索年份范围 {start_year}-{end_year} 的论文: {query}")
        return self.directArxivSearch(date_query, num_results, "submittedDate", "descending")

    def searchPapersAfterYear(self, query: str, after_year: int, num_results: int = 20) -> ArxivResult:
        """
        搜索某年之后的论文
        
        :param query: 搜索的查询
        :type query: str
        :param after_year: 起始年份（包含该年）
        :type after_year: int
        :param num_results: 返回的结果数量
        :type num_results: int
        :return: 搜索结果
        :rtype: ArxivResult
        """
        from datetime import datetime
        current_year = datetime.now().year
        
        # 构造带年份范围的查询，从指定年份到当前年份
        date_query = f"{query} AND submittedDate:[{after_year}0101* TO {current_year}1231*]"
        
        logger.info(f"搜索 {after_year} 年之后的论文: {query}")
        return self.directArxivSearch(date_query, num_results, "submittedDate", "descending")

    def searchPapersByMode(self, query: str, mode: ArxivSearchMode, num_results: int = 20, 
                          start_year: int = None, end_year: int = None, after_year: int = None) -> ArxivResult:
        """
        根据搜索模式搜索论文的统一接口
        
        :param query: 搜索的查询
        :type query: str
        :param mode: 搜索模式
        :type mode: ArxivSearchMode
        :param num_results: 返回的结果数量
        :type num_results: int
        :param start_year: 开始年份（仅用于DATE_RANGE模式）
        :type start_year: int
        :param end_year: 结束年份（仅用于DATE_RANGE模式）
        :type end_year: int
        :param after_year: 起始年份（仅用于AFTER_YEAR模式）
        :type after_year: int
        :return: 搜索结果
        :rtype: ArxivResult
        """
        if mode == ArxivSearchMode.LATEST:
            return self.getLatestPapers(query, num_results)
        elif mode == ArxivSearchMode.MOST_RELEVANT:
            return self.getMostRelevantPapers(query, num_results)
        elif mode == ArxivSearchMode.RECENTLY_UPDATED:
            return self.getRecentlyUpdated(query, num_results)
        elif mode == ArxivSearchMode.DATE_RANGE:
            if start_year is None or end_year is None:
                raise ValueError("DATE_RANGE模式需要提供start_year和end_year参数")
            return self.searchPapersByDateRange(query, start_year, end_year, num_results)
        elif mode == ArxivSearchMode.AFTER_YEAR:
            if after_year is None:
                raise ValueError("AFTER_YEAR模式需要提供after_year参数")
            return self.searchPapersAfterYear(query, after_year, num_results)
        else:
            raise ValueError(f"不支持的搜索模式: {mode}")

    # 移除SearxNG相关方法，现在完全使用直接API


if __name__ == "__main__":
    # ArXiv API 工具测试和结构化显示功能演示
    arxiv_tool = ArxivTool()
    
    print("=== ArXiv API 工具功能测试 ===")
    
    # 测试1: 基础搜索
    print("🔍 测试1: 基础搜索 - machine learning (10个结果)")
    results = arxiv_tool.arxivSearch(query="machine learning", num_results=10)
    print(f"✅ 搜索完成: {results.num_results} 个结果\n")
    
    # 演示结构化显示 - 限制显示前3个
    print("📋 结构化显示演示 - 前3个结果:")
    results.display_results(display_range="limited", max_display=3)
    
    print("\n" + "="*80 + "\n")
    
    # 测试2: 简洁显示模式
    print("🔍 测试2: 最新论文搜索 - deep learning")
    latest_papers = arxiv_tool.getLatestPapersDirectly(query="deep learning", num_results=15)
    
    print("📋 简洁显示演示:")
    latest_papers.display_brief(max_display=5)
    
    print("\n" + "="*80 + "\n")
    
    # 测试3: 仅标题模式
    print("🔍 测试3: 神经网络搜索")
    nn_results = arxiv_tool.arxivSearch(query="neural networks", num_results=20)
    
    print("📋 仅标题显示演示:")
    nn_results.display_titles_only(max_display=8)
    
    print("\n" + "="*80 + "\n")
    
    # 测试4: 完整显示模式（小数据集）
    print("🔍 测试4: 计算机视觉搜索")
    cv_results = arxiv_tool.arxivSearch(query="computer vision", num_results=5)
    
    print("📋 完整显示演示 - 显示全部:")
    cv_results.display_results(display_range="all", show_summary=True)
    
    print("\n" + "="*80 + "\n")
    
    # 演示年份筛选功能
    if latest_papers.num_results > 0:
        print("📋 年份筛选演示 - 筛选2020年后的论文:")
        recent_papers = latest_papers.get_papers_by_date_range(start_year=2020)
        if recent_papers.num_results > 0:
            recent_papers.display_brief(max_display=50)
        else:
            print("   未找到符合条件的论文")
    
    print("\n=== 🎉 ArXiv API 重构完成！现在支持丰富的结构化显示功能 ===")
    
    # OCR 功能测试
    print("\n" + "="*60)
    print("🔍 OCR功能测试 - PyMuPDF + PaddleOCR 3.0")
    print("="*60)
    
    if results.num_results > 0:
        test_paper = results.results[2]
        print(f"📄 测试论文: {test_paper.title[:60]}...")
        
        try:
            # 下载PDF
            print("📥 下载PDF中...")
            test_paper.downloadPdf()
            
            # 测试1: 默认PyMuPDF方法
            print("\n🔍 测试1: PyMuPDF快速文本提取...")
            ocr_result, status_info = test_paper.performOCR(use_paddleocr=False)
            
            if ocr_result:
                print(f"✅ PyMuPDF完成，提取文本: {len(ocr_result)} 字符")
                print(f"📄 处理了 {status_info['processed_pages']}/{status_info['total_pages']} 页")
                if status_info['is_oversized']:
                    print("⚠️ 文档超长，可能是毕业论文或书籍")
                print(f"📝 PyMuPDF结果预览: {ocr_result[:200]}..." if len(ocr_result) > 200 else f"📝 PyMuPDF结果: {ocr_result}")
            else:
                print("❌ PyMuPDF未提取到文本")
            
            # 测试2: PaddleOCR结构化识别
            print("\n🔍 测试2: PaddleOCR 3.0结构化识别...")
            paddle_result, paddle_status = test_paper.performOCR(use_paddleocr=True)
            
            if paddle_result:
                print(f"✅ PaddleOCR完成，提取Markdown: {len(paddle_result)} 字符")
                print(f"📄 处理了 {paddle_status['processed_pages']}/{paddle_status['total_pages']} 页")
                if paddle_status.get('images_count', 0) > 0:
                    print(f"🖼️ 提取图片: {paddle_status['images_count']} 张")
                if paddle_status['is_oversized']:
                    print("⚠️ 文档超长，可能是毕业论文或书籍")
                print(f"📝 PaddleOCR Markdown预览: {paddle_result[:300]}..." if len(paddle_result) > 300 else f"📝 PaddleOCR结果: {paddle_result}")
                
                # 显示PaddleOCR特有功能
                paddle_markdown = test_paper.getPaddleOcrResult()
                paddle_images = test_paper.getPaddleOcrImages()
                print(f"🎯 PaddleOCR特色功能:")
                print(f"   - 结构化Markdown: {len(paddle_markdown)} 字符" if paddle_markdown else "   - 结构化Markdown: 无")
                print(f"   - 图片提取: {len(paddle_images)} 张图片")
                
            else:
                print("❌ PaddleOCR未提取到内容")
                
        except Exception as e:
            print(f"❌ OCR测试失败: {str(e)}")
    
    print("="*60)
    
    # 使用指南
    print("\n📖 ArXiv工具使用指南:")
    print("="*40)
    print("🔍 搜索和显示:")
    print("   results.display_results()           # 完整显示所有结果")
    print("   results.display_results('limited')  # 限制显示前N个") 
    print("   results.display_brief()             # 简洁模式")
    print("   results.display_titles_only()       # 仅显示标题")
    print("   results.get_papers_by_date_range()  # 按年份筛选")
    print("\n📄 OCR功能:")
    print("   paper.performOCR()                  # 默认PyMuPDF快速提取")
    print("   paper.performOCR(use_paddleocr=True) # PaddleOCR结构化识别")
    print("   paper.getOcrResult()                # 获取OCR文本结果")
    print("   paper.getPaddleOcrResult()          # 获取PaddleOCR Markdown")
    print("   paper.getPaddleOcrImages()          # 获取提取的图片")
    print("   paper.savePaddleOcrToFile(path)     # 保存结果到文件")
    print("   paper.clearPaddleOcrResult()        # 清理PaddleOCR数据")
    print("\n💡 依赖要求:")
    print("   - PaddlePaddle >= 3.0.0 (CUDA 12.6)")
    print("   - PaddleOCR >= 3.0.0")
    print("   - PyMuPDF >= 1.20.0")
