"""
File handling utilities for OCR service.
"""
import os
import uuid
import tempfile
import shutil
from typing import Optional, Tuple, List
from pathlib import Path
import fitz  # PyMuPDF


class FileHandler:
    """Handle file upload, processing, and cleanup operations."""
    
    def __init__(self, temp_dir: str = "/tmp/ocr_service", results_dir: str = "/tmp/ocr_results"):
        self.temp_dir = Path(temp_dir)
        self.results_dir = Path(results_dir)
        
        # Ensure directories exist
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.results_dir.mkdir(parents=True, exist_ok=True)
    
    def save_uploaded_file(self, file_data: bytes, filename: str) -> str:
        """
        Save uploaded file to temporary directory.
        
        Args:
            file_data: Binary file data
            filename: Original filename
            
        Returns:
            Path to saved file
        """
        # Generate unique filename
        unique_id = str(uuid.uuid4())
        file_ext = Path(filename).suffix.lower()
        
        if file_ext not in ['.pdf']:
            raise ValueError(f"Unsupported file type: {file_ext}")
        
        temp_filename = f"{unique_id}_{filename}"
        temp_path = self.temp_dir / temp_filename
        
        # Save file
        with open(temp_path, 'wb') as f:
            f.write(file_data)
        
        return str(temp_path)
    
    def validate_pdf(self, pdf_path: str) -> Tuple[bool, Optional[str]]:
        """
        Validate PDF file.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            doc = fitz.open(pdf_path)
            page_count = len(doc)
            doc.close()
            
            if page_count == 0:
                return False, "PDF contains no pages"
            
            return True, None
            
        except Exception as e:
            return False, f"Invalid PDF file: {str(e)}"
    
    def create_results_directory(self, arxiv_id: str, job_id: str = None) -> str:
        """
        Create directory for storing OCR results.
        
        Args:
            arxiv_id: ArXiv paper ID (used as directory name for consistency)
            job_id: Unique job identifier (fallback if arxiv_id not available)
            
        Returns:
            Path to results directory
        """
        # Use arxiv_id as directory name for consistency with local behavior
        # Fall back to job_id if arxiv_id is not available or is "unknown"
        dir_name = arxiv_id if arxiv_id and arxiv_id != "unknown" else job_id
        
        results_path = self.results_dir / dir_name
        results_path.mkdir(parents=True, exist_ok=True)
        
        # Create imgs subdirectory for extracted images
        imgs_path = results_path / "imgs"
        imgs_path.mkdir(exist_ok=True)
        
        return str(results_path)
    
    def save_ocr_results(
        self, 
        job_id: str, 
        ocr_text: str, 
        arxiv_id: str = "unknown"
    ) -> List[str]:
        """
        Save OCR results to files.
        
        Args:
            job_id: Unique job identifier
            ocr_text: OCR extracted text
            arxiv_id: ArXiv paper ID
            
        Returns:
            List of saved file paths
        """
        results_path = Path(self.results_dir) / job_id
        
        # Save main OCR result
        analysis_file = results_path / f"{arxiv_id}_analysis.md"
        with open(analysis_file, 'w', encoding='utf-8') as f:
            f.write(ocr_text)
        
        return [str(analysis_file)]
    
    def cleanup_temp_files(self, file_paths: List[str]) -> None:
        """
        Clean up temporary files.
        
        Args:
            file_paths: List of file paths to remove
        """
        for file_path in file_paths:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception:
                pass  # Ignore cleanup errors
    
    def cleanup_old_files(self, max_age_hours: int = 24) -> None:
        """
        Clean up old temporary and result files.
        
        Args:
            max_age_hours: Maximum age of files to keep in hours
        """
        import time
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        
        for directory in [self.temp_dir, self.results_dir]:
            if not directory.exists():
                continue
                
            for file_path in directory.rglob("*"):
                if file_path.is_file():
                    try:
                        file_age = current_time - file_path.stat().st_mtime
                        if file_age > max_age_seconds:
                            file_path.unlink()
                    except Exception:
                        pass  # Ignore cleanup errors