"""
论文分析Agent

基于LangGraph的英文论文分析智能体，专门用于提取和分析学术论文的结构化信息。
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

from langchain_core.messages import AIMessage, SystemMessage, HumanMessage


class PaperAnalysisState(TypedDict):
    """论文分析状态"""
    paper_text: str  # 输入的论文文本
    iteration_round: Annotated[int, operator.add]  # 当前迭代轮次
    analysis_result: Optional[Dict[str, Any]]  # 分析结果
    quality_assessment: Optional[Dict[str, Any]]  # 质量评估结果
    iteration_history: Annotated[List[Dict[str, Any]], operator.add]  # 迭代历史
    final_result: Optional[Dict[str, Any]]  # 最终结果


class PaperAnalysisConfig:
    """论文分析配置类"""
    
    def __init__(self, 
                 model_name: str = "ollama.Qwen3_30B",
                 max_iterations: int = 3,
                 quality_threshold: float = 8.0,
                 memory_enabled: bool = False,
                 auto_improve: bool = True,
                 custom_settings: Optional[Dict[str, Any]] = None):
        
        self.model_name = model_name
        self.max_iterations = max_iterations
        self.quality_threshold = quality_threshold  # 质量阈值，超过此值则接受结果
        self.memory_enabled = memory_enabled
        self.auto_improve = auto_improve  # 是否自动进行迭代改进
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
            'max_iterations': self.max_iterations,
            'quality_threshold': self.quality_threshold,
            'memory_enabled': self.memory_enabled,
            'auto_improve': self.auto_improve,
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
    2. 使用LLM进行结构化分析，提取8个关键字段
    3. 通过迭代优化提高分析质量
    4. 输出标准化的JSON格式结果
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
        self.structured_analysis_tool = self.tools[0]  # StructuredAnalysisTool
        self.quality_assessment_tool = self.tools[1]  # QualityAssessmentTool
        
        # 设置内存管理
        self.memory = MemorySaver() if self.config.memory_enabled else None
        
        # 构建图
        self._build_graph()
        
        logger.info("论文分析智能体初始化完成")
    
    def _build_graph(self) -> None:
        """构建分析工作流图"""
        # 创建状态图
        graph = StateGraph(PaperAnalysisState)
        
        # 添加节点
        graph.add_node("initial_analysis", self._initial_analysis_node)
        graph.add_node("quality_check", self._quality_check_node)
        graph.add_node("refinement", self._refinement_node)
        graph.add_node("finalize", self._finalize_node)
        
        # 设置流程
        graph.add_edge(START, "initial_analysis")
        graph.add_edge("initial_analysis", "quality_check")
        graph.add_conditional_edges(
            "quality_check",
            self._should_refine,
            {
                "refine": "refinement",
                "finalize": "finalize"
            }
        )
        graph.add_edge("refinement", "quality_check")
        graph.add_edge("finalize", END)
        
        # 编译图
        self.agent = graph.compile(checkpointer=self.memory)
        
        logger.info("论文分析工作流图构建完成")
    
    def _initial_analysis_node(self, state: PaperAnalysisState) -> Dict[str, Any]:
        """初始分析节点"""
        logger.info("开始初始论文分析...")
        
        try:
            # 使用结构化分析工具进行初始分析
            result = self.structured_analysis_tool._run(
                paper_text=state["paper_text"],
                iteration_round=1
            )
            
            # 尝试解析JSON结果
            try:
                analysis_result = json.loads(result)
                logger.info("初始分析完成，成功提取结构化数据")
            except json.JSONDecodeError:
                logger.warning("初始分析结果不是有效JSON格式，使用原始结果")
                analysis_result = {"raw_result": result}
            
            return {
                "iteration_round": 1,
                "analysis_result": analysis_result,
                "iteration_history": [{
                    "round": 1,
                    "type": "initial_analysis",
                    "result": analysis_result,
                    "timestamp": self._get_timestamp()
                }]
            }
            
        except Exception as e:
            logger.error(f"初始分析失败: {e}")
            return {
                "iteration_round": 1,
                "analysis_result": {"error": f"初始分析失败: {str(e)}"},
                "iteration_history": [{
                    "round": 1,
                    "type": "error",
                    "error": str(e),
                    "timestamp": self._get_timestamp()
                }]
            }
    
    def _quality_check_node(self, state: PaperAnalysisState) -> Dict[str, Any]:
        """质量检查节点"""
        logger.info(f"执行第{state['iteration_round']}轮质量检查...")
        
        try:
            if not state.get("analysis_result"):
                logger.error("没有分析结果可供质量检查")
                return {"quality_assessment": {"error": "没有分析结果"}}
            
            # 使用质量评估工具
            assessment_result = self.quality_assessment_tool._run(
                json.dumps(state["analysis_result"], ensure_ascii=False)
            )
            
            # 尝试解析评估结果
            try:
                quality_assessment = json.loads(assessment_result)
                overall_score = quality_assessment.get("overall_score", 0)
                recommendation = quality_assessment.get("recommendation", "REFINE")
                
                logger.info(f"质量评估完成 - 总分: {overall_score}, 建议: {recommendation}")
                
                return {
                    "quality_assessment": quality_assessment,
                    "iteration_history": [{
                        "round": state["iteration_round"],
                        "type": "quality_check",
                        "assessment": quality_assessment,
                        "timestamp": self._get_timestamp()
                    }]
                }
                
            except json.JSONDecodeError:
                logger.warning("质量评估结果不是有效JSON格式")
                return {
                    "quality_assessment": {"raw_assessment": assessment_result},
                    "iteration_history": [{
                        "round": state["iteration_round"],
                        "type": "quality_check_error",
                        "error": "JSON解析失败",
                        "timestamp": self._get_timestamp()
                    }]
                }
                
        except Exception as e:
            logger.error(f"质量检查失败: {e}")
            return {
                "quality_assessment": {"error": f"质量检查失败: {str(e)}"},
                "iteration_history": [{
                    "round": state["iteration_round"],
                    "type": "error",
                    "error": str(e),
                    "timestamp": self._get_timestamp()
                }]
            }
    
    def _refinement_node(self, state: PaperAnalysisState) -> Dict[str, Any]:
        """改进节点"""
        new_round = state["iteration_round"] + 1
        logger.info(f"开始第{new_round}轮分析改进...")
        
        try:
            # 使用结构化分析工具进行改进分析
            result = self.structured_analysis_tool._run(
                paper_text=state["paper_text"],
                iteration_round=new_round,
                previous_analysis=state.get("analysis_result")
            )
            
            # 尝试解析JSON结果
            try:
                refined_result = json.loads(result)
                logger.info(f"第{new_round}轮改进分析完成")
            except json.JSONDecodeError:
                logger.warning(f"第{new_round}轮分析结果不是有效JSON格式")
                refined_result = {"raw_result": result}
            
            return {
                "iteration_round": 1,  # 增加1轮
                "analysis_result": refined_result,
                "iteration_history": [{
                    "round": new_round,
                    "type": "refinement",
                    "result": refined_result,
                    "timestamp": self._get_timestamp()
                }]
            }
            
        except Exception as e:
            logger.error(f"第{new_round}轮改进分析失败: {e}")
            return {
                "iteration_round": 1,
                "analysis_result": state.get("analysis_result"),  # 保持原结果
                "iteration_history": [{
                    "round": new_round,
                    "type": "error",
                    "error": str(e),
                    "timestamp": self._get_timestamp()
                }]
            }
    
    def _finalize_node(self, state: PaperAnalysisState) -> Dict[str, Any]:
        """最终化节点"""
        logger.info("最终化分析结果...")
        
        final_result = {
            "analysis": state.get("analysis_result", {}),
            "quality_assessment": state.get("quality_assessment", {}),
            "total_iterations": state["iteration_round"],
            "iteration_history": state.get("iteration_history", []),
            "timestamp": self._get_timestamp()
        }
        
        logger.info(f"论文分析完成，共进行{state['iteration_round']}轮迭代")
        
        return {"final_result": final_result}
    
    def _should_refine(self, state: PaperAnalysisState) -> str:
        """判断是否需要进一步改进"""
        # 检查是否达到最大迭代次数
        if state["iteration_round"] >= self.config.max_iterations:
            logger.info(f"已达到最大迭代次数({self.config.max_iterations})")
            return "finalize"
        
        # 如果没有质量评估结果，则结束
        quality_assessment = state.get("quality_assessment")
        if not quality_assessment:
            logger.info("没有质量评估结果，结束迭代")
            return "finalize"
        
        # 如果不启用自动改进，则结束
        if not self.config.auto_improve:
            logger.info("自动改进功能已禁用，结束迭代")
            return "finalize"
        
        # 检查质量分数
        overall_score = quality_assessment.get("overall_score", 0)
        if overall_score >= self.config.quality_threshold:
            logger.info(f"质量分数({overall_score})达到阈值({self.config.quality_threshold})")
            return "finalize"
        
        # 检查推荐
        recommendation = quality_assessment.get("recommendation", "REFINE")
        if recommendation == "ACCEPT":
            logger.info("质量评估建议接受，结束迭代")
            return "finalize"
        
        logger.info(f"质量分数({overall_score})未达到阈值，继续改进")
        return "refine"
    
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
        logger.info("开始论文分析...")
        
        try:
            # 创建初始状态
            initial_state: PaperAnalysisState = {
                "paper_text": paper_text,
                "iteration_round": 0,
                "analysis_result": None,
                "quality_assessment": None,
                "iteration_history": [],
                "final_result": None
            }
            
            # 配置
            config_dict = {"configurable": {"thread_id": thread_id}, "recursion_limit": 100}
            
            # 执行分析
            result = self.agent.invoke(initial_state, config_dict)
            
            if result and "final_result" in result:
                logger.info("论文分析成功完成")
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
            self.structured_analysis_tool = self.tools[0]
            self.quality_assessment_tool = self.tools[1]
            logger.info("LLM和工具已重新创建")