"""
OCR processor using PaddleOCR for remote service.
"""
import os
import tempfile
from typing import Optional, Tuple, Dict, Any
import fitz  # PyMuPDF
from pathlib import Path

# Check if PaddleOCR is available
try:
    from ppstructure import PPStructureV3
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False


class OCRProcessor:
    """PaddleOCR processor for document analysis."""
    
    def __init__(self):
        """Initialize OCR processor."""
        self.pipeline = None
        if OCR_AVAILABLE:
            try:
                self.pipeline = PPStructureV3()
                print("PaddleOCR PPStructureV3 initialized successfully")
            except Exception as e:
                print(f"Failed to initialize PaddleOCR: {e}")
                self.pipeline = None
        else:
            print("PaddleOCR not available - missing dependencies")
    
    def process_pdf(
        self, 
        pdf_path: str, 
        max_pages: int = 25,
        output_path: Optional[str] = None,
        arxiv_id: str = "unknown"
    ) -> Tuple[Optional[str], Dict[str, Any]]:
        """
        Process PDF using PaddleOCR (equivalent to _performOCR_paddleocr).
        
        Args:
            pdf_path: Path to PDF file
            max_pages: Maximum pages to process
            output_path: Output directory path
            arxiv_id: ArXiv paper ID for naming
            
        Returns:
            Tuple of (OCR text, status info dict)
        """
        if not OCR_AVAILABLE or self.pipeline is None:
            return None, {
                'error': 'PaddleOCR not available or failed to initialize',
                'total_pages': 0,
                'processed_pages': 0,
                'is_oversized': False,
                'char_count': 0,
                'method': 'paddleocr',
                'saved_files': []
            }
        
        try:
            # Check total pages using PyMuPDF
            pdf_document = fitz.open(pdf_path)
            total_pages = len(pdf_document)
            pdf_document.close()
            
            print(f"PDF total pages: {total_pages}")
            
            # Check if document is oversized
            is_oversized = total_pages > max_pages
            if is_oversized:
                print(f"Document pages ({total_pages}) exceed limit ({max_pages}), processing first {max_pages} pages only")
            
            # Determine pages to process
            pages_to_process = min(max_pages, total_pages)
            
            # Create output directory if specified
            if output_path:
                output_dir = Path(output_path)
                output_dir.mkdir(parents=True, exist_ok=True)
                imgs_dir = output_dir / "imgs"
                imgs_dir.mkdir(exist_ok=True)
            else:
                output_dir = None
                imgs_dir = None
            
            # Process PDF with PaddleOCR
            try:
                print(f"Starting PaddleOCR processing for {pages_to_process} pages...")
                
                # Use a temporary directory for PaddleOCR output
                with tempfile.TemporaryDirectory() as temp_ocr_dir:
                    # Process document with PaddleOCR
                    results = self.pipeline(
                        pdf_path, 
                        output=temp_ocr_dir,
                        page_range=[0, pages_to_process-1] if pages_to_process < total_pages else None
                    )
                    
                    # Extract text and images from results
                    markdown_text = self._extract_markdown_from_results(
                        results, 
                        temp_ocr_dir, 
                        imgs_dir,
                        arxiv_id
                    )
                    
                    # Calculate character count
                    char_count = len(markdown_text) if markdown_text else 0
                    
                    # Prepare saved files list
                    saved_files = []
                    if output_dir and markdown_text:
                        # Save main markdown file
                        markdown_file = output_dir / f"{arxiv_id}_analysis.md"
                        with open(markdown_file, 'w', encoding='utf-8') as f:
                            f.write(markdown_text)
                        saved_files.append(str(markdown_file))
                        
                        # Add image files if any
                        if imgs_dir and imgs_dir.exists():
                            for img_file in imgs_dir.glob("*.jpg"):
                                saved_files.append(str(img_file))
                    
                    status_info = {
                        'total_pages': total_pages,
                        'processed_pages': pages_to_process,
                        'is_oversized': is_oversized,
                        'char_count': char_count,
                        'method': 'paddleocr',
                        'saved_files': saved_files
                    }
                    
                    print(f"PaddleOCR processing completed: {char_count} characters extracted")
                    
                    return markdown_text, status_info
                    
            except Exception as e:
                print(f"PaddleOCR processing failed: {str(e)}")
                return None, {
                    'error': f'PaddleOCR processing failed: {str(e)}',
                    'total_pages': total_pages,
                    'processed_pages': 0,
                    'is_oversized': is_oversized,
                    'char_count': 0,
                    'method': 'paddleocr',
                    'saved_files': []
                }
                
        except Exception as e:
            print(f"PDF processing error: {str(e)}")
            return None, {
                'error': f'PDF processing error: {str(e)}',
                'total_pages': 0,
                'processed_pages': 0,
                'is_oversized': False,
                'char_count': 0,
                'method': 'paddleocr',
                'saved_files': []
            }
    
    def _extract_markdown_from_results(
        self, 
        results: Any, 
        temp_dir: str, 
        imgs_dir: Optional[Path],
        arxiv_id: str
    ) -> str:
        """
        Extract markdown text from PaddleOCR results.
        
        Args:
            results: PaddleOCR processing results
            temp_dir: Temporary directory with OCR output
            imgs_dir: Directory to save images
            arxiv_id: ArXiv paper ID
            
        Returns:
            Formatted markdown text
        """
        # This is a simplified implementation
        # In practice, you would need to parse PaddleOCR's structured output
        # and convert it to the same markdown format as the original implementation
        
        markdown_content = []
        
        # Add header
        markdown_content.append(f"# OCR Analysis for {arxiv_id}")
        markdown_content.append("")
        
        # Try to read any generated markdown files from PaddleOCR
        temp_path = Path(temp_dir)
        
        # Look for markdown files generated by PaddleOCR
        markdown_files = list(temp_path.glob("*.md"))
        if markdown_files:
            for md_file in markdown_files:
                try:
                    with open(md_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        markdown_content.append(content)
                except Exception as e:
                    print(f"Error reading markdown file {md_file}: {e}")
        else:
            # If no markdown files, try to extract text from results directly
            if hasattr(results, '__iter__'):
                for result in results:
                    if isinstance(result, dict) and 'text' in result:
                        markdown_content.append(result['text'])
                    elif isinstance(result, str):
                        markdown_content.append(result)
        
        # Copy any images to the output directory
        if imgs_dir:
            self._copy_images_from_temp(temp_path, imgs_dir)
        
        # Join all content
        full_text = "\n".join(markdown_content)
        
        # If no content was extracted, provide a basic message
        if not full_text.strip():
            full_text = f"# OCR Analysis for {arxiv_id}\n\nOCR processing completed but no text content was extracted."
        
        return full_text
    
    def _copy_images_from_temp(self, temp_dir: Path, target_dir: Path) -> None:
        """
        Copy images from temporary directory to target directory.
        
        Args:
            temp_dir: Source temporary directory
            target_dir: Target images directory
        """
        try:
            # Copy any image files generated by PaddleOCR
            for img_file in temp_dir.rglob("*.jpg"):
                target_file = target_dir / img_file.name
                import shutil
                shutil.copy2(img_file, target_file)
                
            for img_file in temp_dir.rglob("*.png"):
                # Convert PNG to JPG for consistency
                from PIL import Image
                img = Image.open(img_file)
                if img.mode == 'RGBA':
                    img = img.convert('RGB')
                target_file = target_dir / f"{img_file.stem}.jpg"
                img.save(target_file, 'JPEG', quality=95)
                
        except Exception as e:
            print(f"Error copying images: {e}")
    
    def is_available(self) -> bool:
        """Check if OCR processor is available."""
        return OCR_AVAILABLE and self.pipeline is not None