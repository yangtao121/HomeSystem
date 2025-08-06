"""
Common configuration management for remote services.
"""
import os
from typing import Optional

class Config:
    """Base configuration class for remote services."""
    
    # Common settings
    DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
    HOST = os.getenv('HOST', '0.0.0.0')
    PORT = int(os.getenv('PORT', '5000'))
    
    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = os.getenv('LOG_FILE', 'service.log')
    
    # Request limits
    MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', '100')) * 1024 * 1024  # Default 100MB
    REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', '300'))  # Default 5 minutes
    
    @classmethod
    def get_str(cls, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get string environment variable."""
        return os.getenv(key, default)
    
    @classmethod
    def get_int(cls, key: str, default: int = 0) -> int:
        """Get integer environment variable."""
        try:
            return int(os.getenv(key, str(default)))
        except (ValueError, TypeError):
            return default
    
    @classmethod
    def get_bool(cls, key: str, default: bool = False) -> bool:
        """Get boolean environment variable."""
        value = os.getenv(key, str(default)).lower()
        return value in ('true', '1', 'yes', 'on')


class OCRServiceConfig(Config):
    """Configuration specific to OCR service."""
    
    # OCR specific settings
    MAX_PAGES = get_int('OCR_MAX_PAGES', 25)
    TEMP_DIR = get_str('OCR_TEMP_DIR', '/tmp/ocr_service')
    RESULTS_DIR = get_str('OCR_RESULTS_DIR', '/tmp/ocr_results')
    
    # PaddleOCR settings
    USE_ANGLE_CLS = get_bool('PADDLEOCR_USE_ANGLE_CLS', True)
    USE_GPU = get_bool('PADDLEOCR_USE_GPU', False)
    LANG = get_str('PADDLEOCR_LANG', 'ch')