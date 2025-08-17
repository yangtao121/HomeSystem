"""
视频分析工具 - 专门用于分析视频内容

通过提取视频帧并使用本地VL模型进行分析，支持多种帧采样策略。
集成现有的VisionAgent架构，提供专业的视频内容理解。
"""

import os
import tempfile
from typing import Any, Dict, Type, List, Optional, Union
from pathlib import Path
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from loguru import logger

from ..video_utils import VideoUtils, SamplingMethod, ExtractedFrame, DEFAULT_FRAME_COUNT
from ..vision_agent import create_academic_vision_agent


class VideoAnalysisToolInput(BaseModel):
    """视频分析工具输入模型"""
    analysis_query: str = Field(
        description="中文分析请求，例如：'分析这个视频的主要内容和关键场景'"
    )
    video_path: str = Field(
        description="视频文件路径，支持相对路径和绝对路径"
    )
    frame_count: int = Field(
        default=DEFAULT_FRAME_COUNT,
        description=f"提取的帧数，默认{DEFAULT_FRAME_COUNT}，最大20"
    )
    sampling_method: str = Field(
        default="sequential",
        description="帧采样方式：sequential(顺序), random(随机), first(首帧), middle_random(中间随机)"
    )


class VideoAnalysisTool(BaseTool):
    """专业视频分析工具 - 中文交互，专注视频内容理解"""
    
    name: str = "analyze_video"
    description: str = "使用视觉语言模型分析视频内容，通过提取关键帧进行视频理解和内容描述"
    args_schema: Type[BaseModel] = VideoAnalysisToolInput
    return_direct: bool = False
    
    # 声明工具属性
    base_folder_path: str = Field(default="", exclude=True)
    vision_model: str = Field(default="ollama.Qwen2_5_VL_7B", exclude=True)
    
    def __init__(self, 
                 base_folder_path: str = "",
                 vision_model: str = "ollama.Qwen2_5_VL_7B",
                 **kwargs):
        """
        初始化视频分析工具
        
        Args:
            base_folder_path: 视频文件夹基础路径，用于路径补全
            vision_model: 视觉模型名称，默认使用本地Qwen2_5_VL_7B
        """
        super().__init__(**kwargs)
        
        # 使用 object.__setattr__ 来设置属性（Pydantic要求）
        object.__setattr__(self, 'base_folder_path', base_folder_path)
        object.__setattr__(self, 'vision_model', vision_model)
        
        logger.info(f"VideoAnalysisTool initialized with model: {vision_model}")
        logger.info(f"Base folder path: {base_folder_path}")
    
    def _resolve_video_path(self, relative_path: str) -> str:
        """
        智能路径补全：从相对路径解析为绝对路径
        
        Args:
            relative_path: 相对路径，如 "videos/sample.mp4"
            
        Returns:
            str: 绝对路径
            
        Raises:
            FileNotFoundError: 如果视频文件不存在
        """
        # 如果已经是绝对路径，直接验证存在性
        if os.path.isabs(relative_path):
            if os.path.exists(relative_path):
                return relative_path
            else:
                raise FileNotFoundError(f"Video file not found: {relative_path}")
        
        # 尝试多种路径补全策略
        path_candidates = [
            # 策略1: 直接拼接基础路径
            os.path.join(self.base_folder_path, relative_path),
            # 策略2: 在videos子目录中查找
            os.path.join(self.base_folder_path, "videos", os.path.basename(relative_path)),
            # 策略3: 只使用文件名在基础目录查找
            os.path.join(self.base_folder_path, os.path.basename(relative_path))
        ]
        
        # 如果有基础路径，添加更多候选路径
        if self.base_folder_path:
            path_candidates.extend([
                # 在基础路径的各种子目录中查找
                os.path.join(self.base_folder_path, "media", os.path.basename(relative_path)),
                os.path.join(self.base_folder_path, "files", os.path.basename(relative_path))
            ])
        
        for candidate_path in path_candidates:
            if os.path.exists(candidate_path):
                logger.debug(f"Resolved video path: {relative_path} -> {candidate_path}")
                return candidate_path
        
        # 如果所有策略都失败，提供详细错误信息
        error_msg = f"Video file not found: {relative_path}\nTried paths:\n"
        for path in path_candidates:
            error_msg += f"  - {path}\n"
        raise FileNotFoundError(error_msg)
    
    def _parse_sampling_method(self, sampling_method: str) -> SamplingMethod:
        """
        解析采样方法字符串为枚举值
        
        Args:
            sampling_method: 采样方法字符串
            
        Returns:
            SamplingMethod: 采样方法枚举
        """
        method_map = {
            "sequential": SamplingMethod.SEQUENTIAL,
            "random": SamplingMethod.RANDOM,
            "first": SamplingMethod.FIRST,
            "middle_random": SamplingMethod.MIDDLE_RANDOM
        }
        
        method_str = sampling_method.lower().strip()
        if method_str in method_map:
            return method_map[method_str]
        else:
            logger.warning(f"未知的采样方法: {sampling_method}, 使用默认的sequential")
            return SamplingMethod.SEQUENTIAL
    
    
    def _analyze_frame_batch(self, extracted_frames: List[ExtractedFrame], analysis_query: str) -> Dict[str, str]:
        """
        批量分析视频帧
        
        Args:
            extracted_frames: 提取的帧列表
            analysis_query: 分析查询
            
        Returns:
            Dict[str, str]: 帧路径 -> 分析结果的映射
        """
        logger.info(f"开始批量分析 {len(extracted_frames)} 个视频帧")
        
        # 创建VisionAgent实例
        vision_agent = create_academic_vision_agent(vision_model=self.vision_model)
        
        frame_analyses = {}
        
        for i, frame in enumerate(extracted_frames):
            try:
                # 为每个帧生成特定的分析提示
                frame_prompt = f"这是视频的第{i+1}帧（时间戳: {frame.timestamp:.2f}秒）。{analysis_query}"
                
                # 使用VisionAgent分析单帧
                frame_analysis = vision_agent.analyze_image(
                    image_path=frame.frame_path,
                    analysis_query=frame_prompt,
                    thread_id=f"video_frame_{i}_{frame.frame_number}"
                )
                
                frame_analyses[frame.frame_path] = frame_analysis
                logger.debug(f"帧分析完成 {i+1}/{len(extracted_frames)}: {os.path.basename(frame.frame_path)}")
                
            except Exception as e:
                error_msg = f"帧分析失败: {str(e)}"
                logger.error(f"Frame analysis failed for {frame.frame_path}: {e}")
                frame_analyses[frame.frame_path] = error_msg
        
        logger.info(f"批量帧分析完成: {len(frame_analyses)} 个结果")
        return frame_analyses
    
    def _summarize_frame_analyses(self, frame_analyses: Dict[str, str], 
                                 extracted_frames: List[ExtractedFrame],
                                 original_query: str) -> str:
        """
        汇总多帧分析结果为综合视频分析
        
        Args:
            frame_analyses: 帧分析结果映射
            extracted_frames: 提取的帧列表
            original_query: 原始查询
            
        Returns:
            str: 综合视频分析结果
        """
        if not frame_analyses:
            return "无法分析视频内容：没有成功分析的帧。"
        
        # 收集所有有效的分析结果
        valid_analyses = []
        for frame in extracted_frames:
            analysis = frame_analyses.get(frame.frame_path, "")
            if analysis and not analysis.startswith("帧分析失败"):
                valid_analyses.append({
                    'timestamp': frame.timestamp,
                    'frame_number': frame.frame_number,
                    'analysis': analysis
                })
        
        if not valid_analyses:
            return "视频分析失败：所有帧的分析都不成功。"
        
        # 构建综合分析结果
        summary_parts = []
        
        # 1. 基本信息
        total_frames = len(extracted_frames)
        successful_frames = len(valid_analyses)
        duration_range = f"{valid_analyses[0]['timestamp']:.1f}-{valid_analyses[-1]['timestamp']:.1f}秒"
        
        summary_parts.append(f"# 视频分析报告\n")
        summary_parts.append(f"**分析概况**: 成功分析了 {successful_frames}/{total_frames} 帧，时间范围: {duration_range}\n")
        
        # 2. 用户查询回应
        summary_parts.append(f"**分析目标**: {original_query}\n")
        
        # 3. 按时间顺序展示帧分析
        summary_parts.append("## 关键帧分析\n")
        
        for i, analysis_data in enumerate(valid_analyses):
            timestamp = analysis_data['timestamp']
            analysis = analysis_data['analysis']
            
            summary_parts.append(f"### 帧 {i+1} ({timestamp:.2f}秒)")
            summary_parts.append(f"{analysis}\n")
        
        # 4. 如果有多帧，尝试提供综合总结
        if len(valid_analyses) > 1:
            summary_parts.append("## 综合分析\n")
            
            # 简单的内容汇总逻辑
            all_content = " ".join([analysis['analysis'] for analysis in valid_analyses])
            
            # 基于内容长度提供不同级别的总结
            if len(all_content) > 1000:
                summary_parts.append("基于多个关键帧的分析，这个视频展现了丰富的内容。"
                                   "各个时间点的场景和内容在上述帧分析中有详细描述。"
                                   "建议查看各个关键帧的具体分析以获得完整理解。")
            else:
                summary_parts.append("通过对多个关键帧的分析，可以看出视频内容在时间轴上的发展和变化。"
                                   "每个时间点都有其独特的特征和重点内容。")
        
        return "\n".join(summary_parts)
    
    def _run(self, 
             analysis_query: str, 
             video_path: str,
             frame_count: int = DEFAULT_FRAME_COUNT,
             sampling_method: str = "sequential") -> str:
        """
        执行视频分析
        
        Args:
            analysis_query: 中文分析要求
            video_path: 视频文件路径
            frame_count: 提取帧数
            sampling_method: 采样方法
            
        Returns:
            str: 中文分析结果
        """
        extracted_frames = []
        
        try:
            # 1. 解析视频路径
            full_video_path = self._resolve_video_path(video_path)
            
            # 2. 验证视频格式
            if not VideoUtils.validate_video_format(full_video_path):
                return f"Error: 不支持的视频格式或文件损坏: {video_path}"
            
            # 3. 获取视频信息
            video_info = VideoUtils.get_video_info(full_video_path)
            logger.info(f"开始分析视频: {video_info.filename}, "
                       f"时长: {video_info.duration:.1f}s, "
                       f"帧数: {video_info.frame_count}, "
                       f"分辨率: {video_info.width}x{video_info.height}")
            
            # 4. 解析采样方法
            sampling_enum = self._parse_sampling_method(sampling_method)
            
            # 5. 提取视频帧
            logger.info(f"开始提取视频帧，方法: {sampling_method}, 帧数: {frame_count}")
            extracted_frames = VideoUtils.extract_frames(
                video_path=full_video_path,
                frame_count=frame_count,
                sampling_method=sampling_enum
            )
            
            if not extracted_frames:
                return f"Error: 无法从视频中提取帧: {video_path}"
            
            # 6. 验证提取的帧
            valid_frames = VideoUtils.validate_extracted_frames(extracted_frames)
            if not valid_frames:
                return f"Error: 提取的帧文件无效: {video_path}"
            
            logger.info(f"成功提取并验证 {len(valid_frames)}/{len(extracted_frames)} 个有效帧")
            
            # 7. 批量分析帧
            frame_analyses = self._analyze_frame_batch(valid_frames, analysis_query)
            
            # 8. 汇总分析结果
            final_analysis = self._summarize_frame_analyses(
                frame_analyses, valid_frames, analysis_query
            )
            
            # 9. 验证结果
            if not final_analysis or len(final_analysis.strip()) < 50:
                return f"Warning: VLM analysis returned minimal content for {video_path}"
            
            logger.info(f"视频分析完成，结果长度: {len(final_analysis)} 字符")
            return final_analysis
            
        except FileNotFoundError as e:
            error_msg = f"视频文件错误 '{video_path}': {str(e)}"
            logger.error(error_msg)
            return error_msg
            
        except Exception as e:
            error_msg = f"视频分析失败 '{video_path}': {str(e)}"
            logger.error(error_msg)
            return error_msg
            
        finally:
            # 10. 清理临时帧文件
            if extracted_frames:
                try:
                    VideoUtils.cleanup_frames(extracted_frames)
                    logger.debug("临时帧文件清理完成")
                except Exception as e:
                    logger.warning(f"清理临时文件时出错: {e}")
    
    def get_supported_formats(self) -> List[str]:
        """获取支持的视频格式列表"""
        from ..video_utils import get_supported_video_formats
        return get_supported_video_formats()
    
    def validate_video(self, video_path: str) -> Dict[str, Any]:
        """
        验证视频文件
        
        Args:
            video_path: 视频路径（相对或绝对）
            
        Returns:
            Dict: 验证结果，包含is_valid, error_message, video_info等
        """
        try:
            full_path = self._resolve_video_path(video_path)
            
            # 验证格式
            format_valid = VideoUtils.validate_video_format(full_path)
            
            if format_valid:
                video_info = VideoUtils.get_video_info(full_path)
                return {
                    "is_valid": True,
                    "full_path": full_path,
                    "video_info": {
                        "filename": video_info.filename,
                        "duration": video_info.duration,
                        "fps": video_info.fps,
                        "frame_count": video_info.frame_count,
                        "resolution": f"{video_info.width}x{video_info.height}",
                        "format": video_info.format,
                        "file_size_mb": round(video_info.file_size / (1024 * 1024), 2)
                    },
                    "error_message": None
                }
            else:
                return {
                    "is_valid": False,
                    "full_path": full_path,
                    "video_info": None,
                    "error_message": "视频格式不支持或文件损坏"
                }
                
        except Exception as e:
            return {
                "is_valid": False,
                "full_path": None,
                "video_info": None,
                "error_message": str(e)
            }


def create_video_analysis_tool(base_folder_path: str = "", 
                              vision_model: str = "ollama.Qwen2_5_VL_7B") -> VideoAnalysisTool:
    """
    创建视频分析工具的便捷函数
    
    Args:
        base_folder_path: 视频文件夹基础路径
        vision_model: 视觉模型名称
        
    Returns:
        VideoAnalysisTool: 配置好的视频分析工具实例
    """
    return VideoAnalysisTool(
        base_folder_path=base_folder_path,
        vision_model=vision_model
    )


# 使用示例和测试代码
if __name__ == "__main__":
    # 测试代码
    current_dir = os.path.dirname(__file__)
    project_root = os.path.join(current_dir, '..', '..', '..')
    
    # 假设有测试视频文件
    test_video_path = "test_video.mp4"  # 需要实际的视频文件
    
    try:
        # 创建工具实例
        tool = create_video_analysis_tool()
        
        # 验证视频（如果存在）
        if os.path.exists(test_video_path):
            validation = tool.validate_video(test_video_path)
            print(f"Video validation: {validation}")
            
            if validation["is_valid"]:
                # 测试分析
                result = tool._run(
                    analysis_query="分析这个视频的主要内容，描述关键场景和活动",
                    video_path=test_video_path,
                    frame_count=3,
                    sampling_method="sequential"
                )
                print(f"Analysis result length: {len(result)}")
                print(f"First 300 chars: {result[:300]}...")
        else:
            print("测试视频文件不存在，跳过实际分析测试")
            print("支持的视频格式:", tool.get_supported_formats())
        
    except Exception as e:
        print(f"Test failed: {e}")