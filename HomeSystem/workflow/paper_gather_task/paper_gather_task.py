
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional
from HomeSystem.workflow.task import Task
from HomeSystem.utility.arxiv.arxiv import ArxivTool, ArxivResult, ArxivData, ArxivSearchMode
from HomeSystem.workflow.paper_gather_task.llm_config import AbstractAnalysisLLM, AbstractAnalysisResult, FullPaperAnalysisLLM, FullAnalysisResult
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
                 abstract_analysis_model: Optional[str] = None,
                 full_paper_analysis_model: Optional[str] = None,
                 relevance_threshold: float = 0.7,
                 max_papers_in_response: int = 50,
                 max_relevant_papers_in_response: int = 10,
                 # 深度分析相关参数
                 enable_deep_analysis: bool = True,
                 deep_analysis_threshold: float = 0.8,
                 deep_analysis_model: str = "deepseek.DeepSeek_V3",
                 vision_model: str = "ollama.Qwen2_5_VL_7B",
                 ocr_char_limit_for_analysis: int = 10000,
                 # 用户提示词参数
                 enable_user_prompt: bool = False,
                 user_prompt: Optional[str] = None,
                 # 搜索模式相关参数
                 search_mode: ArxivSearchMode = ArxivSearchMode.LATEST,
                 start_year: Optional[int] = None,
                 end_year: Optional[int] = None,
                 after_year: Optional[int] = None,
                 # 远程OCR相关参数
                 enable_remote_ocr: bool = False,
                 remote_ocr_endpoint: str = 'http://localhost:5001',
                 remote_ocr_timeout: int = 300,
                 # 视频分析相关参数
                 enable_video_analysis: bool = False,
                 video_analysis_model: Optional[str] = None,
                 # 任务追踪相关参数
                 task_name: Optional[str] = None,
                 task_id: Optional[str] = None,
                 custom_settings: Optional[Dict[str, Any]] = None):
        
        self.interval_seconds = interval_seconds
        self.search_query = search_query
        self.max_papers_per_search = max_papers_per_search
        self.user_requirements = user_requirements
        self.llm_model_name = llm_model_name

        if not abstract_analysis_model:
            abstract_analysis_model = llm_model_name
        self.abstract_analysis_model = abstract_analysis_model
        if not full_paper_analysis_model:
            full_paper_analysis_model = llm_model_name
        self.full_paper_analysis_model = full_paper_analysis_model
        
        self.relevance_threshold = relevance_threshold
        self.max_papers_in_response = max_papers_in_response
        self.max_relevant_papers_in_response = max_relevant_papers_in_response
        
        # 深度分析相关配置
        self.enable_deep_analysis = enable_deep_analysis
        self.deep_analysis_threshold = deep_analysis_threshold
        self.deep_analysis_model = deep_analysis_model
        self.vision_model = vision_model
        self.ocr_char_limit_for_analysis = ocr_char_limit_for_analysis
        # 用户提示词配置
        self.enable_user_prompt = enable_user_prompt
        self.user_prompt = user_prompt
        # 远程OCR配置
        self.enable_remote_ocr = enable_remote_ocr
        self.remote_ocr_endpoint = remote_ocr_endpoint
        self.remote_ocr_timeout = remote_ocr_timeout
        # 视频分析配置
        self.enable_video_analysis = enable_video_analysis
        if not video_analysis_model:
            video_analysis_model = llm_model_name  # 默认使用主LLM模型
        self.video_analysis_model = video_analysis_model
        # 新增搜索模式相关属性
        self.search_mode = search_mode
        self.start_year = start_year
        self.end_year = end_year
        self.after_year = after_year
        self.custom_settings = custom_settings or {}
        
        # 任务追踪参数
        self.task_name = task_name or "paper_gather"  # 默认任务名称
        self.task_id = task_id  # 如果未提供将在实际执行时生成
        
        # 验证搜索模式参数
        self._validate_search_mode_params()
        
        logger.info(f"论文收集任务配置初始化完成: "
                   f"间隔={interval_seconds}秒, "
                   f"查询='{search_query}', "
                   f"搜索模式={search_mode.value}, "
                   f"最大论文数={max_papers_per_search}, "
                   f"启用深度分析={enable_deep_analysis}, "
                   f"深度分析阈值={deep_analysis_threshold}")
    
    def _validate_search_mode_params(self):
        """验证搜索模式参数的合法性"""
        if self.search_mode == ArxivSearchMode.DATE_RANGE:
            if self.start_year is None or self.end_year is None:
                raise ValueError("DATE_RANGE搜索模式需要提供start_year和end_year参数")
            if self.start_year > self.end_year:
                raise ValueError("start_year不能大于end_year")
            
        elif self.search_mode == ArxivSearchMode.AFTER_YEAR:
            if self.after_year is None:
                raise ValueError("AFTER_YEAR搜索模式需要提供after_year参数")
            from datetime import datetime
            current_year = datetime.now().year
            if self.after_year > current_year:
                logger.warning(f"after_year ({self.after_year}) 大于当前年份 ({current_year})")
    
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
            'abstract_analysis_model': self.abstract_analysis_model,
            'full_paper_analysis_model': self.full_paper_analysis_model,
            'relevance_threshold': self.relevance_threshold,
            'max_papers_in_response': self.max_papers_in_response,
            'max_relevant_papers_in_response': self.max_relevant_papers_in_response,
            # 深度分析相关配置
            'enable_deep_analysis': self.enable_deep_analysis,
            'deep_analysis_threshold': self.deep_analysis_threshold,
            'deep_analysis_model': self.deep_analysis_model,
            'vision_model': self.vision_model,
            'ocr_char_limit_for_analysis': self.ocr_char_limit_for_analysis,
            # 搜索模式相关配置
            'search_mode': self.search_mode.value,
            'start_year': self.start_year,
            'end_year': self.end_year,
            'after_year': self.after_year,
            # 任务追踪相关配置
            'task_name': self.task_name,
            'task_id': self.task_id,
            'custom_settings': self.custom_settings
        }


class PaperGatherTask(Task):
    """论文收集任务 - 通过ArXiv搜索论文并使用LLM进行分析"""
    
    def __init__(self, config: Optional[PaperGatherTaskConfig] = None, delay_first_run: bool = True):
        """
        初始化论文收集任务
        
        Args:
            config: 论文收集任务配置，如果为None则使用默认配置
            delay_first_run: 是否延迟首次运行，默认为True（用于定时任务）
        """
        # 使用配置或默认配置
        self.config = config or PaperGatherTaskConfig()
        
        super().__init__("paper_gather", self.config.interval_seconds, delay_first_run=delay_first_run)
        
        # 初始化工具
        self.arxiv_tool = ArxivTool()
        self.llm_analyzer = AbstractAnalysisLLM(
            model_name=self.config.abstract_analysis_model 
        )
        self.full_paper_analyzer = FullPaperAnalysisLLM(
            model_name=self.config.full_paper_analysis_model
        )
        
        # 初始化数据库操作
        self.db_ops = DatabaseOperations()
        
        logger.info(f"初始化论文收集任务，配置: {self.config.get_config_dict()}")
        
    def update_config(self, **kwargs):
        """更新任务配置"""
        self.config.update_config(**kwargs)
        
        # 如果更新了任何模型配置，需要重新初始化相应的LLM分析器
        model_related_keys = [
            'llm_model_name', 'abstract_analysis_model', 
            'full_paper_analysis_model'
        ]
        
        if any(key in kwargs for key in model_related_keys):
            # 重新初始化摘要分析器
            if 'llm_model_name' in kwargs or 'abstract_analysis_model' in kwargs:
                self.llm_analyzer = AbstractAnalysisLLM(
                    model_name=self.config.abstract_analysis_model or self.config.llm_model_name
                )
                logger.info(f"重新初始化摘要分析器: {self.llm_analyzer.model_name}")
            
            # 重新初始化完整论文分析器
            if 'llm_model_name' in kwargs or 'full_paper_analysis_model' in kwargs:
                self.full_paper_analyzer = FullPaperAnalysisLLM(
                    model_name=self.config.full_paper_analysis_model or self.config.llm_model_name
                )
                logger.info(f"重新初始化完整论文分析器: {self.full_paper_analyzer.model_name}")
    
    def get_config(self) -> PaperGatherTaskConfig:
        """获取当前配置"""
        return self.config
    
    
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
    
    def _get_required_field(self, paper: ArxivData, source_field: str, target_field: str):
        """
        获取必需字段，如果不存在或为空则抛出异常
        
        Args:
            paper: ArxivData对象
            source_field: 源字段名
            target_field: 目标字段名（用于错误消息）
            
        Returns:
            字段值
            
        Raises:
            ValueError: 如果字段不存在、为None或为空字符串
        """
        value = getattr(paper, source_field, None)
        if value is None:
            raise ValueError(f"Required field '{target_field}' is missing (source: '{source_field}') in paper {paper.arxiv_id}")
        if isinstance(value, str) and not value.strip():
            raise ValueError(f"Required field '{target_field}' is empty (source: '{source_field}') in paper {paper.arxiv_id}")
        return value
    
    async def save_paper_to_database(self, paper: ArxivData) -> bool:
        """
        保存论文到数据库
        
        Args:
            paper: ArXiv论文数据
            
        Returns:
            bool: 保存是否成功
        """
        # 检查深度分析是否成功（可选，失败也可以保存基础信息）
        deep_analysis_success = getattr(paper, 'deep_analysis_success', True)
        
        # 深度分析失败不阻止数据库保存，只记录日志
        if not deep_analysis_success:
            logger.warning(f"论文深度分析失败，但仍会保存基础信息到数据库: {paper.arxiv_id} - {paper.title[:50]}...")
            
        try:
            # 准备深度分析字段
            deep_analysis_result = getattr(paper, 'deep_analysis_result', None)
            deep_analysis_completed = getattr(paper, 'deep_analysis_completed', False)
            deep_analysis_status = None
            
            # 根据深度分析情况设置状态
            if deep_analysis_result and deep_analysis_completed:
                deep_analysis_status = 'completed'
            elif not deep_analysis_success:
                deep_analysis_status = 'failed'
            
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
                    'full_paper_relevance_score': getattr(paper, 'full_paper_relevance_score', 0.0)
                },
                # 任务追踪字段
                task_name=self.config.task_name,
                task_id=self.config.task_id,
                # 完整论文相关性评分字段（保留基础分析结果）
                full_paper_relevance_score=getattr(paper, 'full_paper_relevance_score', None),
                full_paper_relevance_justification=getattr(paper, 'full_paper_analysis_justification', 
                                                           getattr(paper, 'abstract_analysis_justification', None)),
                # 深度分析字段
                deep_analysis_result=deep_analysis_result,
                deep_analysis_status=deep_analysis_status,
                deep_analysis_created_at=datetime.now() if deep_analysis_status else None,
                deep_analysis_updated_at=datetime.now() if deep_analysis_status else None
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
        根据配置的搜索模式搜索论文
        
        Args:
            query: 搜索查询
            num_results: 返回结果数量
            
        Returns:
            ArxivResult: 搜索结果
        """
        try:
            logger.info(f"使用搜索模式 {self.config.search_mode.value} 搜索论文: {query}")
            
            # 根据配置的搜索模式选择搜索方法
            results = self.arxiv_tool.searchPapersByMode(
                query=query,
                mode=self.config.search_mode,
                num_results=num_results,
                start_year=self.config.start_year,
                end_year=self.config.end_year,
                after_year=self.config.after_year
            )
            
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
            
            # 准备统一的论文文件夹路径（使用相对路径）
            import os
            from pathlib import Path
            project_root = Path(__file__).parent.parent.parent.parent  # 回到项目根目录
            paper_folder = project_root / "data" / "paper_analyze" / paper.arxiv_id
            paper_folder.mkdir(parents=True, exist_ok=True)
            paper_folder_str = str(paper_folder)
            
            # 检查是否已有OCR结果
            ocr_result = getattr(paper, 'ocr_result', None)
            
            if not ocr_result or len(ocr_result.strip()) < 500:
                # 设置远程OCR环境变量（在PDF下载之前，确保元数据提取也使用正确的OCR）
                if self.config.enable_remote_ocr:
                    import os
                    os.environ['REMOTE_OCR_ENDPOINT'] = self.config.remote_ocr_endpoint
                    os.environ['REMOTE_OCR_TIMEOUT'] = str(self.config.remote_ocr_timeout)
                    logger.info(f"🌐 使用远程OCR服务: {self.config.remote_ocr_endpoint} (超时: {self.config.remote_ocr_timeout}秒)")
                else:
                    logger.debug("🔍 使用本地PaddleOCR处理")
                
                # 下载PDF（这可能会触发元数据提取）
                logger.debug("下载PDF中...")
                paper.downloadPdf()
                
                # 执行OCR并保存到标准路径
                logger.debug("执行OCR识别...")
                ocr_result, status_info = paper.performOCR(
                    use_paddleocr=True,
                    use_remote_ocr=self.config.enable_remote_ocr,
                    auto_save=True,
                    save_path=paper_folder_str,
                    max_pages=25
                )
                
                # 确保OCR结果保存到paper对象
                paper.ocr_result = ocr_result
                paper.ocr_status_info = status_info
                
                if not ocr_result or len(ocr_result.strip()) < 500:
                    logger.warning(f"OCR结果过短或为空，跳过完整分析: {len(ocr_result) if ocr_result else 0} 字符")
                    return None
                
                logger.info(f"PaddleOCR成功，提取了 {status_info['char_count']} 字符，处理了 {status_info['processed_pages']}/{status_info['total_pages']} 页")
                logger.info(f"OCR结果已保存到: {paper_folder_str}/{paper.arxiv_id}_paddleocr.md")
                if status_info['is_oversized']:
                    logger.info("检测到超长文档，可能是毕业论文或书籍")
            else:
                logger.debug(f"使用现有OCR结果进行完整论文分析: {len(ocr_result)} 字符")
            
            # 限制用于LLM分析的字符数（默认10000字符）
            analysis_char_limit = getattr(self.config, 'ocr_char_limit_for_analysis', 10000)
            limited_ocr_result = ocr_result[:analysis_char_limit] if len(ocr_result) > analysis_char_limit else ocr_result
            
            if len(ocr_result) > analysis_char_limit:
                logger.info(f"OCR结果过长({len(ocr_result)}字符)，限制为{analysis_char_limit}字符用于相关性分析")
            
            # 使用FullPaperAnalysisLLM进行分析
            logger.debug("开始LLM分析完整论文...")
            full_analysis = self.full_paper_analyzer.analyze_full_paper(
                paper_content=limited_ocr_result,
                user_requirements=self.config.user_requirements
            )

            logger.debug(f"完整论文分析，justification: {full_analysis.justification}")
            
            logger.info(f"完整论文分析完成 (评分: {full_analysis.relevance_score:.2f}): {paper.title[:50]}...")
            return full_analysis
            
        except Exception as e:
            logger.error(f"完整论文分析失败: {e}")
            return None
    
    async def perform_deep_analysis(self, paper: ArxivData, paper_folder_str: str) -> bool:
        """
        执行深度论文分析，替代原来的 summarize_paper 功能
        
        Args:
            paper: 论文数据对象
            paper_folder_str: 论文文件夹路径
            
        Returns:
            bool: 深度分析是否成功
        """
        try:
            logger.info(f"🤖 开始深度论文分析: {paper.title[:50]}...")
            
            # 导入统一的分析服务
            from HomeSystem.integrations.paper_analysis import PaperAnalysisService
            
            # 创建分析服务实例
            analysis_config = {
                'analysis_model': self.config.deep_analysis_model,
                'vision_model': self.config.vision_model,
                'enable_user_prompt': self.config.enable_user_prompt,
                'user_prompt': self.config.user_prompt,
                'timeout': 600
            }
            
            # 记录用户提示词使用情况
            if self.config.enable_user_prompt and self.config.user_prompt:
                logger.info(f"📝 使用用户提示词进行深度分析")
                logger.debug(f"用户提示词: {self.config.user_prompt[:100]}...")
            
            analysis_service = PaperAnalysisService(default_config=analysis_config)
            
            # 准备论文数据（用于PDF下载，如果需要的话）
            paper_data = {
                'title': paper.title,
                'link': f"https://arxiv.org/abs/{paper.arxiv_id}",
                'snippet': getattr(paper, 'abstract', ''),
                'categories': getattr(paper, 'categories', ''),
                'arxiv_id': paper.arxiv_id
            }
            
            # 执行深度分析
            result = analysis_service.perform_deep_analysis(
                arxiv_id=paper.arxiv_id,
                paper_folder_path=paper_folder_str,
                config=analysis_config,
                paper_data=paper_data
            )
            
            if result['success']:
                # 添加发表时间到分析结果
                publication_date = getattr(paper, 'published_date', '未知')
                final_content = analysis_service.add_analysis_footer(
                    result['analysis_result'], 
                    publication_date=publication_date
                )
                
                # 重新保存带页脚的内容
                with open(result['analysis_file_path'], 'w', encoding='utf-8') as f:
                    f.write(final_content)
                
                # 将深度分析结果保存到paper对象中
                paper.deep_analysis_result = final_content
                paper.deep_analysis_completed = True
                paper.deep_analysis_file_path = result['analysis_file_path']
                
                logger.info(f"深度分析完成: {paper.arxiv_id}, 保存了 {len(final_content)} 字符")
                logger.info(f"分析结果已保存到: {result['analysis_file_path']}")
                
                return True
            else:
                logger.error(f"深度分析失败 {paper.arxiv_id}: {result.get('error', '未知错误')}")
                return False
                
        except Exception as e:
            logger.error(f"❌ 深度分析过程中发生异常 {paper.arxiv_id}: {e}")
            return False
    
    
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
            
            # 初始化论文处理标记
            setattr(paper, 'saved_to_database', False)
            setattr(paper, 'full_paper_analyzed', False)
            setattr(paper, 'deep_analysis_completed', False)  # 深度分析是否完成
            setattr(paper, 'deep_analysis_success', True)  # 默认深度分析成功（如果不执行深度分析）
            
            # 第一步：检查论文是否已在数据库中
            existing_paper = await self.check_paper_in_database(paper.arxiv_id)
            
            if existing_paper:
                logger.info(f"论文已在数据库中，跳过处理: {paper.arxiv_id}")
                # 从数据库中的数据创建ArxivData对象，保持一致性
                paper.final_is_relevant = existing_paper.processing_status == 'completed'
                paper.final_relevance_score = existing_paper.metadata.get('final_relevance_score', 0.0) if existing_paper.metadata else 0.0
                setattr(paper, 'saved_to_database', True)  # 已在数据库中的论文标记为已保存
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
            
            # 第三步：如果摘要相关性足够高，进行完整论文分析
            if abstract_analysis.is_relevant and abstract_analysis.relevance_score >= self.config.relevance_threshold:
                logger.info(f"摘要相关性高 ({abstract_analysis.relevance_score:.2f})，开始完整论文分析: {paper.title[:50]}...")
                
                # 执行完整论文分析（包含PDF下载和OCR）
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
                        
                        # 第四步：如果启用了深度分析且相关性评分足够高，则进行深度分析
                        # 此时OCR结果已经在analyze_full_paper中准备好，不会重复执行
                        deep_analysis_enabled = getattr(self.config, 'enable_deep_analysis', True)
                        deep_analysis_threshold = getattr(self.config, 'deep_analysis_threshold', 0.8)
                        
                        if (deep_analysis_enabled and 
                            full_analysis.relevance_score >= deep_analysis_threshold):
                            
                            logger.info(f"相关性评分足够高 ({full_analysis.relevance_score:.2f})，开始深度分析: {paper.title[:50]}...")
                            
                            # 重新计算论文文件夹路径（保持一致性）
                            from pathlib import Path
                            # For Docker: /app/HomeSystem/workflow/paper_gather_task/paper_gather_task.py -> /app (4 parents) -> /app/data
                            # For local: workflow/paper_gather_task/paper_gather_task.py -> project root (5 parents) -> project_root/data
                            project_root = Path(__file__).parent.parent.parent.parent
                            if not (project_root / "data").exists():
                                project_root = Path(__file__).parent.parent.parent.parent.parent
                            paper_folder = project_root / "data" / "paper_analyze" / paper.arxiv_id
                            paper_folder_str = str(paper_folder)
                            
                            deep_analysis_success = await self.perform_deep_analysis(paper, paper_folder_str)
                            setattr(paper, 'deep_analysis_success', deep_analysis_success)
                            
                            if deep_analysis_success:
                                logger.info(f"深度分析完成: {paper.title[:50]}...")
                            else:
                                logger.warning(f"深度分析失败: {paper.title[:50]}...")
                        else:
                            if not deep_analysis_enabled:
                                logger.debug(f"深度分析功能已禁用，跳过深度分析: {paper.title[:50]}...")
                            elif full_analysis.relevance_score < deep_analysis_threshold:
                                logger.debug(f"相关性评分不足深度分析阈值 ({full_analysis.relevance_score:.2f} < {deep_analysis_threshold})，跳过深度分析: {paper.title[:50]}...")
                    else:
                        logger.info(f"完整论文分析判定不相关 (评分: {full_analysis.relevance_score:.2f}): {paper.title}")
                else:
                    logger.warning(f"完整论文分析失败，由于OCR不可用，标记为不相关: {paper.title[:50]}...")
                    # OCR失败时，采用保守策略：标记为不相关，避免错误保存
                    paper.final_is_relevant = False
                    paper.final_relevance_score = 0.0
                    paper.full_paper_analysis_justification = f"Full paper analysis failed due to OCR service unavailability (abstract score was {abstract_analysis.relevance_score:.2f})"
                    logger.info(f"OCR失败保护：论文 {paper.arxiv_id} 被标记为不相关，将不会保存到数据库")
            else:
                logger.debug(f"摘要相关性低 ({abstract_analysis.relevance_score:.2f})，跳过完整分析: {paper.title[:50]}...")
                # 当跳过完整分析时，也设置默认的justification字段
                paper.full_paper_analysis_justification = getattr(paper, 'abstract_analysis_justification', 
                                                                 f"Full paper analysis skipped due to low abstract relevance score ({abstract_analysis.relevance_score:.2f})")
            
            # 第六步：如果论文符合要求（相关性达标），保存到数据库
            if paper.final_is_relevant and paper.final_relevance_score >= self.config.relevance_threshold:
                logger.info(f"论文符合要求，保存到数据库: {paper.arxiv_id} (评分: {paper.final_relevance_score:.2f})")
                save_success = await self.save_paper_to_database(paper)
                if save_success:
                    # 设置保存标记，用于后续统计
                    setattr(paper, 'saved_to_database', True)
                else:
                    logger.warning(f"论文保存到数据库失败，但继续处理: {paper.arxiv_id}")
                    setattr(paper, 'saved_to_database', False)
            else:
                logger.debug(f"论文不符合要求，不保存到数据库: {paper.arxiv_id} (相关性: {paper.final_is_relevant}, 评分: {paper.final_relevance_score:.2f})")
                setattr(paper, 'saved_to_database', False)
            
            # 第七步：处理完毕释放内存
            # 清理PDF和OCR结果，释放内存
            if hasattr(paper, 'clearPdf'):
                paper.clearPdf()
            if hasattr(paper, 'clearOcrResult'):
                paper.clearOcrResult()
                
            processed_papers.append(paper)
        
        return processed_papers
        
    async def run(self) -> Dict[str, Any]:
        """执行论文收集逻辑"""
        logger.info("开始执行论文收集任务")
        
        all_papers = []
        total_relevant_papers = 0
        total_saved_papers = 0
        
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
                    "saved_papers": 0,
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
            
            # 统计保存到数据库的论文数量
            saved_papers = [p for p in processed_papers 
                          if hasattr(p, 'saved_to_database') and getattr(p, 'saved_to_database', False)]
            total_saved_papers = len(saved_papers)
            
            # 添加查询标识
            for paper in processed_papers:
                paper.search_query = self.config.search_query
            
            all_papers = processed_papers
            
            logger.info(f"查询 '{self.config.search_query}' 完成: 找到 {len(processed_papers)} 篇论文，"
                       f"其中 {len(relevant_papers)} 篇相关（阈值: {self.config.relevance_threshold}），"
                       f"保存了 {total_saved_papers} 篇到数据库")
            
            # 按最终相关性评分排序
            all_papers.sort(key=lambda x: x.final_relevance_score, reverse=True)
            
            logger.info(f"论文收集任务完成: 总共处理 {len(all_papers)} 篇论文，其中 {total_relevant_papers} 篇相关，{total_saved_papers} 篇已保存")
            
            return {
                "message": "论文收集任务执行完成",
                "total_papers": len(all_papers),
                "relevant_papers": total_relevant_papers,
                "saved_papers": total_saved_papers,
                "analyzed_papers": len([p for p in processed_papers if hasattr(p, 'full_paper_analyzed') and p.full_paper_analyzed]),
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
                "saved_papers": 0,
                "error": str(e)
            }
