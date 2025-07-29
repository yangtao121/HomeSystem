# 移除 langchain_community 依赖，直接使用 ArXiv API
from loguru import logger
import pprint
from tqdm import tqdm
import os
import re
from datetime import datetime
import io
from typing import Optional

import requests
import xml.etree.ElementTree as ET
import urllib.parse
import time
import feedparser

# OCR 相关导入
from pix2text import Pix2Text
import fitz  # PyMuPDF
from PIL import Image
import numpy as np


class ArxivData:
    def __init__(self, result: dict):
        """
        用于存储单条arxiv 的搜索结果。
        输入的 result 必须包含的 key 如下：
        - title: 标题
        - link: 链接
        - snippet: 摘要
        - categories: 分类
        :param result: 单条搜索结果
        :type result: dict
        """
        self.title = None
        self.link = None
        self.snippet = None
        self.categories = None

        for key, value in result.items():
            setattr(self, key, value)

        # 获取pdf链接
        self.pdf_link = self.link.replace("abs", "pdf")

        self.pdf = None

        self.pdf_path = None

        # 论文的tag
        self.tag: list[str] = []
        
        # OCR识别结果
        self.ocr_result: Optional[str] = None
        
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
            return None
        
        # ArXiv链接格式: http://arxiv.org/abs/1909.03550v1
        match = re.search(r'arxiv\.org/abs/([0-9]{4}\.[0-9]{4,5})', self.link)
        if match:
            return match.group(1)
        return None

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

    def downloadPdf(self, save_path: str = None):
        """
        下载PDF并保存到指定路径

        Args:
            save_path: PDF保存路径
        Returns:
            bytes: PDF内容
        Raises:
            RequestException: 当下载失败时抛出
            IOError: 当文件保存失败时抛出
        """
        if not self.pdf_link:
            raise ValueError("PDF链接不能为空")

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

            # 同时下载到内存和保存到文件
            # 去除标题中的非法字符
            pdf_title = (self.title or '无标题').replace("/", "_")
            pdf_title = pdf_title.replace(":", "_")
            pdf_title = pdf_title.replace("*", "_")
            pdf_title = pdf_title.replace("?", "_")
            pdf_title = pdf_title.replace("\\", "_")
            pdf_title = pdf_title.replace("<", "_")
            pdf_title = pdf_title.replace(">", "_")
            pdf_title = pdf_title.replace("|", "_")

            # pdf_title = pdf_title.replace(" ", "_")

            # 如果没有指定保存路径，则不保存
            if save_path is None:
                with tqdm(total=total_size, desc="Downloading PDF", unit='B', unit_scale=True) as pbar:
                    for chunk in response.iter_content(chunk_size=chunk_size):
                        if chunk:
                            content.extend(chunk)
                            progress += len(chunk)
                            pbar.update(len(chunk))
            else:
                pdf_path = os.path.join(save_path, pdf_title + ".pdf")

                self.pdf_path = pdf_path

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
    
    def performOCR(self, max_pages: int = 25, use_pix2text: bool = False) -> tuple[Optional[str], dict]:
        """
        对PDF进行OCR文字识别，默认使用PyMuPDF快速提取，可选使用pix2text高精度识别
        
        Args:
            max_pages: 最大处理页数，默认25页（涵盖大部分正常论文）
            use_pix2text: 是否使用pix2text进行高精度OCR，默认False使用PyMuPDF
            
        Returns:
            tuple: (OCR识别结果文本, 状态信息字典)
                - str: OCR识别结果文本，如果失败返回None
                - dict: 包含状态信息的字典，包含以下键：
                    - 'total_pages': 总页数
                    - 'processed_pages': 实际处理页数
                    - 'is_oversized': 是否超过页数限制（可能是毕业论文等长文档）
                    - 'char_count': 实际提取的字符数
                    - 'method': 使用的OCR方法 ('pymupdf' 或 'pix2text')
            
        Raises:
            ValueError: 当PDF内容为空时抛出
            Exception: 当OCR处理失败时抛出
        """
        if self.pdf is None:
            raise ValueError("PDF内容为空，请先调用downloadPdf方法下载PDF")
        
        # 如果明确要求使用pix2text，或者PyMuPDF方法失败时回退
        if use_pix2text:
            return self._performOCR_pix2text(max_pages)
        else:
            try:
                return self._performOCR_pymupdf(max_pages)
            except Exception as e:
                logger.warning(f"PyMuPDF OCR失败: {str(e)}，回退到pix2text")
                return self._performOCR_pix2text(max_pages)
    
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
                        text = page.get_text()
                        
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
    
    def _performOCR_pix2text(self, max_pages: int = 25) -> tuple[Optional[str], dict]:
        """
        使用pix2text进行高精度OCR识别（备用方法）
        """
        try:
            import os
            import tempfile
            import shutil
            
            # 强制设置CPU模式，避免CUDA相关错误
            os.environ['CUDA_VISIBLE_DEVICES'] = ''
            os.environ['CUDA_LAUNCH_BLOCKING'] = '1'
            os.environ['OMP_NUM_THREADS'] = '1'
            
            logger.info(f"开始对PDF进行OCR识别，使用pix2text，最大处理{max_pages}页")
            
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
                
                # 检查是否为超长文档（可能是毕业论文或书籍）
                is_oversized = total_pages > max_pages
                if is_oversized:
                    logger.warning(f"文档页数({total_pages})超过限制({max_pages})，可能是毕业论文或书籍，将只处理前{max_pages}页")
                
                # 决定处理的页数
                pages_to_process = min(max_pages, total_pages)
                page_numbers = list(range(pages_to_process))
                
                logger.info(f"将处理页面: {page_numbers} (共{pages_to_process}页)")
                
                # 使用官方方法：初始化pix2text并识别PDF
                try:
                    # 禁用可能导致问题的组件，只保留文本OCR
                    config = {
                        'text_ocr': {'enabled': True},
                        'layout': {'enabled': True},  # 禁用布局检测
                        'formula': {'enabled': True},  # 禁用公式识别
                        'table': {'enabled': True},   # 禁用表格识别
                        'mfd': {'enabled': True}       # 禁用数学公式检测
                    }
                    p2t = Pix2Text.from_config(config=config)
                    logger.info("使用简化配置初始化pix2text成功")
                except Exception as e:
                    logger.warning(f"简化配置初始化失败: {e}，尝试默认配置")
                    try:
                        # 使用默认配置
                        p2t = Pix2Text()
                        logger.info("使用默认配置初始化pix2text成功")
                    except Exception as e2:
                        logger.error(f"默认配置也失败: {e2}")
                        raise Exception(f"pix2text初始化失败: {e2}")
                
                doc = p2t.recognize_pdf(tmp_pdf_path, page_numbers=page_numbers)
                
                # 导出markdown到临时目录
                # output_md_dir = os.path.join(temp_dir, 'output-md')

                # 保存到当前目录下用于debug

                output_md_dir = os.path.join(os.getcwd(), 'output-md')
                doc.to_markdown(output_md_dir)
                
                logger.info(f"markdown文件已导出到: {output_md_dir}")
                
                # 读取生成的markdown文件，不限制字符数
                all_content = []
                total_chars = 0
                
                if os.path.exists(output_md_dir):
                    # 遍历所有markdown文件
                    for root, dirs, files in os.walk(output_md_dir):
                        # 按文件名排序以保持页面顺序
                        md_files = sorted([f for f in files if f.endswith('.md')])
                        
                        for filename in md_files:
                            filepath = os.path.join(root, filename)
                            try:
                                with open(filepath, 'r', encoding='utf-8') as f:
                                    content = f.read().strip()
                                
                                if content:
                                    # 清理markdown格式，转换为纯文本
                                    import re
                                    clean_content = content
                                    clean_content = re.sub(r'!\[.*?\]\(.*?\)', '', clean_content)  # 移除图片
                                    clean_content = re.sub(r'\[([^\]]*)\]\([^\)]*\)', r'\1', clean_content)  # 保留链接文本
                                    clean_content = re.sub(r'#{1,6}\s*', '', clean_content)  # 移除标题标记
                                    clean_content = re.sub(r'\*{1,2}(.*?)\*{1,2}', r'\1', clean_content)  # 移除粗体/斜体
                                    clean_content = re.sub(r'`{1,3}(.*?)`{1,3}', r'\1', clean_content)  # 移除代码标记
                                    clean_content = re.sub(r'\n\s*\n', '\n\n', clean_content)  # 规范化空行
                                    clean_content = clean_content.strip()
                                    
                                    if clean_content:
                                        content_chars = len(clean_content)
                                        all_content.append(f"=== {filename} ===\n{clean_content}")
                                        total_chars += content_chars
                                            
                            except Exception as e:
                                logger.warning(f"读取文件 {filename} 失败: {e}")
                                continue
                
                # 合并所有内容并构建状态信息
                status_info = {
                    'total_pages': total_pages,
                    'processed_pages': pages_to_process,
                    'is_oversized': is_oversized,
                    'char_count': total_chars,
                    'method': 'pix2text'
                }
                
                if all_content:
                    self.ocr_result = "\n\n".join(all_content)
                    
                    # 记录详细信息
                    status_msg = f"pix2text OCR识别完成，处理了 {pages_to_process}/{total_pages} 页，提取文本 {total_chars} 个字符"
                    if is_oversized:
                        status_msg += f" (文档超长，可能是毕业论文或书籍)"
                    
                    logger.info(status_msg)
                    return self.ocr_result, status_info
                else:
                    logger.warning("pix2text OCR识别未提取到任何文本")
                    self.ocr_result = ""
                    return self.ocr_result, status_info
                
        except Exception as e:
            error_msg = f"pix2text OCR识别失败: {str(e)}"
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

    def arxivSearch(self, query: str,
                    num_results: int = 20,
                    sort_by: str = "relevance",
                    order: str = "desc",
                    max_results: int = None,
                    kwargs: dict = None,
                    use_direct_api: bool = True
                    ) -> ArxivResult:
        """
        使用 ArXiv API 直接搜索，无限制且获取最新数据。

        :param query: 搜索的查询
        :type query: str
        :param num_results: 返回的结果数量
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
        :return: 搜索结果
        :rtype: ArxivResult
        """
        
        # 现在总是使用直接ArXiv API
        logger.info(f"使用直接ArXiv API搜索: {query}")
        
        return self.directArxivSearch(
            query=query,
            num_results=num_results,
            sort_by=sort_by,
            order="descending" if order == "desc" else "ascending"
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
                           max_single_request: int = 20) -> ArxivResult:
        """
        高限制搜索方法，可以获取更多结果
        
        :param query: 搜索查询
        :param num_results: 目标结果数量（可以很大）
        :param sort_by: 排序方式
        :param order: 排序顺序
        :param max_single_request: 单次请求的最大结果数
        :return: 搜索结果
        """
        return self.arxivSearch(query=query, 
                               num_results=num_results,
                               sort_by=sort_by,
                               order=order,
                               max_results=max_single_request)

    def directArxivSearch(self, query: str, num_results: int = 20,
                         sort_by: str = "relevance", order: str = "descending") -> ArxivResult:
        """
        直接使用ArXiv API进行搜索，获取最新数据
        
        :param query: 搜索查询
        :param num_results: 结果数量
        :param sort_by: 排序方式 ("relevance", "lastUpdatedDate", "submittedDate")
        :param order: 排序顺序 ("ascending", "descending")
        :return: 搜索结果
        """
        # ArXiv API URL
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
            "max_results": min(num_results, 2000),  # ArXiv API限制
            "sortBy": sort_map.get(sort_by, "relevance"),
            "sortOrder": order
        }
        
        try:
            logger.info(f"直接调用ArXiv API搜索: {query}")
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
    print("\n" + "="*50)
    print("🔍 OCR功能测试")
    print("="*50)
    
    if results.num_results > 0:
        test_paper = results.results[2]
        print(f"📄 测试论文: {test_paper.title[:60]}...")
        
        try:
            # 下载PDF
            print("📥 下载PDF中...")
            test_paper.downloadPdf()
            
            # 执行OCR（不限制字符数，只限制页数）
            print("🔍 执行OCR识别...")
            ocr_result, status_info = test_paper.performOCR()
            
            if ocr_result:
                print(f"✅ OCR完成，提取文本: {len(ocr_result)} 字符")
                print(f"📄 处理了 {status_info['processed_pages']}/{status_info['total_pages']} 页")
                if status_info['is_oversized']:
                    print("⚠️ 文档超长，可能是毕业论文或书籍")
                print(f"📝 结果预览: {ocr_result}")
            else:
                print("❌ OCR未提取到文本")
                
        except Exception as e:
            print(f"❌ OCR测试失败: {str(e)}")
    
    print("="*50)
    
    # 使用指南
    print("\n📖 结构化显示功能使用指南:")
    print("   results.display_results()           # 完整显示所有结果")
    print("   results.display_results('limited')  # 限制显示前N个") 
    print("   results.display_brief()             # 简洁模式")
    print("   results.display_titles_only()       # 仅显示标题")
    print("   results.get_papers_by_date_range()  # 按年份筛选")
