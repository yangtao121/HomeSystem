
import asyncio
from typing import Dict, Any, List, Optional
from HomeSystem.workflow.task import Task
from HomeSystem.utility.arxiv.arxiv import ArxivTool, ArxivResult, ArxivData
from HomeSystem.workflow.paper_gather_task.llm_config import AbstractAnalysisLLM, AbstractAnalysisResult, FullPaperAnalysisLLM, FullAnalysisResult, TranslationLLM
from HomeSystem.graph.paper_analysis_agent import PaperAnalysisAgent, PaperAnalysisConfig
from HomeSystem.integrations.database import DatabaseOperations, ArxivPaperModel
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
                 enable_paper_summarization: bool = True,
                 summarization_threshold: float = 0.8,
                 enable_translation: bool = True,
                 custom_settings: Optional[Dict[str, Any]] = None):
        
        self.interval_seconds = interval_seconds
        self.search_query = search_query
        self.max_papers_per_search = max_papers_per_search
        self.user_requirements = user_requirements
        self.llm_model_name = llm_model_name
        self.relevance_threshold = relevance_threshold
        self.max_papers_in_response = max_papers_in_response
        self.max_relevant_papers_in_response = max_relevant_papers_in_response
        self.enable_paper_summarization = enable_paper_summarization
        self.summarization_threshold = summarization_threshold
        self.enable_translation = enable_translation
        self.custom_settings = custom_settings or {}
        
        logger.info(f"论文收集任务配置初始化完成: "
                   f"间隔={interval_seconds}秒, "
                   f"查询='{search_query}', "
                   f"最大论文数={max_papers_per_search}, "
                   f"启用论文总结={enable_paper_summarization}, "
                   f"启用翻译={enable_translation}")
    
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
            'enable_paper_summarization': self.enable_paper_summarization,
            'summarization_threshold': self.summarization_threshold,
            'enable_translation': self.enable_translation,
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
        self.translator = TranslationLLM()
        
        # 初始化数据库操作
        self.db_ops = DatabaseOperations()
        
        # 初始化论文分析智能体（用于论文总结）
        if self.config.enable_paper_summarization:
            paper_analysis_config = PaperAnalysisConfig(
                model_name=self.config.llm_model_name,
                memory_enabled=False,
                parallel_execution=True,
                validate_results=True
            )
            self.paper_analysis_agent = PaperAnalysisAgent(config=paper_analysis_config)
            logger.info("论文分析智能体初始化完成")
        else:
            self.paper_analysis_agent = None
        
        logger.info(f"初始化论文收集任务，配置: {self.config.get_config_dict()}")
        
    def update_config(self, **kwargs):
        """更新任务配置"""
        self.config.update_config(**kwargs)
        
        # 如果更新了模型名称，需要重新初始化LLM分析器
        if 'llm_model_name' in kwargs:
            self.llm_analyzer = AbstractAnalysisLLM(model_name=self.config.llm_model_name)
            self.full_paper_analyzer = FullPaperAnalysisLLM(model_name=self.config.llm_model_name)
            self.translator = TranslationLLM()
            
            # 重新初始化论文分析智能体
            if self.config.enable_paper_summarization:
                paper_analysis_config = PaperAnalysisConfig(
                    model_name=self.config.llm_model_name,
                    memory_enabled=False,
                    parallel_execution=True,
                    validate_results=True
                )
                self.paper_analysis_agent = PaperAnalysisAgent(config=paper_analysis_config)
                logger.info(f"重新初始化论文分析智能体: {self.config.llm_model_name}")
            
            logger.info(f"重新初始化LLM分析器: {self.config.llm_model_name}")
            
        # 如果更新了论文总结开关，需要相应地初始化或清理论文分析智能体
        if 'enable_paper_summarization' in kwargs:
            if self.config.enable_paper_summarization and not self.paper_analysis_agent:
                paper_analysis_config = PaperAnalysisConfig(
                    model_name=self.config.llm_model_name,
                    memory_enabled=False,
                    parallel_execution=True,
                    validate_results=True
                )
                self.paper_analysis_agent = PaperAnalysisAgent(config=paper_analysis_config)
                logger.info("启用论文总结，初始化论文分析智能体")
            elif not self.config.enable_paper_summarization:
                self.paper_analysis_agent = None
                logger.info("禁用论文总结，清理论文分析智能体")
    
    def get_config(self) -> PaperGatherTaskConfig:
        """获取当前配置"""
        return self.config
    
    async def translate_paper_fields(self, paper: ArxivData) -> None:
        """
        将论文的英文结构化字段翻译为中文并直接覆盖原字段
        
        Args:
            paper: 论文数据对象，会直接修改其字段
        """
        if not self.config.enable_translation:
            logger.debug("翻译功能已禁用，跳过翻译")
            return
            
        try:
            logger.debug(f"开始翻译论文字段: {paper.title[:50]}...")
            
            # 定义需要翻译的字段
            fields_to_translate = [
                'research_background', 'research_objectives', 'methods', 
                'key_findings', 'conclusions', 'limitations', 'future_work', "snippet"
            ]
            
            # 翻译每个字段
            for field_name in fields_to_translate:
                field_value = getattr(paper, field_name, None)
                if field_value and field_value.strip() and field_value != '无':
                    try:
                        translation_result = self.translator.translate_text(field_value)
                        # 直接覆盖原字段
                        setattr(paper, field_name, translation_result.translated_text)
                        logger.debug(f"字段 {field_name} 翻译完成 (质量: {translation_result.translation_quality})")
                    except Exception as e:
                        logger.error(f"翻译字段 {field_name} 失败: {e}")
            
            logger.debug(f"论文字段翻译完成: {paper.title[:50]}...")
            
        except Exception as e:
            logger.error(f"翻译论文字段时发生异常: {e}")
    
    async def check_paper_in_database(self, arxiv_id: str) -> Optional[ArxivPaperModel]:
        """
        检查论文是否已在数据库中
        
        Args:
            arxiv_id: ArXiv论文ID
            
        Returns:
            ArxivPaperModel: 如果存在返回论文模型，否则返回None
        """
        try:
            existing_paper = self.db_ops.get_by_field(ArxivPaperModel, 'arxiv_id', arxiv_id)
            if existing_paper:
                logger.debug(f"论文已存在于数据库中: {arxiv_id}")
                return existing_paper
            else:
                logger.debug(f"论文不存在于数据库中: {arxiv_id}")
                return None
        except Exception as e:
            logger.error(f"检查论文数据库状态失败: {arxiv_id}, 错误: {e}")
            return None
    
    async def save_paper_to_database(self, paper: ArxivData) -> bool:
        """
        保存论文到数据库
        
        Args:
            paper: ArXiv论文数据
            
        Returns:
            bool: 保存是否成功
        """
        try:
            # 创建ArxivPaperModel实例
            paper_model = ArxivPaperModel(
                arxiv_id=paper.arxiv_id,
                title=paper.title,
                authors=getattr(paper, 'authors', ''),  # 使用getattr安全获取authors属性
                abstract=paper.snippet,  # ArxivData中使用snippet作为abstract
                categories=paper.categories,
                published_date=getattr(paper, 'published_date', ''),  # 使用published_date而不是published
                pdf_url=getattr(paper, 'pdf_link', paper.link.replace("abs", "pdf") if paper.link else ''),  # 使用pdf_link属性
                processing_status='completed',  # 处理完成后设置为completed
                tags=[],  # 初始为空，可以后续添加
                metadata={
                    'search_query': getattr(paper, 'search_query', ''),
                    'final_relevance_score': getattr(paper, 'final_relevance_score', 0.0),
                    'abstract_relevance_score': getattr(paper, 'abstract_relevance_score', 0.0),
                    'full_paper_relevance_score': getattr(paper, 'full_paper_relevance_score', 0.0),
                    'paper_summarized': getattr(paper, 'paper_summarized', False)
                },
                # 结构化论文分析字段
                research_background=getattr(paper, 'research_background', None),
                research_objectives=getattr(paper, 'research_objectives', None),
                methods=getattr(paper, 'methods', None),
                key_findings=getattr(paper, 'key_findings', None),
                conclusions=getattr(paper, 'conclusions', None),
                limitations=getattr(paper, 'limitations', None),
                future_work=getattr(paper, 'future_work', None),
                keywords=getattr(paper, 'keywords', None)
            )
            
            # 保存到数据库
            success = self.db_ops.create(paper_model)
            if success:
                logger.info(f"论文成功保存到数据库: {paper.arxiv_id} - {paper.title[:50]}...")
                return True
            else:
                logger.error(f"论文保存到数据库失败: {paper.arxiv_id}")
                return False
        except Exception as e:
            logger.error(f"保存论文到数据库时发生异常: {paper.arxiv_id}, 错误: {e}")
            return False
        
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

            paper.ocr_result = ocr_result

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
    
    async def summarize_paper(self, paper: ArxivData) -> Optional[Dict[str, Any]]:
        """
        使用论文分析智能体对论文进行总结
        
        Args:
            paper: 论文数据
            
        Returns:
            Dict: 论文总结结果，如果总结失败返回None
        """
        if not self.paper_analysis_agent:
            logger.warning("论文分析智能体未初始化，无法进行论文总结")
            return None
            
        try:
            logger.info(f"开始论文总结: {paper.title[:50]}...")
            
            # 检查是否已有OCR结果
            ocr_result = paper.ocr_result if hasattr(paper, 'ocr_result') and paper.ocr_result else None
            
            if not ocr_result:
                # 如果没有OCR结果，需要重新下载PDF并执行OCR
                logger.debug("重新下载PDF并执行OCR...")
                paper.downloadPdf()
                ocr_result, status_info = paper.performOCR(max_pages=25)
                
                if not ocr_result or len(ocr_result.strip()) < 500:
                    logger.warning(f"OCR结果过短或为空，无法进行论文总结: {len(ocr_result) if ocr_result else 0} 字符")
                    return None
                
                logger.info(f"OCR成功，提取了 {status_info['char_count']} 字符，处理了 {status_info['processed_pages']}/{status_info['total_pages']} 页")
            
            # 使用论文分析智能体进行总结
            logger.debug("开始使用论文分析智能体进行总结...")
            summary_result = self.paper_analysis_agent.analyze_paper(
                paper_text=ocr_result,
                thread_id=f"paper_summary_{paper.arxiv_id}"
            )
            
            if summary_result and "error" not in summary_result:
                # 提取结构化结果
                structured_result = self.paper_analysis_agent.get_structured_result(summary_result)

                # print(f"Structured Result: {structured_result}")

                if structured_result:
                    # 将结构化结果赋值给ArxivData对象的对应字段
                    paper.research_background = structured_result.get("research_background")
                    paper.research_objectives = structured_result.get("research_objectives")
                    paper.methods = structured_result.get("methods")
                    paper.key_findings = structured_result.get("key_findings")
                    paper.conclusions = structured_result.get("conclusions")
                    paper.limitations = structured_result.get("limitations")
                    paper.future_work = structured_result.get("future_work")
                    paper.keywords = structured_result.get("keywords")
                    
                    logger.info(f"论文总结成功: {paper.title[:50]}...")
                    return {
                        "structured_summary": structured_result,
                        "analysis_metadata": {
                            "extraction_method": summary_result.get("extraction_method", "parallel_llm"),
                            "completed_tasks": summary_result.get("completed_tasks", 0),
                            "extraction_errors": summary_result.get("extraction_errors", []),
                            "timestamp": summary_result.get("timestamp", "")
                        }
                    }
                else:
                    logger.warning("无法提取结构化总结结果")
                    return {
                        "raw_summary": summary_result,
                        "analysis_metadata": {
                            "extraction_method": "parallel_llm",
                            "note": "结构化提取失败，返回原始结果"
                        }
                    }
            else:
                error_msg = summary_result.get("error", "未知错误") if summary_result else "无返回结果"
                logger.error(f"论文总结失败: {error_msg}")
                return None
                
        except Exception as e:
            logger.error(f"论文总结过程中发生异常: {e}")
            return None
        finally:
            # 清理内存
            if hasattr(paper, 'clearPdf'):
                paper.clearPdf()
            if hasattr(paper, 'clearOcrResult'):
                paper.clearOcrResult()
    
    async def process_papers(self, papers: ArxivResult) -> List[ArxivData]:
        """
        处理论文数据，包括摘要相关性分析和完整论文分析
        
        Args:
            papers: 搜索到的论文结果
            
        Returns:
            List[ArxivData]: 处理后的论文对象列表
        """
        processed_papers = []
        
        for paper in papers:
            logger.info(f"开始处理论文: {paper.arxiv_id} - {paper.title[:50]}...")
            
            # 第一步：检查论文是否已在数据库中
            existing_paper = await self.check_paper_in_database(paper.arxiv_id)
            
            if existing_paper:
                logger.info(f"论文已在数据库中，跳过处理: {paper.arxiv_id}")
                # 从数据库中的数据创建ArxivData对象，保持一致性
                paper.final_is_relevant = existing_paper.processing_status == 'completed'
                paper.final_relevance_score = existing_paper.metadata.get('final_relevance_score', 0.0) if existing_paper.metadata else 0.0
                processed_papers.append(paper)
                continue
            
            # 第二步：如果论文不在数据库中，进行摘要相关性分析
            logger.debug(f"论文不在数据库中，开始分析: {paper.arxiv_id}")
            abstract_analysis = await self.analyze_paper_relevance(paper)
            
            # 将分析结果直接赋值给ArxivData对象
            paper.abstract_is_relevant = abstract_analysis.is_relevant
            paper.abstract_relevance_score = abstract_analysis.relevance_score
            paper.abstract_analysis_justification = abstract_analysis.justification
            paper.final_is_relevant = abstract_analysis.is_relevant
            paper.final_relevance_score = abstract_analysis.relevance_score
            
            # 第二步：如果摘要相关性足够高，进行完整论文分析
            if abstract_analysis.is_relevant and abstract_analysis.relevance_score >= self.config.relevance_threshold:
                logger.info(f"摘要相关性高 ({abstract_analysis.relevance_score:.2f})，开始完整论文分析: {paper.title[:50]}...")
                
                full_analysis = await self.analyze_full_paper(paper)
                
                if full_analysis:
                    paper.full_paper_analyzed = True
                    paper.full_paper_is_relevant = full_analysis.is_relevant
                    paper.full_paper_relevance_score = full_analysis.relevance_score
                    paper.full_paper_analysis_justification = full_analysis.justification
                    paper.final_is_relevant = full_analysis.is_relevant
                    paper.final_relevance_score = full_analysis.relevance_score
                    
                    if full_analysis.is_relevant:
                        logger.info(f"完整论文分析确认相关 (评分: {full_analysis.relevance_score:.2f}): {paper.title}")
                        
                        # 如果启用了论文总结且相关性评分足够高，则进行论文总结
                        if (self.config.enable_paper_summarization and 
                            self.paper_analysis_agent and 
                            full_analysis.relevance_score >= self.config.summarization_threshold):
                            
                            logger.info(f"相关性评分足够高 ({full_analysis.relevance_score:.2f})，开始论文总结: {paper.title[:50]}...")
                            summary_result = await self.summarize_paper(paper)

                            if summary_result:
                                paper.paper_summarized = True
                                paper.paper_summary = summary_result
                                logger.info(f"论文总结完成: {paper.title[:50]}...")
                                
                                # 翻译结构化字段
                                await self.translate_paper_fields(paper)
                                
                                # 输出翻译后的中文内容
                                logger.debug(f"论文关键词: {paper.keywords}")
                                logger.debug(f"论文研究背景: {paper.research_background if paper.research_background else '无'}")
                                logger.debug(f"论文研究目标: {paper.research_objectives if paper.research_objectives else '无'}")
                                logger.debug(f"论文方法: {paper.methods if paper.methods else '无'}")
                                logger.debug(f"论文主要发现: {paper.key_findings if paper.key_findings else '无'}")
                                logger.debug(f"论文结论: {paper.conclusions if paper.conclusions else '无'}")
                                logger.debug(f"论文局限性: {paper.limitations if paper.limitations else '无'}")
                                logger.debug(f"论文未来工作: {paper.future_work if paper.future_work else '无'}")
                            else:
                                logger.warning(f"论文总结失败: {paper.title[:50]}...")
                        else:
                            if not self.config.enable_paper_summarization:
                                logger.debug(f"论文总结功能已禁用，跳过总结: {paper.title[:50]}...")
                            elif full_analysis.relevance_score < self.config.summarization_threshold:
                                logger.debug(f"相关性评分不足总结阈值 ({full_analysis.relevance_score:.2f} < {self.config.summarization_threshold})，跳过总结: {paper.title[:50]}...")
                    else:
                        logger.info(f"完整论文分析判定不相关 (评分: {full_analysis.relevance_score:.2f}): {paper.title}")
                else:
                    logger.warning(f"完整论文分析失败，使用摘要分析结果: {paper.title[:50]}...")
            else:
                logger.debug(f"摘要相关性低 ({abstract_analysis.relevance_score:.2f})，跳过完整分析: {paper.title[:50]}...")
            
            # 第三步：如果论文符合要求（相关性达标），保存到数据库
            if paper.final_is_relevant and paper.final_relevance_score >= self.config.relevance_threshold:
                logger.info(f"论文符合要求，保存到数据库: {paper.arxiv_id} (评分: {paper.final_relevance_score:.2f})")
                save_success = await self.save_paper_to_database(paper)
                if not save_success:
                    logger.warning(f"论文保存到数据库失败，但继续处理: {paper.arxiv_id}")
            else:
                logger.debug(f"论文不符合要求，不保存到数据库: {paper.arxiv_id} (相关性: {paper.final_is_relevant}, 评分: {paper.final_relevance_score:.2f})")
            
            processed_papers.append(paper)
        
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
                             if p.final_is_relevant and p.final_relevance_score >= self.config.relevance_threshold]
            total_relevant_papers = len(relevant_papers)
            
            # 添加查询标识
            for paper in processed_papers:
                paper.search_query = self.config.search_query
            
            all_papers = processed_papers
            
            logger.info(f"查询 '{self.config.search_query}' 完成: 找到 {len(processed_papers)} 篇论文，"
                       f"其中 {len(relevant_papers)} 篇相关（阈值: {self.config.relevance_threshold}）")
            
            # 按最终相关性评分排序
            all_papers.sort(key=lambda x: x.final_relevance_score, reverse=True)
            
            logger.info(f"论文收集任务完成: 总共处理 {len(all_papers)} 篇论文，其中 {total_relevant_papers} 篇相关")
            
            return {
                "message": "论文收集任务执行完成",
                "total_papers": len(all_papers),
                "relevant_papers": total_relevant_papers,
                "search_query": self.config.search_query,
                "user_requirements": self.config.user_requirements,
                "config": self.config.get_config_dict(),
                "papers": all_papers[:self.config.max_papers_in_response],  # 返回配置数量的ArxivData对象
                "top_relevant_papers": relevant_papers[:self.config.max_relevant_papers_in_response]  # 返回配置数量的相关ArxivData对象
            }
            
        except Exception as e:
            logger.error(f"论文收集任务执行失败: {e}")
            return {
                "message": f"论文收集任务执行失败: {str(e)}",
                "total_papers": 0,
                "relevant_papers": 0,
                "error": str(e)
            }
