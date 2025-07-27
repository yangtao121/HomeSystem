from langchain_community.utilities import SearxSearchWrapper
from langchain_community.tools.searx_search.tool import SearxSearchResults
from loguru import logger
import pprint
from tqdm import tqdm
import os
import re
from datetime import datetime

import requests
import xml.etree.ElementTree as ET
import urllib.parse
import time


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
            pdf_title = self.title.replace("/", "_")
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


class ArxivTool:
    def __init__(self, search_host: str):
        """
        用于调用 searxng 的 api，并简化返回结果，提供给大模型使用。

        :param search_host: searxng 的 host
        :type search_host: str
        """
        self.search_host = search_host
        self.search_wrapper = SearxSearchWrapper(searx_host=search_host)

    def arxivSearch(self, query: str,
                    num_results: int = 5,
                    sort_by: str = "relevance",
                    order: str = "desc",
                    max_results: int = None,
                    kwargs: dict = {
                        "engines": ["arxiv"],
                    }
                    ) -> ArxivResult:
        """
        用于搜索 arxiv 的 api，并将结果转换为list[dict]。

        :param query: 搜索的查询
        :type query: str
        :param num_results: 返回的结果数量
        :type num_results: int
        :param sort_by: 排序方式，可选 "relevance", "lastUpdatedDate", "submittedDate"
        :type sort_by: str
        :param order: 排序顺序，可选 "asc" (升序) 或 "desc" (降序)
        :type order: str
        :param max_results: 最大结果数量限制，如果num_results超过此值则使用分页搜索
        :type max_results: int
        :return: 搜索结果
        :rtype: ArxivResult
        """
        
        # 设置默认的最大单次搜索结果数量
        single_search_limit = max_results or 30
        
        # 如果请求的结果数量超过单次搜索限制，使用分页搜索
        if num_results > single_search_limit:
            return self._paginated_search(query, num_results, sort_by, order, single_search_limit, kwargs)

        default_kwargs = {
            "engines": ["arxiv"],
        }

        # 处理排序参数
        if sort_by in ["lastUpdatedDate", "submittedDate"]:
            default_kwargs["sort"] = sort_by
            if order in ["asc", "desc"]:
                default_kwargs["order"] = order

        default_kwargs.update(kwargs)
        arxiv_tool = SearxSearchResults(name="Arxiv", wrapper=self.search_wrapper,
                                        num_results=num_results,
                                        kwargs=default_kwargs)

        results = arxiv_tool.invoke(query)

        eval_results = eval(results)

        # 调试信息：打印实际返回的结果数量
        logger.info(f"SearxNG实际返回结果数量: {len(eval_results)} (请求数量: {num_results})")
        # pprint.pprint(results)

        if not self.checkResult(eval_results):
            logger.error(f"No good Search Result, please try again.")
            return ArxivResult([])

        logger.info(f"Successfully get the result from arxiv.")
        return ArxivResult(eval_results)

    def _paginated_search(self, query: str, num_results: int, sort_by: str, order: str, 
                         single_search_limit: int, kwargs: dict) -> ArxivResult:
        """
        分页搜索以获取更多结果
        
        :param query: 搜索查询
        :param num_results: 目标结果数量
        :param sort_by: 排序方式
        :param order: 排序顺序
        :param single_search_limit: 单次搜索限制
        :param kwargs: 额外参数
        :return: 合并后的搜索结果
        """
        all_results = []
        remaining_results = num_results
        page = 1
        
        logger.info(f"开始分页搜索，目标结果数量: {num_results}")
        
        while remaining_results > 0:
            # 计算当前页面需要获取的结果数量
            current_page_size = min(remaining_results, single_search_limit)
            
            logger.info(f"搜索第 {page} 页，获取 {current_page_size} 个结果")
            
            default_kwargs = {
                "engines": ["arxiv"],
                "pageno": page  # 添加页面参数
            }
            
            # 处理排序参数
            if sort_by in ["lastUpdatedDate", "submittedDate"]:
                default_kwargs["sort"] = sort_by
                if order in ["asc", "desc"]:
                    default_kwargs["order"] = order
            
            default_kwargs.update(kwargs)
            
            arxiv_tool = SearxSearchResults(name="Arxiv", wrapper=self.search_wrapper,
                                          num_results=current_page_size,
                                          kwargs=default_kwargs)
            
            try:
                results = arxiv_tool.invoke(query)
                eval_results = eval(results)
                
                if not self.checkResult(eval_results):
                    logger.warning(f"第 {page} 页没有找到有效结果，停止搜索")
                    break
                
                # 去重：检查是否有重复的结果（基于链接）
                existing_links = {result.get('link', '') for result in all_results}
                new_results = [result for result in eval_results 
                             if result.get('link', '') not in existing_links]
                
                if not new_results:
                    logger.warning(f"第 {page} 页结果全部重复，停止搜索")
                    break
                
                all_results.extend(new_results)
                remaining_results -= len(new_results)
                page += 1
                
                logger.info(f"第 {page-1} 页获取到 {len(new_results)} 个新结果，总计 {len(all_results)} 个结果")
                
                # 如果当前页面返回的结果少于请求的数量，说明没有更多结果了
                if len(eval_results) < current_page_size:
                    logger.info("已获取所有可用结果")
                    break
                    
            except Exception as e:
                logger.error(f"第 {page} 页搜索失败: {str(e)}")
                break
        
        logger.info(f"分页搜索完成，共获取 {len(all_results)} 个结果")
        return ArxivResult(all_results)

    def getLatestPapers(self, query: str, num_results: int = 5) -> ArxivResult:
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

    def getRecentlyUpdated(self, query: str, num_results: int = 5) -> ArxivResult:
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

    def checkResult(self, results: list[dict]) -> bool:
        """
        检查搜索结果是否为空。
        """

        if 'Result' in results[0]:
            return False
        return True


if __name__ == "__main__":
    arxiv_tool = ArxivTool(search_host="http://192.168.5.54:8080")
    
    # 示例1: 默认搜索（小量结果）
    print("=== 示例1: 默认搜索 ===")
    results = arxiv_tool.arxivSearch(query="learning navigation", num_results=10)
    print(f"默认搜索结果数量: {results.num_results}")
    
    # 示例2: 高限制搜索（获取更多结果）
    print("\n=== 示例2: 高限制搜索 ===")
    high_limit_results = arxiv_tool.searchWithHighLimit(
        query="machine learning", 
        num_results=50,  # 请求50个结果
        max_single_request=15  # 每次最多请求15个
    )
    print(f"高限制搜索结果数量: {high_limit_results.num_results}")
    
    # 示例3: 超大量搜索（使用分页）
    print("\n=== 示例3: 超大量搜索 ===")
    large_results = arxiv_tool.arxivSearch(
        query="deep learning", 
        num_results=100,  # 请求100个结果
        max_results=20    # 单次最多20个，会自动分页
    )
    print(f"超大量搜索结果数量: {large_results.num_results}")
    
    # 示例4: 按时间排序的大量搜索
    print("\n=== 示例4: 按时间排序大量搜索 ===")
    latest_results = arxiv_tool.getLatestPapers(query="reinforcement learning", num_results=60)
    print(f"最新论文搜索结果数量: {latest_results.num_results}")
    
    # 显示第一个结果的详细信息
    if results.num_results > 0:
        first_result = results.results[0]
        print("\n" + "=" * 50)
        print("第一个结果详细信息:")
        print(f"标题: {first_result.title}")
        print(f"ArXiv ID: {first_result.arxiv_id}")
        print(f"发布时间: {first_result.published_date}")
        print(f"链接: {first_result.link}")
        print(f"摘要: {first_result.snippet[:200]}...")
        print("=" * 50)
    
    # 显示高限制搜索的统计信息
    if high_limit_results.num_results > 0:
        print(f"\n高限制搜索前10个结果:")
        for i, result in enumerate(high_limit_results.results):
            print(f"{i+1}. {result.title[:60]}... ({result.published_date})")
