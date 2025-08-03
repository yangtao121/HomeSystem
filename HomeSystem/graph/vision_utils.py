"""
视觉处理工具模块 - 支持图片预处理、编码和验证
"""

import base64
import io
import os
from pathlib import Path
from typing import Union, Tuple, List, Optional
from PIL import Image, ImageOps
from loguru import logger


# 支持的图片格式
SUPPORTED_IMAGE_FORMATS = {
    'JPEG', 'JPG', 'PNG', 'WebP', 'BMP', 'GIF', 'TIFF'
}

# 最大图片尺寸（像素）
MAX_IMAGE_SIZE = (2048, 2048)

# 最大文件大小（字节，20MB）
MAX_FILE_SIZE = 20 * 1024 * 1024


class VisionUtils:
    """视觉处理工具类"""
    
    @staticmethod
    def validate_image_format(file_path: Union[str, Path]) -> bool:
        """
        验证图片格式是否支持
        
        Args:
            file_path: 图片文件路径
            
        Returns:
            bool: 是否为支持的格式
        """
        try:
            with Image.open(file_path) as img:
                return img.format.upper() in SUPPORTED_IMAGE_FORMATS
        except Exception as e:
            logger.warning(f"无法验证图片格式: {e}")
            return False
    
    @staticmethod
    def validate_image_size(file_path: Union[str, Path]) -> bool:
        """
        验证图片文件大小
        
        Args:
            file_path: 图片文件路径
            
        Returns:
            bool: 文件大小是否在允许范围内
        """
        try:
            file_size = os.path.getsize(file_path)
            return file_size <= MAX_FILE_SIZE
        except Exception as e:
            logger.warning(f"无法检查文件大小: {e}")
            return False
    
    @staticmethod
    def resize_image_if_needed(image: Image.Image, max_size: Tuple[int, int] = MAX_IMAGE_SIZE) -> Image.Image:
        """
        如果图片过大则调整尺寸
        
        Args:
            image: PIL图片对象
            max_size: 最大尺寸 (width, height)
            
        Returns:
            Image.Image: 调整后的图片
        """
        if image.size[0] <= max_size[0] and image.size[1] <= max_size[1]:
            return image
        
        logger.info(f"调整图片尺寸从 {image.size} 到最大 {max_size}")
        # 保持纵横比缩放
        image.thumbnail(max_size, Image.Resampling.LANCZOS)
        return image
    
    @staticmethod
    def image_to_base64(file_path: Union[str, Path], resize: bool = True) -> str:
        """
        将图片文件转换为base64编码
        
        Args:
            file_path: 图片文件路径
            resize: 是否自动调整尺寸
            
        Returns:
            str: base64编码的图片数据
            
        Raises:
            ValueError: 图片格式不支持或文件过大
            FileNotFoundError: 文件不存在
        """
        file_path = Path(file_path)
        
        # 检查文件是否存在
        if not file_path.exists():
            raise FileNotFoundError(f"图片文件不存在: {file_path}")
        
        # 验证格式
        if not VisionUtils.validate_image_format(file_path):
            raise ValueError(f"不支持的图片格式。支持的格式: {', '.join(SUPPORTED_IMAGE_FORMATS)}")
        
        # 验证文件大小
        if not VisionUtils.validate_image_size(file_path):
            raise ValueError(f"文件过大。最大支持 {MAX_FILE_SIZE // (1024*1024)}MB")
        
        try:
            with Image.open(file_path) as image:
                # 转换为RGB（如果是RGBA或其他模式）
                if image.mode in ('RGBA', 'LA', 'P'):
                    # 对于透明图片，使用白色背景
                    background = Image.new('RGB', image.size, (255, 255, 255))
                    if image.mode == 'P':
                        image = image.convert('RGBA')
                    background.paste(image, mask=image.getchannel('A') if 'A' in image.getbands() else None)
                    image = background
                elif image.mode != 'RGB':
                    image = image.convert('RGB')
                
                # 调整图片尺寸（如果需要）
                if resize:
                    image = VisionUtils.resize_image_if_needed(image)
                
                # 转换为base64
                buffer = io.BytesIO()
                # 使用JPEG格式以减小文件大小，质量设置为85
                image.save(buffer, format='JPEG', quality=85, optimize=True)
                buffer.seek(0)
                
                base64_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
                logger.info(f"图片转换完成: {file_path.name}, 大小: {len(base64_data)//1024}KB")
                
                return base64_data
                
        except Exception as e:
            logger.error(f"图片处理失败: {e}")
            raise ValueError(f"图片处理失败: {e}")
    
    @staticmethod
    def create_image_message_content(image_path: Union[str, Path], text: str = "") -> List[dict]:
        """
        创建包含图片的消息内容（用于LangChain）
        
        Args:
            image_path: 图片文件路径
            text: 附加的文本内容
            
        Returns:
            List[dict]: 消息内容列表
        """
        content = []
        
        # 添加文本内容（如果有）
        if text.strip():
            content.append({
                "type": "text",
                "text": text
            })
        
        # 添加图片内容
        try:
            base64_image = VisionUtils.image_to_base64(image_path)
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{base64_image}"
                }
            })
            
            logger.info(f"创建多模态消息内容，包含图片: {Path(image_path).name}")
            
        except Exception as e:
            logger.error(f"创建图片消息内容失败: {e}")
            raise
        
        return content
    
    @staticmethod
    def get_image_info(file_path: Union[str, Path]) -> dict:
        """
        获取图片信息
        
        Args:
            file_path: 图片文件路径
            
        Returns:
            dict: 图片信息字典
        """
        try:
            with Image.open(file_path) as image:
                file_size = os.path.getsize(file_path)
                
                return {
                    'filename': Path(file_path).name,
                    'format': image.format,
                    'mode': image.mode,
                    'size': image.size,
                    'width': image.size[0],
                    'height': image.size[1],
                    'file_size_bytes': file_size,
                    'file_size_mb': round(file_size / (1024 * 1024), 2),
                    'supported': image.format.upper() in SUPPORTED_IMAGE_FORMATS,
                    'needs_resize': image.size[0] > MAX_IMAGE_SIZE[0] or image.size[1] > MAX_IMAGE_SIZE[1]
                }
        except Exception as e:
            logger.error(f"获取图片信息失败: {e}")
            return {
                'filename': Path(file_path).name,
                'error': str(e),
                'supported': False
            }
    
    @staticmethod
    def batch_process_images(image_paths: List[Union[str, Path]], text: str = "") -> List[dict]:
        """
        批量处理多张图片
        
        Args:
            image_paths: 图片文件路径列表
            text: 附加的文本内容
            
        Returns:
            List[dict]: 处理结果列表
        """
        results = []
        
        for image_path in image_paths:
            try:
                info = VisionUtils.get_image_info(image_path)
                if info.get('supported', False):
                    content = VisionUtils.create_image_message_content(image_path, text)
                    results.append({
                        'path': str(image_path),
                        'status': 'success',
                        'content': content,
                        'info': info
                    })
                else:
                    results.append({
                        'path': str(image_path),
                        'status': 'error',
                        'error': f"不支持的图片格式: {info.get('format', 'unknown')}",
                        'info': info
                    })
            except Exception as e:
                results.append({
                    'path': str(image_path),
                    'status': 'error',
                    'error': str(e)
                })
        
        logger.info(f"批量处理图片完成: {len(results)} 张图片")
        return results


# 便捷函数
def encode_image(image_path: Union[str, Path]) -> str:
    """便捷函数：将图片编码为base64"""
    return VisionUtils.image_to_base64(image_path)


def create_vision_message(image_path: Union[str, Path], text: str = "") -> List[dict]:
    """便捷函数：创建视觉消息内容"""
    return VisionUtils.create_image_message_content(image_path, text)


def check_image_support(image_path: Union[str, Path]) -> bool:
    """便捷函数：检查图片是否支持"""
    return VisionUtils.validate_image_format(image_path) and VisionUtils.validate_image_size(image_path)


def get_supported_formats() -> List[str]:
    """便捷函数：获取支持的图片格式列表"""
    return list(SUPPORTED_IMAGE_FORMATS)


if __name__ == "__main__":
    # 测试代码
    print("支持的图片格式:", get_supported_formats())
    print("最大图片尺寸:", MAX_IMAGE_SIZE)
    print("最大文件大小:", f"{MAX_FILE_SIZE // (1024*1024)}MB")