"""
论文文件夹解析器

专门用于解析论文文件夹结构，提取markdown文本、图片路径映射、
LaTeX公式等信息，为深度分析做准备。
"""

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from loguru import logger


class PaperFolderParser:
    """论文文件夹解析器 - 处理论文文件夹结构和内容提取"""
    
    def __init__(self, folder_path: str):
        """
        初始化解析器
        
        Args:
            folder_path: 论文文件夹路径
        """
        self.folder_path = Path(folder_path)
        self.images_dir = self.folder_path / "imgs"
        
        if not self.folder_path.exists():
            raise FileNotFoundError(f"论文文件夹不存在: {folder_path}")
        
        logger.info(f"PaperFolderParser initialized for: {folder_path}")
    
    def parse_folder(self) -> Dict[str, Any]:
        """
        解析论文文件夹，提取所有相关信息
        
        Returns:
            Dict: 包含所有解析信息的字典
        """
        logger.info("开始解析论文文件夹...")
        
        result = {
            "base_path": str(self.folder_path),
            "paper_text": self._load_paper_text(),
            "image_mappings": self._build_image_mappings(),
            "available_images": self._list_available_images(),
            "latex_formulas": self._extract_latex_formulas(),
            "image_references": self._extract_image_references(),
            "content_sections": self._identify_content_sections(),
            "folder_structure": self._analyze_folder_structure()
        }
        
        logger.info(f"文件夹解析完成: {len(result['paper_text'])} 字符文本, "
                   f"{len(result['available_images'])} 张图片, "
                   f"{result['latex_formulas']['total_count']} 个公式")
        
        return result
    
    def _load_paper_text(self) -> str:
        """加载论文文本内容"""
        # 查找markdown文件
        markdown_files = list(self.folder_path.glob("*.md"))
        
        if not markdown_files:
            logger.warning(f"未在 {self.folder_path} 中找到markdown文件")
            return ""
        
        # 优先选择paddleocr.md文件
        preferred_file = None
        for md_file in markdown_files:
            if "paddleocr" in md_file.name.lower():
                preferred_file = md_file
                break
        
        # 如果没有paddleocr文件，使用第一个markdown文件
        if not preferred_file:
            preferred_file = markdown_files[0]
        
        try:
            with open(preferred_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            logger.info(f"加载论文文本: {preferred_file.name}, 长度: {len(content)} 字符")
            return content
            
        except Exception as e:
            logger.error(f"加载论文文本失败: {e}")
            return ""
    
    def _build_image_mappings(self) -> Dict[str, str]:
        """
        建立图片路径映射：相对路径 -> 绝对路径
        
        Returns:
            Dict: 路径映射字典
        """
        mappings = {}
        
        if not self.images_dir.exists():
            logger.warning(f"图片目录不存在: {self.images_dir}")
            return mappings
        
        # 支持的图片格式
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff']
        
        for img_file in self.images_dir.iterdir():
            if img_file.is_file() and img_file.suffix.lower() in image_extensions:
                relative_path = f"imgs/{img_file.name}"
                absolute_path = str(img_file)
                mappings[relative_path] = absolute_path
        
        logger.info(f"建立图片映射: {len(mappings)} 个文件")
        return mappings
    
    def _list_available_images(self) -> List[str]:
        """
        获取可用图片列表（相对路径）
        
        Returns:
            List[str]: 相对路径列表
        """
        if not self.images_dir.exists():
            return []
        
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff']
        images = []
        
        for img_file in self.images_dir.iterdir():
            if img_file.is_file() and img_file.suffix.lower() in image_extensions:
                relative_path = f"imgs/{img_file.name}"
                images.append(relative_path)
        
        # 按文件名排序
        images.sort()
        return images
    
    def _extract_latex_formulas(self, content: str = None) -> Dict[str, Any]:
        """
        提取LaTeX公式（已在markdown中准确转换）
        
        Args:
            content: 论文文本内容，如果为None则使用已加载的文本
            
        Returns:
            Dict: 公式信息字典
        """
        if content is None:
            content = self._load_paper_text()
        
        formulas = {
            "display_formulas": [],
            "inline_formulas": [],
            "total_count": 0
        }
        
        # 提取行间公式 $$...$$
        display_pattern = r'\$\$(.*?)\$\$'
        display_matches = re.findall(display_pattern, content, re.DOTALL)
        formulas["display_formulas"] = [match.strip() for match in display_matches]
        
        # 提取行内公式 $...$（但不包括$$...$$）
        inline_pattern = r'(?<!\$)\$([^\$\n]+?)\$(?!\$)'
        inline_matches = re.findall(inline_pattern, content)
        formulas["inline_formulas"] = [match.strip() for match in inline_matches]
        
        formulas["total_count"] = len(formulas["display_formulas"]) + len(formulas["inline_formulas"])
        
        logger.info(f"提取公式: {len(formulas['display_formulas'])} 个行间公式, "
                   f"{len(formulas['inline_formulas'])} 个行内公式")
        
        return formulas
    
    def _extract_image_references(self, content: str = None) -> List[str]:
        """
        从markdown内容中提取图片引用
        
        Args:
            content: 论文文本内容
            
        Returns:
            List[str]: 图片引用路径列表
        """
        if content is None:
            content = self._load_paper_text()
        
        # 匹配markdown中的图片引用模式
        patterns = [
            r'imgs/[^)\s"]+\.jpg',
            r'imgs/[^)\s"]+\.jpeg', 
            r'imgs/[^)\s"]+\.png',
            r'imgs/[^)\s"]+\.gif'
        ]
        
        image_refs = []
        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            image_refs.extend(matches)
        
        # 去重并排序
        image_refs = sorted(list(set(image_refs)))
        
        logger.info(f"提取图片引用: {len(image_refs)} 个引用")
        return image_refs
    
    def _identify_content_sections(self, content: str = None) -> Dict[str, Dict[str, Any]]:
        """
        识别论文内容章节结构
        
        Args:
            content: 论文文本内容
            
        Returns:
            Dict: 章节信息字典
        """
        if content is None:
            content = self._load_paper_text()
        
        sections = {}
        
        # 常见的学术论文章节模式
        section_patterns = {
            "abstract": r'(?i)##?\s*abstract\s*\n(.*?)(?=##|\Z)',
            "introduction": r'(?i)##?\s*(?:introduction|1\s+introduction)\s*\n(.*?)(?=##|\Z)',
            "related_work": r'(?i)##?\s*(?:related\s+work|background)\s*\n(.*?)(?=##|\Z)',
            "methodology": r'(?i)##?\s*(?:method|methodology|approach)\s*\n(.*?)(?=##|\Z)',
            "experiments": r'(?i)##?\s*(?:experiment|evaluation|results)\s*\n(.*?)(?=##|\Z)',
            "conclusion": r'(?i)##?\s*(?:conclusion|conclusions)\s*\n(.*?)(?=##|\Z)'
        }
        
        for section_name, pattern in section_patterns.items():
            matches = re.findall(pattern, content, re.DOTALL)
            if matches:
                section_content = matches[0].strip()
                sections[section_name] = {
                    "content": section_content,
                    "length": len(section_content),
                    "word_count": len(section_content.split()),
                    "has_formulas": bool(re.search(r'\$.*?\$', section_content)),
                    "has_images": bool(re.search(r'imgs/', section_content))
                }
        
        logger.info(f"识别章节: {list(sections.keys())}")
        return sections
    
    def _analyze_folder_structure(self) -> Dict[str, Any]:
        """
        分析文件夹结构
        
        Returns:
            Dict: 文件夹结构信息
        """
        structure = {
            "total_files": 0,
            "file_types": {},
            "subdirectories": [],
            "pdf_files": [],
            "markdown_files": [],
            "image_files": [],
            "other_files": []
        }
        
        for item in self.folder_path.iterdir():
            if item.is_file():
                structure["total_files"] += 1
                
                # 统计文件类型
                ext = item.suffix.lower()
                structure["file_types"][ext] = structure["file_types"].get(ext, 0) + 1
                
                # 分类文件
                if ext == '.pdf':
                    structure["pdf_files"].append(item.name)
                elif ext in ['.md', '.markdown']:
                    structure["markdown_files"].append(item.name)
                elif ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']:
                    structure["image_files"].append(item.name)
                else:
                    structure["other_files"].append(item.name)
            
            elif item.is_dir():
                structure["subdirectories"].append(item.name)
        
        # 检查imgs目录
        if self.images_dir.exists():
            img_count = len(list(self.images_dir.glob("*")))
            structure["imgs_directory"] = {
                "exists": True,
                "file_count": img_count
            }
        else:
            structure["imgs_directory"] = {"exists": False}
        
        return structure
    
    def categorize_images_by_type(self, image_refs: List[str] = None) -> Dict[str, List[str]]:
        """
        根据文件名特征对图片进行分类
        
        Args:
            image_refs: 图片引用列表，如果为None则使用已提取的引用
            
        Returns:
            Dict: 分类后的图片字典
        """
        if image_refs is None:
            image_refs = self._extract_image_references()
        
        categorized = {
            "architecture_diagrams": [],    # 架构图
            "result_charts": [],           # 结果图表
            "tables": [],                  # 表格
            "formulas": [],                # 公式图片
            "examples": [],                # 示例图
            "other": []
        }
        
        for img_path in image_refs:
            img_name = img_path.lower()
            
            if "table" in img_name:
                categorized["tables"].append(img_path)
            elif "formula" in img_name:
                categorized["formulas"].append(img_path)
            elif "image_box" in img_name:
                # 通常是图表或架构图
                categorized["architecture_diagrams"].append(img_path)
            elif any(keyword in img_name for keyword in ["chart", "graph", "plot"]):
                categorized["result_charts"].append(img_path)
            elif any(keyword in img_name for keyword in ["example", "sample"]):
                categorized["examples"].append(img_path)
            else:
                categorized["other"].append(img_path)
        
        logger.info(f"图片分类: 架构图 {len(categorized['architecture_diagrams'])}, "
                   f"图表 {len(categorized['result_charts'])}, "
                   f"表格 {len(categorized['tables'])}, "
                   f"其他 {len(categorized['other'])}")
        
        return categorized
    
    def validate_folder_integrity(self) -> Dict[str, Any]:
        """
        验证文件夹完整性
        
        Returns:
            Dict: 验证结果
        """
        validation = {
            "is_valid": True,
            "issues": [],
            "recommendations": []
        }
        
        # 检查必需文件
        if not any(self.folder_path.glob("*.md")):
            validation["is_valid"] = False
            validation["issues"].append("缺少markdown文件")
            validation["recommendations"].append("请确保有OCR处理后的markdown文件")
        
        # 检查图片目录
        if not self.images_dir.exists():
            validation["issues"].append("缺少imgs目录")
            validation["recommendations"].append("如果有图片，请创建imgs目录")
        elif len(list(self.images_dir.glob("*"))) == 0:
            validation["issues"].append("imgs目录为空")
        
        # 检查文件权限
        try:
            markdown_files = list(self.folder_path.glob("*.md"))
            if markdown_files:
                with open(markdown_files[0], 'r', encoding='utf-8') as f:
                    f.read(100)  # 尝试读取一些内容
        except Exception as e:
            validation["is_valid"] = False
            validation["issues"].append(f"无法读取markdown文件: {e}")
            validation["recommendations"].append("检查文件权限和编码")
        
        logger.info(f"文件夹验证: {'通过' if validation['is_valid'] else '失败'}, "
                   f"{len(validation['issues'])} 个问题")
        
        return validation


def create_paper_folder_parser(folder_path: str) -> PaperFolderParser:
    """
    创建论文文件夹解析器的便捷函数
    
    Args:
        folder_path: 论文文件夹路径
        
    Returns:
        PaperFolderParser: 配置好的解析器实例
    """
    return PaperFolderParser(folder_path)


def parse_paper_folder(folder_path: str) -> Dict[str, Any]:
    """
    解析论文文件夹的便捷函数
    
    Args:
        folder_path: 论文文件夹路径
        
    Returns:
        Dict: 解析结果
    """
    parser = PaperFolderParser(folder_path)
    return parser.parse_folder()


# 测试代码
if __name__ == "__main__":
    # 测试解析器 - 使用相对路径
    current_dir = os.path.dirname(__file__)
    project_root = os.path.join(current_dir, '..', '..', '..')
    test_folder = os.path.join(project_root, "data/paper_analyze/2502.13508")
    
    try:
        parser = create_paper_folder_parser(test_folder)
        
        # 验证文件夹
        validation = parser.validate_folder_integrity()
        print(f"文件夹验证: {validation['is_valid']}")
        if validation["issues"]:
            print(f"问题: {validation['issues']}")
        
        # 解析文件夹
        result = parser.parse_folder()
        print(f"解析完成:")
        print(f"  文本长度: {len(result['paper_text'])} 字符")
        print(f"  图片数量: {len(result['available_images'])}")
        print(f"  公式数量: {result['latex_formulas']['total_count']}")
        print(f"  章节数量: {len(result['content_sections'])}")
        
        # 图片分类
        categorized = parser.categorize_images_by_type()
        for category, images in categorized.items():
            if images:
                print(f"  {category}: {len(images)} 张")
    
    except Exception as e:
        print(f"测试失败: {e}")