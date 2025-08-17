"""
图片分析工具 - 专门用于论文中的图表、架构图、实验结果等视觉内容分析

支持中文交互和智能路径处理，集成本地VLM进行专业的学术图片分析。
"""

import os
from typing import Any, Dict, Type
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from loguru import logger

from ..vision_utils import VisionUtils
from ..vision_agent import create_academic_vision_agent


class ImageAnalysisToolInput(BaseModel):
    """图片分析工具输入模型"""
    analysis_query: str = Field(
        description="中文分析请求，例如：'分析这个架构图并识别主要组件'"
    )
    image_path: str = Field(
        description="图片相对路径，例如：'imgs/img_in_image_box_253_178_967_593.jpg'"
    )


class ImageAnalysisTool(BaseTool):
    """专业图片分析工具 - 中文交互，专注学术论文图片理解"""
    
    name: str = "analyze_image"
    description: str = "使用视觉语言模型分析学术论文中的图片，包括架构图、实验图表、表格和示例图片"
    args_schema: Type[BaseModel] = ImageAnalysisToolInput
    return_direct: bool = False
    
    # 声明工具属性
    base_folder_path: str = Field(default="", exclude=True)
    vision_model: str = Field(default="ollama.Qwen2_5_VL_7B", exclude=True)
    
    def __init__(self, 
                 base_folder_path: str,
                 vision_model: str = "ollama.Qwen2_5_VL_7B",
                 **kwargs):
        """
        初始化图片分析工具
        
        Args:
            base_folder_path: 论文文件夹基础路径，用于路径补全
            vision_model: 视觉模型名称，默认使用本地Qwen2_5_VL_7B
        """
        super().__init__(**kwargs)
        
        # 使用 object.__setattr__ 来设置属性
        object.__setattr__(self, 'base_folder_path', base_folder_path)
        object.__setattr__(self, 'vision_model', vision_model)
        
        logger.info(f"ImageAnalysisTool initialized with model: {vision_model}")
        logger.info(f"Base folder path: {base_folder_path}")
    
    def _resolve_image_path(self, relative_path: str) -> str:
        """
        智能路径补全：从相对路径解析为绝对路径
        
        Args:
            relative_path: 相对路径，如 "imgs/img_in_image_box_770_409_986_609.jpg"
            
        Returns:
            str: 绝对路径
            
        Raises:
            FileNotFoundError: 如果图片文件不存在
        """
        # 如果已经是绝对路径，直接验证存在性
        if os.path.isabs(relative_path):
            if os.path.exists(relative_path):
                return relative_path
            else:
                raise FileNotFoundError(f"Image file not found: {relative_path}")
        
        # 尝试多种路径补全策略
        path_candidates = [
            # 策略1: 直接拼接基础路径
            os.path.join(self.base_folder_path, relative_path),
            # 策略2: 在imgs子目录中查找
            os.path.join(self.base_folder_path, "imgs", os.path.basename(relative_path)),
            # 策略3: 只使用文件名在基础目录查找
            os.path.join(self.base_folder_path, os.path.basename(relative_path))
        ]
        
        for candidate_path in path_candidates:
            if os.path.exists(candidate_path):
                logger.debug(f"Resolved image path: {relative_path} -> {candidate_path}")
                return candidate_path
        
        # 如果所有策略都失败，提供详细错误信息
        error_msg = f"Image file not found: {relative_path}\nTried paths:\n"
        for path in path_candidates:
            error_msg += f"  - {path}\n"
        raise FileNotFoundError(error_msg)
    
    
    def _run(self, analysis_query: str, image_path: str) -> str:
        """
        执行图片分析
        
        Args:
            analysis_query: 中文分析要求
            image_path: 图片相对路径
            
        Returns:
            str: 中文分析结果
        """
        try:
            # 1. 解析图片路径
            full_image_path = self._resolve_image_path(image_path)
            
            # 2. 验证图片格式
            if not VisionUtils.validate_image_format(full_image_path):
                return f"Error: Unsupported image format for {image_path}"
            
            # 3. 获取图片信息
            image_info = VisionUtils.get_image_info(full_image_path)
            logger.info(f"Analyzing image: {image_info['filename']}, "
                       f"Format: {image_info.get('format', 'unknown')}, "
                       f"Size: {image_info.get('width', 0)}x{image_info.get('height', 0)}")
            
            # 4. 准备中文分析查询（VisionAgent内部会生成专业提示词）
            
            # 5. 创建VisionAgent并进行分析
            logger.info(f"Starting VisionAgent analysis for image: {os.path.basename(full_image_path)}")
            
            # 创建专门的VisionAgent实例
            vision_agent = create_academic_vision_agent(vision_model=self.vision_model)
            
            # 使用VisionAgent进行分析
            analysis_result = vision_agent.analyze_image(
                image_path=full_image_path,
                analysis_query=analysis_query,
                thread_id=f"img_analysis_{os.path.basename(full_image_path)}"
            )
            
            # 6. 处理和验证结果
            if not analysis_result or len(analysis_result.strip()) < 10:
                return f"Warning: VLM analysis returned minimal content for {image_path}"
            
            logger.info(f"Image analysis completed successfully, result length: {len(analysis_result)} characters")
            return analysis_result
            
        except FileNotFoundError as e:
            error_msg = f"Image file error for '{image_path}': {str(e)}"
            logger.error(error_msg)
            return error_msg
            
        except Exception as e:
            error_msg = f"Image analysis failed for '{image_path}': {str(e)}"
            logger.error(error_msg)
            return error_msg
    
    def get_supported_formats(self) -> list:
        """获取支持的图片格式列表"""
        from ..vision_utils import get_supported_formats
        return get_supported_formats()
    
    def validate_image(self, image_path: str) -> Dict[str, Any]:
        """
        验证图片文件
        
        Args:
            image_path: 图片路径（相对或绝对）
            
        Returns:
            Dict: 验证结果，包含is_valid, error_message, image_info等
        """
        try:
            full_path = self._resolve_image_path(image_path)
            
            # 验证格式和大小
            format_valid = VisionUtils.validate_image_format(full_path)
            size_valid = VisionUtils.validate_image_size(full_path)
            
            if format_valid and size_valid:
                image_info = VisionUtils.get_image_info(full_path)
                return {
                    "is_valid": True,
                    "full_path": full_path,
                    "image_info": image_info,
                    "error_message": None
                }
            else:
                return {
                    "is_valid": False,
                    "full_path": full_path,
                    "image_info": None,
                    "error_message": f"Invalid format: {not format_valid}, Invalid size: {not size_valid}"
                }
                
        except Exception as e:
            return {
                "is_valid": False,
                "full_path": None,
                "image_info": None,
                "error_message": str(e)
            }


def create_image_analysis_tool(base_folder_path: str, vision_model: str = "ollama.llava") -> ImageAnalysisTool:
    """
    创建图片分析工具的便捷函数
    
    Args:
        base_folder_path: 论文文件夹基础路径
        vision_model: 视觉模型名称
        
    Returns:
        ImageAnalysisTool: 配置好的图片分析工具实例
    """
    return ImageAnalysisTool(
        base_folder_path=base_folder_path,
        vision_model=vision_model
    )


# 使用示例和测试代码
if __name__ == "__main__":
    # 测试代码 - 使用相对路径
    current_dir = os.path.dirname(__file__)
    project_root = os.path.join(current_dir, '..', '..', '..')
    test_folder_path = os.path.join(project_root, "data/paper_analyze/2502.13508")
    test_image_path = "imgs/img_in_image_box_253_178_967_593.jpg"
    
    try:
        # 创建工具实例
        tool = create_image_analysis_tool(test_folder_path)
        
        # 验证图片
        validation = tool.validate_image(test_image_path)
        print(f"Image validation: {validation}")
        
        if validation["is_valid"]:
            # 测试分析
            result = tool._run(
                analysis_query="分析这个架构图并描述主要组件及其关系",
                image_path=test_image_path
            )
            print(f"Analysis result length: {len(result)}")
            print(f"First 200 chars: {result[:200]}...")
        
    except Exception as e:
        print(f"Test failed: {e}")