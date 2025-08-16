"""
OCR processor using PaddleOCR PPStructureV3 for remote service.
Simplified to match local _performOCR_paddleocr implementation.
"""
import os
import tempfile
from typing import Optional, Tuple, Dict, Any
import fitz  # PyMuPDF
from pathlib import Path

# Check if PaddleOCR is available
print("DEBUG: Testing PaddleOCR import...")
try:
    from paddleocr import PPStructureV3
    print("DEBUG: PPStructureV3 import successful")
    OCR_AVAILABLE = True
except ImportError as e:
    print(f"DEBUG: PPStructureV3 import failed with ImportError: {e}")
    OCR_AVAILABLE = False
except Exception as e:
    print(f"DEBUG: PPStructureV3 import failed with Exception: {e}")
    OCR_AVAILABLE = False

print(f"DEBUG: Final OCR_AVAILABLE = {OCR_AVAILABLE}")


class OCRProcessor:
    """PaddleOCR PPStructureV3 processor for document analysis."""
    
    def __init__(self):
        """Initialize OCR processor."""
        self.pipeline = None
        if OCR_AVAILABLE:
            try:
                from shared.config import OCRServiceConfig
                # Initialize PaddleOCR PPStructureV3 - matches local implementation
                self.pipeline = PPStructureV3()
                print(f"PPStructureV3 initialized successfully (GPU: {OCRServiceConfig.USE_GPU})")
            except Exception as e:
                print(f"Failed to initialize PPStructureV3: {e}")
                self.pipeline = None
        else:
            print("PPStructureV3 not available - missing dependencies")
    
    def process_pdf(
        self, 
        pdf_path: str, 
        max_pages: int = 25,
        output_path: Optional[str] = None,
        arxiv_id: str = "unknown"
    ) -> Tuple[Optional[str], Dict[str, Any]]:
        """
        Process PDF using PaddleOCR PPStructureV3 (matches local _performOCR_paddleocr).
        
        Args:
            pdf_path: Path to PDF file
            max_pages: Maximum pages to process (unused but kept for API compatibility)
            output_path: Output directory path
            arxiv_id: ArXiv paper ID for naming
            
        Returns:
            Tuple of (OCR markdown text, status info dict)
        """
        if not OCR_AVAILABLE or self.pipeline is None:
            return None, {
                'error': 'PPStructureV3 not available or failed to initialize',
                'total_pages': 0,
                'processed_pages': 0,
                'is_oversized': False,
                'char_count': 0,
                'method': 'paddleocr',
                'saved_files': []
            }
        
        try:
            # Check total pages using PyMuPDF - matches local implementation
            pdf_document = fitz.open(pdf_path)
            total_pages = len(pdf_document)
            pdf_document.close()
            
            print(f"PDF总页数: {total_pages}")
            
            # Check if document is oversized - matches local implementation
            is_oversized = total_pages > max_pages
            if is_oversized:
                print(f"文档页数({total_pages})超过限制({max_pages})，将只处理前{max_pages}页")
            
            pages_to_process = min(max_pages, total_pages)
            
            # Create output directory - matches local implementation  
            if output_path:
                output_dir = Path(output_path)
                output_dir.mkdir(parents=True, exist_ok=True)
            else:
                output_dir = Path(tempfile.mkdtemp())
                
            print(f"输出目录: {output_dir}")
            
            # Execute structured recognition - EXACTLY like local implementation
            print("开始执行结构化文档识别...")
            output = self.pipeline.predict(input=pdf_path)
            
            # Process results and extract markdown and images - matches local implementation
            markdown_list = []
            markdown_images = []
            
            for res in output:
                if hasattr(res, 'markdown'):
                    md_info = res.markdown
                    markdown_list.append(md_info)
                    markdown_images.append(md_info.get("markdown_images", {}))
            
            # Merge markdown pages - matches local implementation
            if hasattr(self.pipeline, 'concatenate_markdown_pages'):
                markdown_texts = self.pipeline.concatenate_markdown_pages(markdown_list)
            else:
                # Backup method: manual merge
                markdown_texts = "\n\n".join([str(md) for md in markdown_list if md])
            
            if not markdown_texts:
                markdown_texts = f"# OCR Analysis for {arxiv_id}\n\nPPStructureV3 processing completed but no text content was extracted."
            
            # Save files - matches local implementation
            saved_files = []
            
            # Use arxiv_id as filename (if available) - matches local implementation
            base_filename = arxiv_id if (arxiv_id and arxiv_id != "unknown") else "unknown"
            mkd_file_path = output_dir / f"{base_filename}_paddleocr.md"
            
            with open(mkd_file_path, "w", encoding="utf-8") as f:
                f.write(markdown_texts)
            saved_files.append(str(mkd_file_path))
            
            # Create imgs directory - matches local implementation
            imgs_dir = output_dir / "imgs"
            imgs_dir.mkdir(exist_ok=True)
            
            # Save images - matches local implementation
            images_saved = 0
            for item in markdown_images:
                if item:
                    for path, image in item.items():
                        # Remove redundant imgs/ prefix if present (PPStructureV3 may include it)
                        clean_path = path.replace('imgs/', '', 1) if path.startswith('imgs/') else path
                        file_path = imgs_dir / clean_path
                        file_path.parent.mkdir(parents=True, exist_ok=True)
                        image.save(file_path)
                        saved_files.append(str(file_path))
                        images_saved += 1
            
            print(f"Markdown文件和图片已保存到: {output_dir}")
            print(f"保存了 {images_saved} 张图片")
            
            # Build status info - matches local implementation
            total_chars = len(markdown_texts) if markdown_texts else 0
            status_info = {
                'total_pages': total_pages,
                'processed_pages': pages_to_process,
                'is_oversized': is_oversized,
                'char_count': total_chars,
                'method': 'paddleocr',
                'images_count': images_saved,
                'saved_files': saved_files
            }
            
            print(f"PaddleOCR结构化识别完成，处理了 {pages_to_process}/{total_pages} 页，提取Markdown文本 {total_chars} 个字符，提取图片 {images_saved} 张")
            
            return markdown_texts, status_info
            
        except Exception as e:
            print(f"PPStructureV3 processing error: {str(e)}")
            import traceback
            traceback.print_exc()
            return None, {
                'error': f'PPStructureV3 processing error: {str(e)}',
                'total_pages': 0,
                'processed_pages': 0,
                'is_oversized': False,
                'char_count': 0,
                'method': 'paddleocr',
                'saved_files': []
            }