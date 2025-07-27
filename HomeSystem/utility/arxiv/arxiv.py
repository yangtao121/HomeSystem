from langchain_community.utilities import SearxSearchWrapper
from langchain_community.tools.searx_search.tool import SearxSearchResults
from loguru import logger
import pprint
from tqdm import tqdm
import os

import requests


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

    def setTag(self, tag: list[str]):
        """
        设置论文的tag
        """

        if not isinstance(tag, list):
            logger.error(
                f"The tag of the paper is not a list, but a {type(tag)}.")
            return
        self.tag = tag

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
        :return: 搜索结果
        :rtype: ArxivResult
        """

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

        # pprint.pprint(results)

        if not self.checkResult(eval_results):
            logger.error(f"No good Search Result, please try again.")
            return ArxivResult([])

        logger.info(f"Successfully get the result from arxiv.")
        return ArxivResult(eval_results)

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

    def checkResult(self, results: list[dict]) -> bool:
        """
        检查搜索结果是否为空。
        """

        if 'Result' in results[0]:
            return False
        return True


if __name__ == "__main__":
    arxiv_tool = ArxivTool(search_host="http://192.168.5.54:8080")
    
    # 默认搜索
    results = arxiv_tool.arxivSearch(query="learning navigation", num_results=5)
    
    # 按时间排序的搜索示例
    latest_results = arxiv_tool.getLatestPapers(query="learning navigation", num_results=5)
    
    # 或者直接使用 arxivSearch 方法
    # results = arxiv_tool.arxivSearch(query="learning navigation",
    #                                  num_results=5,
    #                                  sort_by="submittedDate", 
    #                                  order="desc")
    
    print(results.results[0].title)
    # print(results.results[0].link)
    print(results.results[0].snippet)
