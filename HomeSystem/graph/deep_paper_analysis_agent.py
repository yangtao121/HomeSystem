"""
深度论文分析Agent

基于LangGraph的论文深度分析智能体，实现两阶段工作流：
1. 英文深度分析阶段 - 迭代式分析，可反复调用工具
2. 翻译阶段 - 将分析结果翻译成中文并格式化输出

支持云端LLM文本分析 + 本地VLM图片理解的混合架构。
"""

import json
import operator
from pathlib import Path
from typing import Annotated, Any, Dict, List, Optional
from typing_extensions import TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, START, END
from langchain_core.runnables import RunnableConfig
from loguru import logger

from .base_graph import BaseGraph
from .llm_factory import get_llm
from .tool.image_analysis_tool import create_image_analysis_tool
from .tool.deep_analysis_tools import create_analysis_tools
from .tool.paper_translation_tool import create_translation_tool
from .parser.paper_folder_parser import create_paper_folder_parser
from .formatter.markdown_formatter import create_markdown_formatter


class DeepPaperAnalysisState(TypedDict):
    """深度论文分析状态 - 结构化输出便于markdown生成"""
    # 输入数据
    base_folder_path: str                           # 论文文件夹路径
    paper_text: str                                 # 论文markdown文本
    available_images: List[str]                     # 可用图片列表
    image_mappings: Dict[str, str]                  # 图片路径映射 (相对路径 -> 绝对路径)
    
    # 深度分析结果（英文）
    main_contributions: Optional[Dict[str, Any]]     # 主要贡献（逐条列出）
    background_analysis: Optional[Dict[str, Any]]    # 背景分析
    methodology_analysis: Optional[Dict[str, Any]]   # 方法分析（支持子标题）
    experimental_results: Optional[Dict[str, Any]]   # 实验结果分析
    
    # 图片分析结果（英文）
    analyzed_images: Optional[Dict[str, Any]]        # 已分析的图片内容
    image_insights: Optional[Dict[str, Any]]         # 图片提供的洞察
    
    # 翻译结果（中文）
    translated_contributions: Optional[Dict[str, Any]]    # 翻译后的主要贡献
    translated_background: Optional[Dict[str, Any]]       # 翻译后的背景
    translated_methodology: Optional[Dict[str, Any]]      # 翻译后的方法
    translated_results: Optional[Dict[str, Any]]          # 翻译后的结果
    
    # 执行状态跟踪
    analysis_iteration: Annotated[int, operator.add]      # 分析轮次
    completed_tasks: List[str]                             # 完成的任务列表
    is_analysis_complete: bool                             # 深度分析是否完成
    is_translation_complete: bool                          # 翻译是否完成
    analysis_errors: Annotated[List[str], operator.add]   # 错误记录


class DeepPaperAnalysisConfig:
    """深度论文分析配置类"""
    
    def __init__(self,
                 analysis_model: str = "deepseek.DeepSeek_V3",
                 vision_model: str = "ollama.llava", 
                 translation_model: str = "ollama.Qwen3_30B",
                 max_analysis_iterations: int = 10,
                 enable_translation: bool = True,
                 target_language: str = "zh",
                 memory_enabled: bool = True,
                 custom_settings: Optional[Dict[str, Any]] = None):
        
        self.analysis_model = analysis_model          # 主分析LLM
        self.vision_model = vision_model              # 图片理解VLM
        self.translation_model = translation_model    # 翻译LLM
        self.max_analysis_iterations = max_analysis_iterations
        self.enable_translation = enable_translation
        self.target_language = target_language
        self.memory_enabled = memory_enabled
        self.custom_settings = custom_settings or {}
    
    @classmethod
    def load_from_file(cls, config_path: str) -> "DeepPaperAnalysisConfig":
        """从配置文件加载配置"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            return cls(**config_data)
        except Exception as e:
            logger.warning(f"配置文件加载失败，使用默认配置: {e}")
            return cls()


class DeepPaperAnalysisAgent(BaseGraph):
    """深度论文分析智能体
    
    功能：
    1. 两阶段工作流：英文深度分析 → 中文翻译
    2. 迭代式分析：LLM可反复调用工具直到完成
    3. 混合架构：云端LLM + 本地VLM
    4. 结构化输出：便于生成markdown报告
    """
    
    def __init__(self,
                 config: Optional[DeepPaperAnalysisConfig] = None,
                 config_path: Optional[str] = None,
                 **kwargs):
        
        super().__init__(**kwargs)
        
        # 加载配置
        if config_path:
            self.config = DeepPaperAnalysisConfig.load_from_file(config_path)
        elif config:
            self.config = config
        else:
            self.config = DeepPaperAnalysisConfig()
        
        logger.info(f"初始化深度论文分析智能体")
        logger.info(f"分析模型: {self.config.analysis_model}")
        logger.info(f"视觉模型: {self.config.vision_model}")
        logger.info(f"翻译模型: {self.config.translation_model}")
        
        # 创建主分析LLM
        self.analysis_llm = get_llm(self.config.analysis_model)
        
        # 设置内存管理
        self.memory = MemorySaver() if self.config.memory_enabled else None
        
        # 工具实例将在分析时创建（需要文件夹路径）
        self.image_tool = None
        self.analysis_tools = None
        self.translation_tool = None
        
        # 构建图
        self._build_graph()
        
        logger.info("深度论文分析智能体初始化完成")
    
    def _build_graph(self) -> None:
        """构建两阶段分析工作流图"""
        graph = StateGraph(DeepPaperAnalysisState)
        
        # 第一阶段：英文深度分析
        graph.add_node("initialize_analysis", self._initialize_analysis_node)
        graph.add_node("iterative_english_analysis", self._iterative_english_analysis_node)
        graph.add_node("extract_contributions", self._extract_contributions_node)
        graph.add_node("analyze_methodology", self._analyze_methodology_node)
        graph.add_node("analyze_results", self._analyze_results_node)
        graph.add_node("analyze_background", self._analyze_background_node)
        
        # 第二阶段：翻译
        graph.add_node("translate_all_sections", self._translate_all_sections_node)
        
        # 构建两阶段流程
        graph.add_edge(START, "initialize_analysis")
        graph.add_edge("initialize_analysis", "iterative_english_analysis")
        
        # 英文分析阶段的条件分支
        graph.add_conditional_edges(
            "iterative_english_analysis",
            self._should_continue_english_analysis,
            {
                "continue": "iterative_english_analysis",  # 继续迭代
                "extract_contributions": "extract_contributions",  # 开始提取贡献
            }
        )
        
        # 完成英文分析的各个部分
        graph.add_edge("extract_contributions", "analyze_methodology")
        graph.add_edge("analyze_methodology", "analyze_results") 
        graph.add_edge("analyze_results", "analyze_background")
        
        # 进入翻译阶段
        graph.add_conditional_edges(
            "analyze_background",
            self._should_translate,
            {
                "translate": "translate_all_sections",
                "skip_translation": END
            }
        )
        
        graph.add_edge("translate_all_sections", END)
        
        # 编译图
        self.agent = graph.compile(checkpointer=self.memory)
        logger.info("两阶段深度分析工作流图构建完成")
    
    def _initialize_analysis_node(self, state: DeepPaperAnalysisState) -> Dict[str, Any]:
        """初始化分析节点"""
        logger.info("初始化论文分析...")
        
        # 创建工具实例
        base_folder = state["base_folder_path"]
        self.image_tool = create_image_analysis_tool(base_folder, self.config.vision_model)
        self.analysis_tools = create_analysis_tools(self.config.analysis_model)
        self.translation_tool = create_translation_tool(self.config.translation_model, self.config.target_language)
        
        # 按名称索引分析工具
        self.analysis_tools_dict = {tool.name: tool for tool in self.analysis_tools}
        
        logger.info(f"工具初始化完成：图片分析工具，{len(self.analysis_tools)}个分析工具，翻译工具")
        
        # 分析可用图片
        available_images = state.get("available_images", [])
        logger.info(f"可分析图片数量: {len(available_images)}")
        
        return {
            "analysis_iteration": 1,
            "completed_tasks": ["tools_initialized"],
            "is_analysis_complete": False,
            "is_translation_complete": False,
            "analyzed_images": {},
            "image_insights": {}
        }
    
    def _iterative_english_analysis_node(self, state: DeepPaperAnalysisState) -> Dict[str, Any]:
        """迭代英文分析节点 - 可反复调用工具直到完成"""
        current_iteration = state.get("analysis_iteration", 0)
        logger.info(f"开始第 {current_iteration} 轮英文分析...")
        
        # 检查是否达到最大迭代次数
        if current_iteration >= self.config.max_analysis_iterations:
            logger.warning(f"达到最大迭代次数 {self.config.max_analysis_iterations}，结束迭代分析")
            return {"is_analysis_complete": True}
        
        # 生成决策提示词
        decision_prompt = self._generate_analysis_decision_prompt(state)
        
        try:
            # LLM决策下一步行动
            response = self.analysis_llm.invoke(decision_prompt)
            decision_content = response.content if hasattr(response, 'content') else str(response)
            
            logger.info(f"LLM分析决策 (第{current_iteration}轮): {decision_content[:200]}...")
            
            # 解析LLM的决策
            action_result = self._parse_and_execute_decision(decision_content, state)
            
            # 更新状态
            update_dict = {
                "analysis_iteration": 1,
                **action_result
            }
            
            return update_dict
            
        except Exception as e:
            logger.error(f"迭代分析失败 (第{current_iteration}轮): {e}")
            return {
                "analysis_errors": [f"第{current_iteration}轮分析失败: {str(e)}"],
                "analysis_iteration": 1
            }
    
    def _generate_analysis_decision_prompt(self, state: DeepPaperAnalysisState) -> str:
        """生成分析决策提示词"""
        return f"""
You are conducting deep analysis of an academic paper in English. You are an expert researcher who can make intelligent decisions about what to analyze next.

**Current Analysis Status:**
- Paper text length: {len(state['paper_text'])} characters
- Available images: {len(state['available_images'])} images
- Completed tasks: {state.get('completed_tasks', [])}
- Analysis iteration: {state.get('analysis_iteration', 0)}
- Already analyzed images: {len(state.get('analyzed_images', {}))} images

**Available Images for Analysis:**
{', '.join(state['available_images'][:10])}  # Show first 10 images

**Available Actions:**
1. **analyze_image**: Analyze a specific image from the paper
   - Use when you need to understand diagrams, charts, tables, or figures
   - Format: analyze_image|<image_path>|<analysis_query>
   - Example: analyze_image|imgs/img_in_image_box_253_178_967_593.jpg|Analyze this architecture diagram and describe the main components

2. **deep_text_analysis**: Perform focused analysis on specific sections
   - Use when you need to extract detailed information from text
   - Format: deep_text_analysis|<focus_area>
   - Example: deep_text_analysis|methodology_details

3. **complete_analysis**: Mark the analysis phase as complete
   - Use when you have sufficient understanding of the paper
   - Format: complete_analysis

**Your Task:**
Decide what to do next to gain deep understanding of this academic paper. Consider:
- What key information is still missing?
- Which images might provide crucial insights?
- Have you understood the core methodology and contributions?

**Decision Format:**
Respond with exactly one action in the specified format. Be specific about what you want to analyze and why.

**Your Decision:**"""
    
    def _parse_and_execute_decision(self, decision_content: str, state: DeepPaperAnalysisState) -> Dict[str, Any]:
        """解析并执行LLM的决策"""
        try:
            # 提取决策行
            lines = decision_content.strip().split('\n')
            decision_line = None
            
            for line in lines:
                line = line.strip()
                if '|' in line and any(action in line for action in ['analyze_image', 'deep_text_analysis', 'complete_analysis']):
                    decision_line = line
                    break
            
            if not decision_line:
                # 如果没有找到格式化的决策，查找关键词
                if 'complete_analysis' in decision_content.lower() or 'complete' in decision_content.lower():
                    decision_line = "complete_analysis"
                else:
                    # 默认进行文本分析
                    decision_line = "deep_text_analysis|general_analysis"
            
            logger.info(f"解析到的决策: {decision_line}")
            
            # 执行决策
            if decision_line.startswith("analyze_image"):
                return self._execute_image_analysis(decision_line, state)
            elif decision_line.startswith("deep_text_analysis"):
                return self._execute_text_analysis(decision_line, state)
            elif decision_line.startswith("complete_analysis") or decision_line == "complete_analysis":
                return {"is_analysis_complete": True, "completed_tasks": ["iterative_analysis_complete"]}
            else:
                logger.warning(f"未识别的决策格式: {decision_line}")
                return {"analysis_errors": [f"未识别的决策格式: {decision_line}"]}
                
        except Exception as e:
            logger.error(f"决策解析和执行失败: {e}")
            return {"analysis_errors": [f"决策执行失败: {str(e)}"]}
    
    def _execute_image_analysis(self, decision_line: str, state: DeepPaperAnalysisState) -> Dict[str, Any]:
        """执行图片分析决策"""
        try:
            parts = decision_line.split('|')
            if len(parts) >= 3:
                image_path = parts[1].strip()
                analysis_query = parts[2].strip()
            else:
                # 如果格式不完整，使用默认查询
                image_path = state['available_images'][0] if state['available_images'] else ""
                analysis_query = "Analyze this image and describe its content in detail"
            
            if not image_path or image_path not in state['available_images']:
                return {"analysis_errors": [f"Invalid image path: {image_path}"]}
            
            logger.info(f"分析图片: {image_path}")
            
            # 调用图片分析工具
            analysis_result = self.image_tool._run(analysis_query, image_path)
            
            # 更新状态
            analyzed_images = state.get("analyzed_images", {}).copy()
            analyzed_images[image_path] = {
                "analysis_query": analysis_query,
                "analysis_result": analysis_result,
                "iteration": state.get("analysis_iteration", 0)
            }
            
            completed_tasks = state.get("completed_tasks", []).copy()
            completed_tasks.append(f"analyzed_image_{len(analyzed_images)}")
            
            return {
                "analyzed_images": analyzed_images,
                "completed_tasks": completed_tasks
            }
            
        except Exception as e:
            logger.error(f"图片分析执行失败: {e}")
            return {"analysis_errors": [f"图片分析失败: {str(e)}"]}
    
    def _execute_text_analysis(self, decision_line: str, state: DeepPaperAnalysisState) -> Dict[str, Any]:
        """执行文本分析决策"""
        try:
            parts = decision_line.split('|')
            focus_area = parts[1].strip() if len(parts) > 1 else "general_analysis"
            
            logger.info(f"执行文本分析: {focus_area}")
            
            # 这里可以根据focus_area进行不同的文本分析
            # 目前简单记录分析任务完成
            completed_tasks = state.get("completed_tasks", []).copy()
            completed_tasks.append(f"text_analysis_{focus_area}")
            
            return {
                "completed_tasks": completed_tasks
            }
            
        except Exception as e:
            logger.error(f"文本分析执行失败: {e}")
            return {"analysis_errors": [f"文本分析失败: {str(e)}"]}
    
    def _should_continue_english_analysis(self, state: DeepPaperAnalysisState) -> str:
        """判断是否继续英文分析"""
        if state.get("is_analysis_complete", False):
            return "extract_contributions"
        
        current_iteration = state.get("analysis_iteration", 0)
        if current_iteration >= self.config.max_analysis_iterations:
            logger.warning("达到最大迭代次数，强制进入贡献提取阶段")
            return "extract_contributions"
        
        return "continue"
    
    def _extract_contributions_node(self, state: DeepPaperAnalysisState) -> Dict[str, Any]:
        """提取主要贡献节点"""
        logger.info("开始提取主要贡献...")
        
        try:
            contribution_tool = self.analysis_tools_dict["analyze_contributions"]
            image_insights = state.get("analyzed_images", {})
            
            result = contribution_tool._run(
                paper_text=state["paper_text"],
                image_insights=image_insights
            )
            
            # 解析结果
            contributions_data = json.loads(result) if isinstance(result, str) else result
            
            logger.info("主要贡献提取完成")
            return {"main_contributions": contributions_data}
            
        except Exception as e:
            logger.error(f"主要贡献提取失败: {e}")
            return {"analysis_errors": [f"贡献提取失败: {str(e)}"]}
    
    def _analyze_methodology_node(self, state: DeepPaperAnalysisState) -> Dict[str, Any]:
        """分析方法论节点"""
        logger.info("开始分析方法论...")
        
        try:
            methodology_tool = self.analysis_tools_dict["analyze_methodology"]
            image_insights = state.get("analyzed_images", {})
            
            result = methodology_tool._run(
                paper_text=state["paper_text"],
                image_insights=image_insights
            )
            
            methodology_data = json.loads(result) if isinstance(result, str) else result
            
            logger.info("方法论分析完成")
            return {"methodology_analysis": methodology_data}
            
        except Exception as e:
            logger.error(f"方法论分析失败: {e}")
            return {"analysis_errors": [f"方法论分析失败: {str(e)}"]}
    
    def _analyze_results_node(self, state: DeepPaperAnalysisState) -> Dict[str, Any]:
        """分析实验结果节点"""
        logger.info("开始分析实验结果...")
        
        try:
            results_tool = self.analysis_tools_dict["analyze_experimental_results"]
            chart_insights = state.get("analyzed_images", {})
            
            result = results_tool._run(
                paper_text=state["paper_text"],
                chart_insights=chart_insights
            )
            
            results_data = json.loads(result) if isinstance(result, str) else result
            
            logger.info("实验结果分析完成")
            return {"experimental_results": results_data}
            
        except Exception as e:
            logger.error(f"实验结果分析失败: {e}")
            return {"analysis_errors": [f"实验结果分析失败: {str(e)}"]}
    
    def _analyze_background_node(self, state: DeepPaperAnalysisState) -> Dict[str, Any]:
        """分析背景节点"""
        logger.info("开始分析研究背景...")
        
        try:
            background_tool = self.analysis_tools_dict["analyze_background"]
            image_insights = state.get("analyzed_images", {})
            
            result = background_tool._run(
                paper_text=state["paper_text"],
                image_insights=image_insights
            )
            
            background_data = json.loads(result) if isinstance(result, str) else result
            
            logger.info("研究背景分析完成")
            return {"background_analysis": background_data}
            
        except Exception as e:
            logger.error(f"研究背景分析失败: {e}")
            return {"analysis_errors": [f"背景分析失败: {str(e)}"]}
    
    def _should_translate(self, state: DeepPaperAnalysisState) -> str:
        """判断是否需要翻译"""
        if self.config.enable_translation:
            return "translate"
        else:
            return "skip_translation"
    
    def _translate_all_sections_node(self, state: DeepPaperAnalysisState) -> Dict[str, Any]:
        """翻译所有章节节点"""
        logger.info("开始翻译所有分析结果...")
        
        translation_results = {}
        
        try:
            # 翻译主要贡献
            if state.get("main_contributions"):
                logger.info("翻译主要贡献...")
                translated = self.translation_tool.translate_contributions(state["main_contributions"])
                translation_results["translated_contributions"] = translated
            
            # 翻译方法论
            if state.get("methodology_analysis"):
                logger.info("翻译方法论...")
                translated = self.translation_tool.translate_methodology(state["methodology_analysis"])
                translation_results["translated_methodology"] = translated
            
            # 翻译实验结果
            if state.get("experimental_results"):
                logger.info("翻译实验结果...")
                translated = self.translation_tool.translate_results(state["experimental_results"])
                translation_results["translated_results"] = translated
            
            # 翻译背景分析
            if state.get("background_analysis"):
                logger.info("翻译研究背景...")
                translated = self.translation_tool.translate_background(state["background_analysis"])
                translation_results["translated_background"] = translated
            
            translation_results["is_translation_complete"] = True
            logger.info("所有章节翻译完成")
            
            return translation_results
            
        except Exception as e:
            logger.error(f"翻译失败: {e}")
            return {
                "analysis_errors": [f"翻译失败: {str(e)}"],
                "is_translation_complete": False
            }
    
    def analyze_paper_folder(self, folder_path: str, thread_id: str = "1") -> Dict[str, Any]:
        """
        分析论文文件夹的主入口
        
        Args:
            folder_path: 论文文件夹路径
            thread_id: 线程ID
            
        Returns:
            Dict: 完整的分析结果状态
        """
        logger.info(f"开始分析论文文件夹: {folder_path}")
        
        # 解析文件夹内容
        folder_data = self._parse_paper_folder(folder_path)
        
        # 创建初始状态
        initial_state: DeepPaperAnalysisState = {
            "base_folder_path": folder_path,
            "paper_text": folder_data["paper_text"],
            "available_images": folder_data["available_images"],
            "image_mappings": folder_data["image_mappings"],
            
            # 分析结果初始化
            "main_contributions": None,
            "background_analysis": None,
            "methodology_analysis": None,
            "experimental_results": None,
            "analyzed_images": None,
            "image_insights": None,
            
            # 翻译结果初始化
            "translated_contributions": None,
            "translated_background": None,
            "translated_methodology": None,
            "translated_results": None,
            
            # 状态跟踪初始化
            "analysis_iteration": 0,
            "completed_tasks": [],
            "is_analysis_complete": False,
            "is_translation_complete": False,
            "analysis_errors": []
        }
        
        # 配置LangGraph
        config = RunnableConfig(
            configurable={"thread_id": thread_id},
            recursion_limit=100
        )
        
        try:
            # 执行分析
            logger.info("开始执行两阶段分析流程...")
            result = self.agent.invoke(initial_state, config)
            
            logger.info("论文分析完成")
            return result
            
        except Exception as e:
            logger.error(f"论文分析失败: {e}")
            return {
                "error": f"分析失败: {str(e)}",
                "initial_state": initial_state
            }
    
    def _parse_paper_folder(self, folder_path: str) -> Dict[str, Any]:
        """解析论文文件夹结构"""
        # 使用专门的解析器
        parser = create_paper_folder_parser(folder_path)
        
        # 验证文件夹完整性
        validation = parser.validate_folder_integrity()
        if not validation["is_valid"]:
            logger.warning(f"文件夹验证失败: {validation['issues']}")
        
        # 解析文件夹
        parse_result = parser.parse_folder()
        
        # 提取需要的信息
        return {
            "paper_text": parse_result["paper_text"],
            "available_images": parse_result["available_images"],
            "image_mappings": parse_result["image_mappings"],
            "latex_formulas": parse_result["latex_formulas"],
            "image_references": parse_result["image_references"],
            "content_sections": parse_result["content_sections"]
        }
    
    def get_config(self) -> DeepPaperAnalysisConfig:
        """获取当前配置"""
        return self.config
    
    def generate_markdown_report(self, analysis_result: Dict[str, Any], output_path: str = None) -> str:
        """
        生成markdown分析报告
        
        Args:
            analysis_result: 分析结果状态
            output_path: 输出文件路径（可选）
            
        Returns:
            str: markdown报告内容
        """
        logger.info("生成markdown分析报告...")
        
        # 创建格式化器
        formatter = create_markdown_formatter(self.config.target_language)
        
        # 生成报告
        report_content = formatter.format_analysis_report(analysis_result)
        
        # 保存文件（如果指定了路径）
        if output_path:
            success = formatter.save_report(report_content, output_path)
            if success:
                logger.info(f"报告已保存到: {output_path}")
            else:
                logger.error("报告保存失败")
        
        return report_content
    
    def analyze_and_generate_report(self, folder_path: str, output_path: str = None, thread_id: str = "1") -> tuple[Dict[str, Any], str]:
        """
        完整的分析和报告生成流程
        
        Args:
            folder_path: 论文文件夹路径
            output_path: 报告输出路径（可选）
            thread_id: 线程ID
            
        Returns:
            tuple: (分析结果, markdown报告内容)
        """
        logger.info(f"开始完整的论文分析和报告生成流程: {folder_path}")
        
        # 执行分析
        analysis_result = self.analyze_paper_folder(folder_path, thread_id)
        
        # 生成报告
        report_content = self.generate_markdown_report(analysis_result, output_path)
        
        logger.info("完整流程执行完成")
        return analysis_result, report_content


# 便捷函数
def create_deep_paper_analysis_agent(
    analysis_model: str = "deepseek.DeepSeek_V3",
    vision_model: str = "ollama.llava",
    translation_model: str = "ollama.Qwen3_30B",
    **kwargs
) -> DeepPaperAnalysisAgent:
    """创建深度论文分析agent的便捷函数"""
    config = DeepPaperAnalysisConfig(
        analysis_model=analysis_model,
        vision_model=vision_model,
        translation_model=translation_model,
        **kwargs
    )
    return DeepPaperAnalysisAgent(config=config)


# 测试代码
if __name__ == "__main__":
    # 测试agent创建
    agent = create_deep_paper_analysis_agent()
    print(f"深度论文分析Agent创建成功")
    print(f"配置: {agent.get_config().__dict__}")