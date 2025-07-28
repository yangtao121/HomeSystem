
import asyncio
from typing import Dict, Any, List, Optional
from HomeSystem.workflow.task import Task
from HomeSystem.utility.arxiv.arxiv import ArxivTool, ArxivResult, ArxivData
from HomeSystem.workflow.paper_gather_task.llm_config import AbstractAnalysisLLM, AbstractAnalysisResult, FullPaperAnalysisLLM, FullAnalysisResult
from loguru import logger


class PaperGatherTaskConfig:
    """论文收集任务配置类"""
    
    def __init__(self, 
                 interval_seconds: int = 3600,
                 search_query: str = "machine learning",
                 max_papers_per_search: int = 20,
                 user_requirements: str = "寻找机器学习和人工智能领域的最新研究论文",
                 llm_model_name: str = "ollama.Qwen3_30B",
                 relevance_threshold: float = 0.7,
                 max_papers_in_response: int = 50,
                 max_relevant_papers_in_response: int = 10,
                 custom_settings: Optional[Dict[str, Any]] = None):
        
        self.interval_seconds = interval_seconds
        self.search_query = search_query
        self.max_papers_per_search = max_papers_per_search
        self.user_requirements = user_requirements
        self.llm_model_name = llm_model_name
        self.relevance_threshold = relevance_threshold
        self.max_papers_in_response = max_papers_in_response
        self.max_relevant_papers_in_response = max_relevant_papers_in_response
        self.custom_settings = custom_settings or {}
        
        logger.info(f"论文收集任务配置初始化完成: "
                   f"间隔={interval_seconds}秒, "
                   f"查询='{search_query}', "
                   f"最大论文数={max_papers_per_search}")
    
    def update_config(self, **kwargs):
        """更新配置参数"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
                logger.info(f"配置更新: {key} = {value}")
            else:
                logger.warning(f"未知配置参数: {key}")
    
    def get_config_dict(self) -> Dict[str, Any]:
        """获取配置字典"""
        return {
            'interval_seconds': self.interval_seconds,
            'search_query': self.search_query,
            'max_papers_per_search': self.max_papers_per_search,
            'user_requirements': self.user_requirements,
            'llm_model_name': self.llm_model_name,
            'relevance_threshold': self.relevance_threshold,
            'max_papers_in_response': self.max_papers_in_response,
            'max_relevant_papers_in_response': self.max_relevant_papers_in_response,
            'custom_settings': self.custom_settings
        }


class PaperGatherTask(Task):
    """论文收集任务 - 通过ArXiv搜索论文并使用LLM进行分析"""
    
    def __init__(self, config: Optional[PaperGatherTaskConfig] = None):
        """
        初始化论文收集任务
        
        Args:
            config: 论文收集任务配置，如果为None则使用默认配置
        """
        # 使用配置或默认配置
        self.config = config or PaperGatherTaskConfig()
        
        super().__init__("paper_gather", self.config.interval_seconds)
        
        # 初始化工具
        self.arxiv_tool = ArxivTool()
        self.llm_analyzer = AbstractAnalysisLLM(model_name=self.config.llm_model_name)
        self.full_paper_analyzer = FullPaperAnalysisLLM(model_name=self.config.llm_model_name)
        
        logger.info(f"初始化论文收集任务，配置: {self.config.get_config_dict()}")
        
    def update_config(self, **kwargs):
        """更新任务配置"""
        self.config.update_config(**kwargs)
        
        # 如果更新了模型名称，需要重新初始化LLM分析器
        if 'llm_model_name' in kwargs:
            self.llm_analyzer = AbstractAnalysisLLM(model_name=self.config.llm_model_name)
            self.full_paper_analyzer = FullPaperAnalysisLLM(model_name=self.config.llm_model_name)
            logger.info(f"重新初始化LLM分析器: {self.config.llm_model_name}")
    
    def get_config(self) -> PaperGatherTaskConfig:
        """获取当前配置"""
        return self.config
        
    async def search_papers(self, query: str, num_results: int = 10) -> ArxivResult:
        """
        搜索论文
        
        Args:
            query: 搜索查询
            num_results: 返回结果数量
            
        Returns:
            ArxivResult: 搜索结果
        """
        try:
            logger.info(f"搜索论文: {query}")
            # 获取最新论文
            results = self.arxiv_tool.getLatestPapers(query=query, num_results=num_results)
            logger.info(f"找到 {results.num_results} 篇论文")
            return results
        except Exception as e:
            logger.error(f"搜索论文失败: {e}")
            return ArxivResult([])
    
    async def analyze_paper_relevance(self, paper: ArxivData) -> AbstractAnalysisResult:
        """
        分析论文相关性
        
        Args:
            paper: 论文数据
            
        Returns:
            AbstractAnalysisResult: 分析结果
        """
        try:
            logger.debug(f"分析论文相关性: {paper.title[:50]}...")
            result = self.llm_analyzer.analyze_abstract(
                abstract=paper.snippet,
                user_requirements=self.config.user_requirements
            )

            logger.debug(f"abstract justification: {result.justification}")
            return result
        except Exception as e:
            logger.error(f"论文分析失败: {e}")
            return AbstractAnalysisResult(
                is_relevant=False,
                relevance_score=0.0,
                justification=f"分析错误: {str(e)}"
            )
    
    async def analyze_full_paper(self, paper: ArxivData) -> Optional[FullAnalysisResult]:
        """
        分析完整论文的相关性
        
        Args:
            paper: 论文数据
            
        Returns:
            FullAnalysisResult: 完整论文分析结果，如果分析失败返回None
        """
        try:
            logger.info(f"开始完整论文分析: {paper.title[:50]}...")
            
            # 下载PDF
            logger.debug("下载PDF中...")
            paper.downloadPdf()
            
            # 执行OCR
            logger.debug("执行OCR识别...")
            ocr_result, status_info = paper.performOCR(max_pages=25)
            
            if not ocr_result or len(ocr_result.strip()) < 500:
                logger.warning(f"OCR结果过短或为空，跳过完整分析: {len(ocr_result) if ocr_result else 0} 字符")
                return None
            
            logger.info(f"OCR成功，提取了 {status_info['char_count']} 字符，处理了 {status_info['processed_pages']}/{status_info['total_pages']} 页")
            if status_info['is_oversized']:
                logger.info("检测到超长文档，可能是毕业论文或书籍")
            
            # 使用FullPaperAnalysisLLM进行分析
            logger.debug("开始LLM分析完整论文...")
            full_analysis = self.full_paper_analyzer.analyze_full_paper(
                paper_content=ocr_result,
                user_requirements=self.config.user_requirements
            )

            logger.debug(f"完整论文分析，justification: {full_analysis.justification}")
            
            logger.info(f"完整论文分析完成 (评分: {full_analysis.relevance_score:.2f}): {paper.title[:50]}...")
            return full_analysis
            
        except Exception as e:
            logger.error(f"完整论文分析失败: {e}")
            return None
        finally:
            # 清理内存
            paper.clearPdf()
            paper.clearOcrResult()
    
    async def process_papers(self, papers: ArxivResult) -> List[Dict[str, Any]]:
        """
        处理论文数据，包括摘要相关性分析和完整论文分析
        
        Args:
            papers: 搜索到的论文结果
            
        Returns:
            List[Dict]: 处理后的论文数据列表
        """
        processed_papers = []
        
        for paper in papers:
            # 第一步：分析摘要相关性
            abstract_analysis = await self.analyze_paper_relevance(paper)
            
            # 构建基础论文数据
            paper_data = {
                "title": paper.title,
                "arxiv_id": paper.arxiv_id,
                "link": paper.link,
                "pdf_link": paper.pdf_link,
                "published_date": paper.published_date,
                "categories": paper.categories,
                "abstract": paper.snippet,
                "abstract_is_relevant": abstract_analysis.is_relevant,
                "abstract_relevance_score": abstract_analysis.relevance_score,
                "abstract_analysis_justification": abstract_analysis.justification,
                "tags": paper.tag,
                "full_paper_analyzed": False,
                "full_paper_is_relevant": None,
                "full_paper_relevance_score": None,
                "full_paper_analysis_justification": None,
                "final_is_relevant": abstract_analysis.is_relevant,
                "final_relevance_score": abstract_analysis.relevance_score
            }
            
            # 第二步：如果摘要相关性足够高，进行完整论文分析
            if abstract_analysis.is_relevant and abstract_analysis.relevance_score >= self.config.relevance_threshold:
                logger.info(f"摘要相关性高 ({abstract_analysis.relevance_score:.2f})，开始完整论文分析: {paper.title[:50]}...")
                
                full_analysis = await self.analyze_full_paper(paper)
                
                if full_analysis:
                    paper_data.update({
                        "full_paper_analyzed": True,
                        "full_paper_is_relevant": full_analysis.is_relevant,
                        "full_paper_relevance_score": full_analysis.relevance_score,
                        "full_paper_analysis_justification": full_analysis.justification,
                        "final_is_relevant": full_analysis.is_relevant,
                        "final_relevance_score": full_analysis.relevance_score
                    })
                    
                    if full_analysis.is_relevant:
                        logger.info(f"完整论文分析确认相关 (评分: {full_analysis.relevance_score:.2f}): {paper.title}")
                    else:
                        logger.info(f"完整论文分析判定不相关 (评分: {full_analysis.relevance_score:.2f}): {paper.title}")
                else:
                    logger.warning(f"完整论文分析失败，使用摘要分析结果: {paper.title[:50]}...")
            else:
                logger.debug(f"摘要相关性低 ({abstract_analysis.relevance_score:.2f})，跳过完整分析: {paper.title[:50]}...")
            
            processed_papers.append(paper_data)
        
        return processed_papers
        
    async def run(self) -> Dict[str, Any]:
        """执行论文收集逻辑"""
        logger.info("开始执行论文收集任务")
        
        all_papers = []
        total_relevant_papers = 0
        
        try:
            # 处理搜索查询
            logger.info(f"处理搜索查询: {self.config.search_query}")
            
            # 搜索论文
            search_results = await self.search_papers(
                self.config.search_query, 
                num_results=self.config.max_papers_per_search
            )
            
            if search_results.num_results == 0:
                logger.warning(f"查询 '{self.config.search_query}' 未找到论文")
                return {
                    "message": "未找到相关论文",
                    "total_papers": 0,
                    "relevant_papers": 0,
                    "search_query": self.config.search_query,
                    "user_requirements": self.config.user_requirements,
                    "config": self.config.get_config_dict()
                }
            
            # 处理和分析论文
            processed_papers = await self.process_papers(search_results)
            
            # 统计相关论文（根据配置的阈值过滤，使用最终判断结果）
            relevant_papers = [p for p in processed_papers 
                             if p["final_is_relevant"] and p["final_relevance_score"] >= self.config.relevance_threshold]
            total_relevant_papers = len(relevant_papers)
            
            # 添加查询标识
            for paper in processed_papers:
                paper["search_query"] = self.config.search_query
            
            all_papers = processed_papers
            
            logger.info(f"查询 '{self.config.search_query}' 完成: 找到 {len(processed_papers)} 篇论文，"
                       f"其中 {len(relevant_papers)} 篇相关（阈值: {self.config.relevance_threshold}）")
            
            # 按最终相关性评分排序
            all_papers.sort(key=lambda x: x["final_relevance_score"], reverse=True)
            
            logger.info(f"论文收集任务完成: 总共处理 {len(all_papers)} 篇论文，其中 {total_relevant_papers} 篇相关")
            
            return {
                "message": "论文收集任务执行完成",
                "total_papers": len(all_papers),
                "relevant_papers": total_relevant_papers,
                "search_query": self.config.search_query,
                "user_requirements": self.config.user_requirements,
                "config": self.config.get_config_dict(),
                "papers": all_papers[:self.config.max_papers_in_response],  # 返回配置数量的论文
                "top_relevant_papers": relevant_papers[:self.config.max_relevant_papers_in_response]  # 返回配置数量的相关论文
            }
            
        except Exception as e:
            logger.error(f"论文收集任务执行失败: {e}")
            return {
                "message": f"论文收集任务执行失败: {str(e)}",
                "total_papers": 0,
                "relevant_papers": 0,
                "error": str(e)
            }
