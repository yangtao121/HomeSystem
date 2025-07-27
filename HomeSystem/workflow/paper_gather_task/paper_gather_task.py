
import asyncio
from typing import Dict, Any, List, Optional
from HomeSystem.workflow.task import Task
from HomeSystem.utility.arxiv.arxiv import ArxivTool, ArxivResult, ArxivData
from HomeSystem.workflow.paper_gather_task.llm_config import AbstractAnalysisLLM, AbstractAnalysisResult
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
        
        logger.info(f"初始化论文收集任务，配置: {self.config.get_config_dict()}")
        
    def update_config(self, **kwargs):
        """更新任务配置"""
        self.config.update_config(**kwargs)
        
        # 如果更新了模型名称，需要重新初始化LLM分析器
        if 'llm_model_name' in kwargs:
            self.llm_analyzer = AbstractAnalysisLLM(model_name=self.config.llm_model_name)
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
            return result
        except Exception as e:
            logger.error(f"论文分析失败: {e}")
            return AbstractAnalysisResult(
                is_relevant=False,
                relevance_score=0.0,
                justification=f"分析错误: {str(e)}"
            )
    
    async def process_papers(self, papers: ArxivResult) -> List[Dict[str, Any]]:
        """
        处理论文数据，包括相关性分析
        
        Args:
            papers: 搜索到的论文结果
            
        Returns:
            List[Dict]: 处理后的论文数据列表
        """
        processed_papers = []
        
        for paper in papers:
            # 分析论文相关性
            analysis_result = await self.analyze_paper_relevance(paper)
            
            # 构建论文数据
            paper_data = {
                "title": paper.title,
                "arxiv_id": paper.arxiv_id,
                "link": paper.link,
                "pdf_link": paper.pdf_link,
                "published_date": paper.published_date,
                "categories": paper.categories,
                "abstract": paper.snippet,
                "is_relevant": analysis_result.is_relevant,
                "relevance_score": analysis_result.relevance_score,
                "analysis_justification": analysis_result.justification,
                "tags": paper.tag
            }
            
            processed_papers.append(paper_data)
            
            # 记录相关论文
            if analysis_result.is_relevant:
                logger.info(f"发现相关论文 (评分: {analysis_result.relevance_score:.2f}): {paper.title}")
            else:
                logger.debug(f"论文不相关 (评分: {analysis_result.relevance_score:.2f}): {paper.title}")
        
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
            
            # 统计相关论文（根据配置的阈值过滤）
            relevant_papers = [p for p in processed_papers 
                             if p["is_relevant"] and p["relevance_score"] >= self.config.relevance_threshold]
            total_relevant_papers = len(relevant_papers)
            
            # 添加查询标识
            for paper in processed_papers:
                paper["search_query"] = self.config.search_query
            
            all_papers = processed_papers
            
            logger.info(f"查询 '{self.config.search_query}' 完成: 找到 {len(processed_papers)} 篇论文，"
                       f"其中 {len(relevant_papers)} 篇相关（阈值: {self.config.relevance_threshold}）")
            
            # 按相关性评分排序
            all_papers.sort(key=lambda x: x["relevance_score"], reverse=True)
            
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
