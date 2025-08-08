"""
视频处理工具模块 - 支持视频帧提取、验证和处理

提供多种帧采样方式，专门为VL模型分析视频内容设计。
"""

import os
import cv2
import tempfile
import random
from typing import List, Tuple, Optional, Union
from pathlib import Path
from enum import Enum
from loguru import logger


class SamplingMethod(Enum):
    """帧采样方式枚举"""
    SEQUENTIAL = "sequential"      # 顺序均匀采样
    RANDOM = "random"             # 随机采样
    FIRST = "first"               # 只取第一帧
    MIDDLE_RANDOM = "middle_random"  # 中间部分随机采样


# 支持的视频格式
SUPPORTED_VIDEO_FORMATS = {
    '.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm', '.m4v', '.3gp', '.ogv'
}

# 默认帧提取参数
DEFAULT_FRAME_COUNT = 5
MAX_FRAME_COUNT = 20
DEFAULT_FRAME_SIZE = (1024, 768)  # 默认帧尺寸


class VideoInfo:
    """视频信息类"""
    def __init__(self, 
                 filename: str,
                 duration: float,
                 fps: float,
                 frame_count: int,
                 width: int,
                 height: int,
                 format: str,
                 file_size: int):
        self.filename = filename
        self.duration = duration
        self.fps = fps
        self.frame_count = frame_count
        self.width = width
        self.height = height
        self.format = format
        self.file_size = file_size
        self.supported = format.lower() in SUPPORTED_VIDEO_FORMATS


class ExtractedFrame:
    """提取的帧信息类"""
    def __init__(self, 
                 frame_path: str,
                 frame_number: int,
                 timestamp: float,
                 sampling_method: SamplingMethod):
        self.frame_path = frame_path
        self.frame_number = frame_number
        self.timestamp = timestamp
        self.sampling_method = sampling_method


class VideoUtils:
    """视频处理工具类"""
    
    @staticmethod
    def validate_video_format(file_path: Union[str, Path]) -> bool:
        """
        验证视频文件格式是否支持
        
        Args:
            file_path: 视频文件路径
            
        Returns:
            bool: 是否为支持的格式
        """
        try:
            file_path = Path(file_path)
            if not file_path.exists():
                return False
            
            # 检查文件扩展名
            extension = file_path.suffix.lower()
            if extension not in SUPPORTED_VIDEO_FORMATS:
                return False
            
            # 尝试用OpenCV打开视频
            cap = cv2.VideoCapture(str(file_path))
            if not cap.isOpened():
                return False
            
            # 尝试读取第一帧
            ret, _ = cap.read()
            cap.release()
            
            return ret
            
        except Exception as e:
            logger.warning(f"视频格式验证失败: {e}")
            return False
    
    @staticmethod
    def get_video_info(file_path: Union[str, Path]) -> VideoInfo:
        """
        获取视频文件信息
        
        Args:
            file_path: 视频文件路径
            
        Returns:
            VideoInfo: 视频信息对象
        """
        file_path = Path(file_path)
        
        try:
            cap = cv2.VideoCapture(str(file_path))
            if not cap.isOpened():
                raise ValueError("无法打开视频文件")
            
            # 获取基本信息
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            # 计算时长（秒）
            duration = frame_count / fps if fps > 0 else 0
            
            # 获取文件大小
            file_size = file_path.stat().st_size
            
            cap.release()
            
            return VideoInfo(
                filename=file_path.name,
                duration=duration,
                fps=fps,
                frame_count=frame_count,
                width=width,
                height=height,
                format=file_path.suffix.lower(),
                file_size=file_size
            )
            
        except Exception as e:
            logger.error(f"获取视频信息失败: {e}")
            # 返回基本信息，标记为不支持
            return VideoInfo(
                filename=file_path.name,
                duration=0,
                fps=0,
                frame_count=0,
                width=0,
                height=0,
                format=file_path.suffix.lower(),
                file_size=file_path.stat().st_size if file_path.exists() else 0
            )
    
    @staticmethod
    def calculate_frame_positions(video_info: VideoInfo, 
                                frame_count: int,
                                sampling_method: SamplingMethod) -> List[int]:
        """
        根据采样方式计算需要提取的帧位置
        
        Args:
            video_info: 视频信息
            frame_count: 需要提取的帧数
            sampling_method: 采样方式
            
        Returns:
            List[int]: 帧位置列表
        """
        total_frames = video_info.frame_count
        if total_frames <= 0:
            return []
        
        # 限制帧数
        actual_frame_count = min(frame_count, MAX_FRAME_COUNT, total_frames)
        
        if sampling_method == SamplingMethod.FIRST:
            # 只取第一帧
            return [0]
        
        elif sampling_method == SamplingMethod.SEQUENTIAL:
            # 顺序均匀采样
            if actual_frame_count >= total_frames:
                return list(range(total_frames))
            
            step = total_frames // actual_frame_count
            positions = [i * step for i in range(actual_frame_count)]
            
            # 确保最后一帧也被包含（如果可能）
            if positions[-1] < total_frames - 1:
                positions[-1] = total_frames - 1
            
            return positions
        
        elif sampling_method == SamplingMethod.RANDOM:
            # 随机采样
            positions = sorted(random.sample(range(total_frames), actual_frame_count))
            return positions
        
        elif sampling_method == SamplingMethod.MIDDLE_RANDOM:
            # 中间部分随机采样（跳过前后各25%）
            start_frame = total_frames // 4
            end_frame = total_frames * 3 // 4
            middle_frames = end_frame - start_frame
            
            if middle_frames <= actual_frame_count:
                # 中间部分帧数不足，返回所有中间帧
                return list(range(start_frame, end_frame))
            
            # 从中间部分随机选择
            positions = sorted(random.sample(range(start_frame, end_frame), actual_frame_count))
            return positions
        
        else:
            # 默认使用顺序采样
            return VideoUtils.calculate_frame_positions(
                video_info, frame_count, SamplingMethod.SEQUENTIAL
            )
    
    @staticmethod
    def extract_frames(video_path: Union[str, Path],
                      frame_count: int = DEFAULT_FRAME_COUNT,
                      sampling_method: SamplingMethod = SamplingMethod.SEQUENTIAL,
                      output_dir: Optional[str] = None,
                      frame_size: Optional[Tuple[int, int]] = None) -> List[ExtractedFrame]:
        """
        从视频中提取帧
        
        Args:
            video_path: 视频文件路径
            frame_count: 提取帧数
            sampling_method: 采样方式
            output_dir: 输出目录（如果为None则使用临时目录）
            frame_size: 帧尺寸 (width, height)
            
        Returns:
            List[ExtractedFrame]: 提取的帧列表
        """
        video_path = Path(video_path)
        
        # 验证视频文件
        if not VideoUtils.validate_video_format(video_path):
            raise ValueError(f"不支持的视频格式或文件不存在: {video_path}")
        
        # 获取视频信息
        video_info = VideoUtils.get_video_info(video_path)
        logger.info(f"开始提取视频帧: {video_info.filename}, "
                   f"时长: {video_info.duration:.1f}s, "
                   f"帧数: {video_info.frame_count}")
        
        # 计算帧位置
        frame_positions = VideoUtils.calculate_frame_positions(
            video_info, frame_count, sampling_method
        )
        
        if not frame_positions:
            raise ValueError("无法计算帧位置")
        
        # 设置输出目录
        if output_dir is None:
            output_dir = tempfile.mkdtemp(prefix="video_frames_")
        else:
            os.makedirs(output_dir, exist_ok=True)
        
        extracted_frames = []
        
        try:
            cap = cv2.VideoCapture(str(video_path))
            if not cap.isOpened():
                raise ValueError(f"无法打开视频文件: {video_path}")
            
            for i, frame_pos in enumerate(frame_positions):
                # 定位到指定帧
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_pos)
                ret, frame = cap.read()
                
                if not ret:
                    logger.warning(f"无法读取帧 {frame_pos}, 跳过")
                    continue
                
                # 调整帧尺寸
                if frame_size:
                    frame = cv2.resize(frame, frame_size, interpolation=cv2.INTER_AREA)
                elif frame.shape[1] > DEFAULT_FRAME_SIZE[0] or frame.shape[0] > DEFAULT_FRAME_SIZE[1]:
                    # 如果帧过大，调整到默认尺寸
                    frame = cv2.resize(frame, DEFAULT_FRAME_SIZE, interpolation=cv2.INTER_AREA)
                
                # 保存帧
                timestamp = frame_pos / video_info.fps if video_info.fps > 0 else 0
                frame_filename = f"frame_{i:03d}_{frame_pos:06d}_{timestamp:.2f}s.jpg"
                frame_path = os.path.join(output_dir, frame_filename)
                
                success = cv2.imwrite(frame_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
                if success:
                    extracted_frame = ExtractedFrame(
                        frame_path=frame_path,
                        frame_number=frame_pos,
                        timestamp=timestamp,
                        sampling_method=sampling_method
                    )
                    extracted_frames.append(extracted_frame)
                    logger.debug(f"提取帧成功: {frame_filename}")
                else:
                    logger.warning(f"保存帧失败: {frame_path}")
            
            cap.release()
            
        except Exception as e:
            logger.error(f"帧提取过程中发生错误: {e}")
            raise
        
        logger.info(f"帧提取完成: {len(extracted_frames)}/{len(frame_positions)} 帧成功提取")
        return extracted_frames
    
    @staticmethod
    def cleanup_frames(extracted_frames: List[ExtractedFrame]) -> None:
        """
        清理提取的临时帧文件
        
        Args:
            extracted_frames: 提取的帧列表
        """
        for frame in extracted_frames:
            try:
                if os.path.exists(frame.frame_path):
                    os.remove(frame.frame_path)
                    logger.debug(f"清理临时帧文件: {frame.frame_path}")
            except Exception as e:
                logger.warning(f"清理帧文件失败 {frame.frame_path}: {e}")
        
        # 清理空的临时目录
        if extracted_frames:
            temp_dir = os.path.dirname(extracted_frames[0].frame_path)
            try:
                if temp_dir.startswith(tempfile.gettempdir()) and os.path.exists(temp_dir):
                    if not os.listdir(temp_dir):  # 目录为空
                        os.rmdir(temp_dir)
                        logger.debug(f"清理临时目录: {temp_dir}")
            except Exception as e:
                logger.warning(f"清理临时目录失败 {temp_dir}: {e}")
    
    @staticmethod
    def validate_extracted_frames(extracted_frames: List[ExtractedFrame]) -> List[ExtractedFrame]:
        """
        验证提取的帧是否有效
        
        Args:
            extracted_frames: 提取的帧列表
            
        Returns:
            List[ExtractedFrame]: 有效的帧列表
        """
        valid_frames = []
        
        for frame in extracted_frames:
            try:
                if os.path.exists(frame.frame_path):
                    # 尝试用OpenCV读取图片
                    img = cv2.imread(frame.frame_path)
                    if img is not None and img.size > 0:
                        valid_frames.append(frame)
                    else:
                        logger.warning(f"帧文件损坏: {frame.frame_path}")
                else:
                    logger.warning(f"帧文件不存在: {frame.frame_path}")
            except Exception as e:
                logger.warning(f"帧验证失败 {frame.frame_path}: {e}")
        
        return valid_frames


# 便捷函数
def extract_video_frames(video_path: Union[str, Path],
                        frame_count: int = DEFAULT_FRAME_COUNT,
                        sampling_method: str = "sequential") -> List[ExtractedFrame]:
    """
    便捷函数：从视频中提取帧
    
    Args:
        video_path: 视频文件路径
        frame_count: 提取帧数
        sampling_method: 采样方式字符串
        
    Returns:
        List[ExtractedFrame]: 提取的帧列表
    """
    # 转换采样方式
    method_map = {
        "sequential": SamplingMethod.SEQUENTIAL,
        "random": SamplingMethod.RANDOM,
        "first": SamplingMethod.FIRST,
        "middle_random": SamplingMethod.MIDDLE_RANDOM
    }
    
    method = method_map.get(sampling_method.lower(), SamplingMethod.SEQUENTIAL)
    
    return VideoUtils.extract_frames(
        video_path=video_path,
        frame_count=frame_count,
        sampling_method=method
    )


def get_supported_video_formats() -> List[str]:
    """获取支持的视频格式列表"""
    return list(SUPPORTED_VIDEO_FORMATS)


if __name__ == "__main__":
    # 测试代码
    print("支持的视频格式:", get_supported_video_formats())
    print("默认帧数:", DEFAULT_FRAME_COUNT)
    print("最大帧数:", MAX_FRAME_COUNT)
    print("默认帧尺寸:", DEFAULT_FRAME_SIZE)
    
    # 可以添加实际视频文件测试
    # test_video = "test_video.mp4"
    # if os.path.exists(test_video):
    #     info = VideoUtils.get_video_info(test_video)
    #     print(f"视频信息: {info.filename}, {info.duration}s, {info.frame_count}帧")