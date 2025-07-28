"""
论文分析Agent

基于LangGraph的英文论文分析智能体，使用并行LLM提取不同字段组，提高效率。
"""
from .llm_factory import llm_factory
from .base_graph import BaseGraph
from .tool.paper_analysis_tools import create_paper_analysis_tools

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, START, END
from typing import Annotated, Optional, Dict, Any, List
from typing_extensions import TypedDict
import operator
import json
from pathlib import Path
from loguru import logger

# from langchain_core.messages import AIMessage  # Not used in parallel implementation


class PaperAnalysisState(TypedDict):
    """论文分析状态"""
    paper_text: str  # 输入的论文文本
    
    # 并行提取的字段组
    background_objectives_result: Optional[Dict[str, Any]]  # 背景和目标
    methods_findings_result: Optional[Dict[str, Any]]      # 方法和发现
    conclusions_future_result: Optional[Dict[str, Any]]    # 结论、限制和未来工作
    
    # 合成的关键词
    keywords_result: Optional[Dict[str, Any]]
    
    # 最终聚合结果
    final_result: Optional[Dict[str, Any]]
    
    # 执行状态跟踪
    parallel_tasks_completed: Annotated[int, operator.add]
    extraction_errors: Annotated[List[str], operator.add]


class PaperAnalysisConfig:
    """论文分析配置类"""
    
    def __init__(self, 
                 model_name: str = "ollama.Qwen3_30B",
                 memory_enabled: bool = False,
                 parallel_execution: bool = True,
                 validate_results: bool = True,
                 custom_settings: Optional[Dict[str, Any]] = None):
        
        self.model_name = model_name
        self.memory_enabled = memory_enabled
        self.parallel_execution = parallel_execution  # 是否启用并行执行
        self.validate_results = validate_results      # 是否验证结果完整性
        self.custom_settings = custom_settings or {}
    
    @classmethod
    def load_from_file(cls, config_path: str) -> "PaperAnalysisConfig":
        """从配置文件加载配置"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            return cls(**config_data)
        except Exception as e:
            logger.warning(f"配置文件加载失败，使用默认配置: {e}")
            return cls()
    
    def save_to_file(self, config_path: str) -> None:
        """保存配置到文件"""
        config_data = {
            'model_name': self.model_name,
            'memory_enabled': self.memory_enabled,
            'parallel_execution': self.parallel_execution,
            'validate_results': self.validate_results,
            'custom_settings': self.custom_settings
        }
        
        # 创建目录
        Path(config_path).parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"配置已保存到: {config_path}")


class PaperAnalysisAgent(BaseGraph):
    """论文分析智能体
    
    功能：
    1. 接收OCR处理后的英文论文全文
    2. 使用3个LLM并行提取不同字段组
    3. 从已提取字段合成关键词
    4. 聚合所有结果为标准化的8字段JSON格式
    """
    
    def __init__(self, 
                 config: Optional[PaperAnalysisConfig] = None,
                 config_path: Optional[str] = None):
        
        super().__init__()
        
        # 加载配置
        if config_path:
            self.config = PaperAnalysisConfig.load_from_file(config_path)
        elif config:
            self.config = config
        else:
            self.config = PaperAnalysisConfig()
        
        logger.info(f"初始化论文分析智能体，使用模型: {self.config.model_name}")
        
        # 创建LLM
        self.llm = llm_factory.create_llm(model_name=self.config.model_name)
        
        # 创建分析工具
        self.tools = create_paper_analysis_tools(self.llm)
        self.background_objectives_tool = self.tools[0]  # BackgroundObjectivesTool
        self.methods_findings_tool = self.tools[1]       # MethodsFindingsTool
        self.conclusions_future_tool = self.tools[2]     # ConclusionsFutureTool
        self.keywords_synthesis_tool = self.tools[3]     # KeywordsSynthesisTool
        
        # 设置内存管理
        self.memory = MemorySaver() if self.config.memory_enabled else None
        
        # 构建图
        self._build_graph()
        
        logger.info("论文分析智能体初始化完成")
    
    def _build_graph(self) -> None:
        """构建并行分析工作流图"""
        # 创建状态图
        graph = StateGraph(PaperAnalysisState)
        
        # 添加并行提取节点
        graph.add_node("extract_background_objectives", self._extract_background_objectives_node)
        graph.add_node("extract_methods_findings", self._extract_methods_findings_node)  
        graph.add_node("extract_conclusions_future", self._extract_conclusions_future_node)
        
        # 添加关键词合成和结果聚合节点
        graph.add_node("synthesize_keywords", self._synthesize_keywords_node)
        graph.add_node("aggregate_results", self._aggregate_results_node)
        
        # 设置并行流程
        graph.add_edge(START, "extract_background_objectives")
        graph.add_edge(START, "extract_methods_findings")
        graph.add_edge(START, "extract_conclusions_future")
        
        # 所有并行提取完成后，进行关键词合成
        graph.add_edge("extract_background_objectives", "synthesize_keywords")
        graph.add_edge("extract_methods_findings", "synthesize_keywords") 
        graph.add_edge("extract_conclusions_future", "synthesize_keywords")
        
        # 关键词合成完成后，聚合所有结果
        graph.add_edge("synthesize_keywords", "aggregate_results")
        graph.add_edge("aggregate_results", END)
        
        # 编译图
        self.agent = graph.compile(checkpointer=self.memory)
        
        logger.info("并行论文分析工作流图构建完成")
    
    def _extract_background_objectives_node(self, state: PaperAnalysisState) -> Dict[str, Any]:
        """提取背景和目标节点"""
        logger.info("开始并行提取：研究背景和目标...")
        
        try:
            result = self.background_objectives_tool._run(paper_text=state["paper_text"])
            
            # 尝试解析JSON结果
            try:
                parsed_result = json.loads(result)
                logger.info("背景和目标提取完成")
                return {
                    "background_objectives_result": parsed_result,
                    "parallel_tasks_completed": 1
                }
            except json.JSONDecodeError:
                logger.warning("背景和目标提取结果不是有效JSON格式")
                return {
                    "background_objectives_result": {"raw_result": result},
                    "parallel_tasks_completed": 1
                }
                
        except Exception as e:
            logger.error(f"背景和目标提取失败: {e}")
            return {
                "background_objectives_result": {"error": f"提取失败: {str(e)}"},
                "parallel_tasks_completed": 1,
                "extraction_errors": [f"背景和目标提取: {str(e)}"]
            }
    
    def _extract_methods_findings_node(self, state: PaperAnalysisState) -> Dict[str, Any]:
        """提取方法和发现节点"""
        logger.info("开始并行提取：研究方法和主要发现...")
        
        try:
            result = self.methods_findings_tool._run(paper_text=state["paper_text"])
            
            # 尝试解析JSON结果
            try:
                parsed_result = json.loads(result)
                logger.info("方法和发现提取完成")
                return {
                    "methods_findings_result": parsed_result,
                    "parallel_tasks_completed": 1
                }
            except json.JSONDecodeError:
                logger.warning("方法和发现提取结果不是有效JSON格式")
                return {
                    "methods_findings_result": {"raw_result": result},
                    "parallel_tasks_completed": 1
                }
                
        except Exception as e:
            logger.error(f"方法和发现提取失败: {e}")
            return {
                "methods_findings_result": {"error": f"提取失败: {str(e)}"},
                "parallel_tasks_completed": 1,
                "extraction_errors": [f"方法和发现提取: {str(e)}"]
            }
    
    def _extract_conclusions_future_node(self, state: PaperAnalysisState) -> Dict[str, Any]:
        """提取结论和未来工作节点"""
        logger.info("开始并行提取：结论、限制和未来工作...")
        
        try:
            result = self.conclusions_future_tool._run(paper_text=state["paper_text"])
            
            # 尝试解析JSON结果
            try:
                parsed_result = json.loads(result)
                logger.info("结论和未来工作提取完成")
                return {
                    "conclusions_future_result": parsed_result,
                    "parallel_tasks_completed": 1
                }
            except json.JSONDecodeError:
                logger.warning("结论和未来工作提取结果不是有效JSON格式")
                return {
                    "conclusions_future_result": {"raw_result": result},
                    "parallel_tasks_completed": 1
                }
                
        except Exception as e:
            logger.error(f"结论和未来工作提取失败: {e}")
            return {
                "conclusions_future_result": {"error": f"提取失败: {str(e)}"},
                "parallel_tasks_completed": 1,
                "extraction_errors": [f"结论和未来工作提取: {str(e)}"]
            }
    
    def _synthesize_keywords_node(self, state: PaperAnalysisState) -> Dict[str, Any]:
        """合成关键词节点"""
        logger.info("开始从已提取字段合成关键词...")
        
        try:
            # 检查所有并行任务是否完成
            if state.get("parallel_tasks_completed", 0) < 3:
                logger.warning("并行提取任务未全部完成，等待...")
                return {}
            
            # 提取各个字段的内容
            background_obj = state.get("background_objectives_result") or {}
            methods_find = state.get("methods_findings_result") or {}
            conclusions_fut = state.get("conclusions_future_result") or {}
            
            # 提取具体字段内容
            research_background = background_obj.get("research_background", "")
            research_objectives = background_obj.get("research_objectives", "")
            methods = methods_find.get("methods", "")
            key_findings = methods_find.get("key_findings", "")
            conclusions = conclusions_fut.get("conclusions", "")
            
            # 检查字段完整性
            if not all([research_background, research_objectives, methods, key_findings, conclusions]):
                logger.warning("部分字段提取不完整，使用可用内容合成关键词")
            
            # 调用关键词合成工具
            result = self.keywords_synthesis_tool._run(
                research_background=research_background,
                research_objectives=research_objectives,
                methods=methods,
                key_findings=key_findings,
                conclusions=conclusions
            )
            
            # 尝试解析JSON结果
            try:
                parsed_result = json.loads(result)
                logger.info("关键词合成完成")
                return {"keywords_result": parsed_result}
            except json.JSONDecodeError:
                logger.warning("关键词合成结果不是有效JSON格式")
                return {"keywords_result": {"raw_result": result}}
                
        except Exception as e:
            logger.error(f"关键词合成失败: {e}")
            return {
                "keywords_result": {"error": f"合成失败: {str(e)}"},
                "extraction_errors": [f"关键词合成: {str(e)}"]
            }
    
    def _aggregate_results_node(self, state: PaperAnalysisState) -> Dict[str, Any]:
        """聚合结果节点"""
        logger.info("开始聚合所有提取结果...")
        
        try:
            # 提取各个部分的结果
            background_obj = state.get("background_objectives_result") or {}
            methods_find = state.get("methods_findings_result") or {}
            conclusions_fut = state.get("conclusions_future_result") or {}
            keywords = state.get("keywords_result") or {}
            
            # 构建最终的8字段结构
            final_analysis = {
                "keywords": keywords.get("keywords", []),
                "research_background": background_obj.get("research_background", ""),
                "research_objectives": background_obj.get("research_objectives", ""),
                "methods": methods_find.get("methods", ""),
                "key_findings": methods_find.get("key_findings", ""),
                "conclusions": conclusions_fut.get("conclusions", ""),
                "limitations": conclusions_fut.get("limitations", ""),
                "future_work": conclusions_fut.get("future_work", "")
            }
            
            # 验证结果完整性
            if self.config.validate_results:
                missing_fields = [field for field, value in final_analysis.items() 
                                if not value or (isinstance(value, list) and not value)]
                if missing_fields:
                    logger.warning(f"以下字段提取不完整: {missing_fields}")
            
            # 构建最终结果
            final_result = {
                "analysis": final_analysis,
                "extraction_method": "parallel_llm",
                "completed_tasks": state.get("parallel_tasks_completed", 0),
                "extraction_errors": state.get("extraction_errors", []),
                "timestamp": self._get_timestamp()
            }
            
            logger.info("论文分析聚合完成")
            return {"final_result": final_result}
            
        except Exception as e:
            logger.error(f"结果聚合失败: {e}")
            return {
                "final_result": {
                    "error": f"聚合失败: {str(e)}",
                    "timestamp": self._get_timestamp()
                }
            }
    
    def _get_timestamp(self) -> str:
        """获取时间戳"""
        from datetime import datetime
        return datetime.now().isoformat()
    
    def analyze_paper(self, paper_text: str, thread_id: str = "1") -> Dict[str, Any]:
        """分析论文
        
        Args:
            paper_text: OCR处理后的英文论文全文
            thread_id: 线程ID（用于内存管理）
        
        Returns:
            包含分析结果的字典
        """
        logger.info("开始并行论文分析...")
        
        try:
            # 创建初始状态
            initial_state: PaperAnalysisState = {
                "paper_text": paper_text,
                "background_objectives_result": None,
                "methods_findings_result": None,
                "conclusions_future_result": None,
                "keywords_result": None,
                "final_result": None,
                "parallel_tasks_completed": 0,
                "extraction_errors": []
            }
            
            # 配置
            from langchain_core.runnables import RunnableConfig
            config_dict = RunnableConfig(
                configurable={"thread_id": thread_id},
                recursion_limit=100
            )
            
            # 执行分析
            result = self.agent.invoke(initial_state, config_dict)

        
            
            if result and "final_result" in result:
                logger.info("并行论文分析成功完成")
                return result["final_result"]
            else:
                logger.error("论文分析未能产生有效结果")
                return {"error": "分析未能产生有效结果", "raw_result": result}
                
        except Exception as e:
            logger.error(f"论文分析失败: {e}")
            return {"error": f"分析失败: {str(e)}"}
    
    def get_structured_result(self, analysis_result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """提取结构化结果
        
        Args:
            analysis_result: 分析结果
        
        Returns:
            标准化的8字段结构，如果提取失败返回None
        """
        try:
            if "analysis" in analysis_result:
                analysis_data = analysis_result["analysis"]
                
                # 检查是否包含所有必需字段
                required_fields = [
                    "keywords", "research_background", "research_objectives",
                    "methods", "key_findings", "conclusions", "limitations", "future_work"
                ]
                
                if all(field in analysis_data for field in required_fields):
                    return {field: analysis_data[field] for field in required_fields}
                else:
                    logger.warning("分析结果缺少必需字段")
                    return analysis_data
            else:
                logger.warning("分析结果格式不正确")
                return None
                
        except Exception as e:
            logger.error(f"提取结构化结果失败: {e}")
            return None
    
    def get_config(self) -> PaperAnalysisConfig:
        """获取当前配置"""
        return self.config
    
    def update_config(self, **kwargs) -> None:
        """更新配置"""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
                logger.info(f"配置更新: {key} = {value}")
            else:
                logger.warning(f"未知配置项: {key}")
        
        # 如果模型相关配置更新，重新创建LLM和工具
        if 'model_name' in kwargs:
            self.llm = llm_factory.create_llm(model_name=self.config.model_name)
            self.tools = create_paper_analysis_tools(self.llm)
            self.background_objectives_tool = self.tools[0]
            self.methods_findings_tool = self.tools[1]
            self.conclusions_future_tool = self.tools[2]
            self.keywords_synthesis_tool = self.tools[3]
            logger.info("LLM和工具已重新创建")