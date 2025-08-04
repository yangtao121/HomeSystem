"""
专门的视觉分析代理 - 基于ChatAgent优化，专注学术图片分析

继承ChatAgent的架构但移除工具集成，专门用于图片分析任务。
支持多模态输入，针对学术论文图片分析进行优化。
"""

from typing import Optional, Dict, Any, Union
from pathlib import Path
from loguru import logger

from .chat_agent import ChatAgent, ChatAgentConfig
from .llm_factory import validate_vision_input


class VisionAgentConfig(ChatAgentConfig):
    """视觉分析代理配置类"""
    
    def __init__(self, 
                 vision_model: str = "ollama.llava",
                 analysis_language: str = "en",
                 memory_enabled: bool = False,  # 视觉分析通常不需要记忆
                 custom_settings: Optional[Dict[str, Any]] = None):
        
        # 专门的学术图片分析系统提示词
        system_message = self._create_academic_vision_prompt(analysis_language)
        
        super().__init__(
            model_name=vision_model,
            system_message=system_message,
            memory_enabled=memory_enabled,
            conversation_context_limit=10,  # 视觉分析不需要长上下文
            custom_settings=custom_settings or {}
        )
        
        self.vision_model = vision_model
        self.analysis_language = analysis_language
        
        # 验证模型支持视觉输入
        try:
            validate_vision_input(vision_model)
            logger.info(f"Vision model validated: {vision_model}")
        except Exception as e:
            logger.error(f"Vision model validation failed: {e}")
            raise
    
    def _create_academic_vision_prompt(self, language: str) -> str:
        """创建专业的学术图片分析系统提示词"""
        if language.lower() == "zh":
            return """你是一个专业的学术图片分析专家，专门分析计算机科学和机器学习领域的论文图表。

你的任务是分析学术论文中的图片，包括：
- 架构图：识别组件、连接关系和数据流
- 实验图表：提取数据趋势、性能指标和对比结果
- 表格：提取具体数值和比较信息
- 示例图：描述具体内容和关键特征

请提供准确、详细的中文分析，专注于技术精度和学术严谨性。"""
        else:
            return """You are a professional academic image analysis expert specializing in computer science and machine learning research papers.

Your task is to analyze images from academic papers, including:
- Architecture diagrams: Identify components, connections, and data flow
- Experimental charts: Extract data trends, performance metrics, and comparison results  
- Tables: Extract specific values and comparison information
- Example figures: Describe specific content and key features

Please provide accurate, detailed analysis in professional English, focusing on technical precision and academic rigor."""


class VisionAgent(ChatAgent):
    """专门的视觉分析代理
    
    基于ChatAgent但专门优化用于学术图片分析：
    - 移除MCP和工具集成
    - 专门配置视觉模型
    - 优化的学术分析提示词
    - 支持多模态输入
    """
    
    def __init__(self, 
                 config: Optional[VisionAgentConfig] = None,
                 config_path: Optional[str] = None):
        
        # 加载或创建配置
        if config_path:
            # 从文件加载配置，但转换为VisionAgentConfig
            base_config = ChatAgentConfig.load_from_file(config_path)
            vision_config = VisionAgentConfig(
                vision_model=base_config.model_name,
                analysis_language="en",
                memory_enabled=base_config.memory_enabled,
                custom_settings=base_config.custom_settings
            )
            self.config = vision_config
        elif config:
            self.config = config
        else:
            self.config = VisionAgentConfig()
        
        # 明确禁用MCP功能，专注视觉分析
        super().__init__(
            config=self.config, 
            enable_mcp=False,  # 不需要工具集成
            mcp_config_path=None
        )
        
        logger.info(f"VisionAgent initialized with model: {self.config.vision_model}")
        logger.info(f"Analysis language: {self.config.analysis_language}")
    
    def analyze_image(self, 
                     image_path: Union[str, Path], 
                     analysis_query: str = "",
                     thread_id: str = "vision_analysis") -> str:
        """
        分析单张图片
        
        Args:
            image_path: 图片文件路径
            analysis_query: 分析要求（可选）
            thread_id: 线程ID
            
        Returns:
            str: 分析结果
        """
        logger.info(f"Starting image analysis: {Path(image_path).name}")
        
        try:
            # 构建分析提示词
            if analysis_query.strip():
                prompt_text = f"Analyze this image with focus on: {analysis_query}"
            else:
                prompt_text = "Analyze this image in detail, focusing on technical content and academic significance."
            
            # 使用BaseGraph的run_with_image方法
            result = self.run_with_image(
                image_path=image_path,
                text=prompt_text,
                model_name=None,  # 使用当前配置的模型
                thread_id=thread_id
            )
            
            logger.info(f"Image analysis completed, result length: {len(result)} characters")
            return result
            
        except Exception as e:
            error_msg = f"Image analysis failed for '{image_path}': {str(e)}"
            logger.error(error_msg)
            return error_msg
    
    def analyze_image_with_context(self, 
                                 image_path: Union[str, Path],
                                 paper_context: str,
                                 specific_query: str = "",
                                 thread_id: str = "vision_context_analysis") -> str:
        """
        结合论文上下文分析图片
        
        Args:
            image_path: 图片文件路径
            paper_context: 论文相关上下文信息
            specific_query: 具体分析要求
            thread_id: 线程ID
            
        Returns:
            str: 分析结果
        """
        logger.info(f"Starting contextual image analysis: {Path(image_path).name}")
        
        # 构建包含上下文的提示词
        context_prompt = f"""
Paper Context: {paper_context}

{specific_query if specific_query else 'Analyze this image in detail considering the paper context.'}

Please provide a comprehensive analysis focusing on how this image relates to the research described in the context.
"""
        
        return self.analyze_image(image_path, context_prompt, thread_id)
    
    def batch_analyze_images(self, 
                           image_paths: list,
                           common_query: str = "",
                           thread_id: str = "batch_vision_analysis") -> Dict[str, str]:
        """
        批量分析多张图片
        
        Args:
            image_paths: 图片路径列表
            common_query: 通用分析要求
            thread_id: 线程ID
            
        Returns:
            Dict[str, str]: 图片路径 -> 分析结果的映射
        """
        logger.info(f"Starting batch image analysis for {len(image_paths)} images")
        
        results = {}
        for i, image_path in enumerate(image_paths):
            try:
                # 为每个图片使用独立的线程ID
                image_thread_id = f"{thread_id}_{i}"
                result = self.analyze_image(image_path, common_query, image_thread_id)
                results[str(image_path)] = result
                
                logger.debug(f"Completed analysis {i+1}/{len(image_paths)}: {Path(image_path).name}")
                
            except Exception as e:
                logger.error(f"Failed to analyze image {image_path}: {e}")
                results[str(image_path)] = f"Analysis failed: {str(e)}"
        
        logger.info(f"Batch analysis completed: {len(results)} results")
        return results
    
    def get_vision_config(self) -> VisionAgentConfig:
        """获取视觉分析配置"""
        return self.config
    
    def update_vision_config(self, **kwargs) -> None:
        """更新视觉分析配置"""
        vision_specific_keys = ['vision_model', 'analysis_language']
        
        # 处理视觉专用配置
        for key in vision_specific_keys:
            if key in kwargs:
                setattr(self.config, key, kwargs[key])
                logger.info(f"Vision config updated: {key} = {kwargs[key]}")
        
        # 如果修改了vision_model，需要验证和重新创建LLM
        if 'vision_model' in kwargs:
            validate_vision_input(kwargs['vision_model'])
            kwargs['model_name'] = kwargs['vision_model']  # 同步到基类
        
        # 调用基类的更新方法
        super().update_config(**kwargs)
    
    def get_analysis_stats(self) -> Dict[str, Any]:
        """获取分析统计信息"""
        base_stats = self.get_conversation_stats()
        base_stats.update({
            'agent_type': 'VisionAgent',
            'vision_model': self.config.vision_model,
            'analysis_language': self.config.analysis_language,
            'mcp_enabled': False,  # 明确标记不支持MCP
            'specialized_for': 'academic_image_analysis'
        })
        return base_stats


# 便捷函数
def create_vision_agent(vision_model: str = "ollama.llava", 
                       analysis_language: str = "en",
                       **kwargs) -> VisionAgent:
    """
    创建视觉分析代理的便捷函数
    
    Args:
        vision_model: 视觉模型名称
        analysis_language: 分析语言（en/zh）
        **kwargs: 其他配置参数
        
    Returns:
        VisionAgent: 配置好的视觉分析代理实例
    """
    config = VisionAgentConfig(
        vision_model=vision_model,
        analysis_language=analysis_language,
        **kwargs
    )
    return VisionAgent(config=config)


def create_academic_vision_agent(vision_model: str = "ollama.llava") -> VisionAgent:
    """
    创建专门用于学术论文分析的视觉代理
    
    Args:
        vision_model: 视觉模型名称
        
    Returns:
        VisionAgent: 学术优化的视觉分析代理
    """
    return create_vision_agent(
        vision_model=vision_model,
        analysis_language="en",  # 学术分析使用英文
        memory_enabled=False,    # 不需要记忆
    )


# 测试代码
if __name__ == "__main__":
    # 测试VisionAgent创建
    try:
        agent = create_academic_vision_agent()
        print(f"VisionAgent created successfully")
        print(f"Config: {agent.get_analysis_stats()}")
        
        # 测试图片分析（如果有测试图片） - 使用相对路径
        current_dir = os.path.dirname(__file__)
        project_root = os.path.join(current_dir, '..', '..')
        test_image = os.path.join(project_root, "data/paper_analyze/2502.13508/imgs/img_in_image_box_253_178_967_593.jpg")
        if Path(test_image).exists():
            result = agent.analyze_image(test_image, "Analyze this architecture diagram")
            print(f"Analysis result length: {len(result)}")
            print(f"First 200 chars: {result[:200]}...")
        
    except Exception as e:
        print(f"Test failed: {e}")