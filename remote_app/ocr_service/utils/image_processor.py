"""
Image processing utilities for OCR service.
"""
import os
from typing import List, Tuple, Optional
from pathlib import Path
import cv2
import numpy as np
from PIL import Image


class ImageProcessor:
    """Handle image processing operations for OCR."""
    
    def __init__(self):
        pass
    
    def save_image_from_array(
        self, 
        image_array: np.ndarray, 
        save_path: str, 
        quality: int = 95
    ) -> bool:
        """
        Save image array to file.
        
        Args:
            image_array: Image as numpy array
            save_path: Path to save the image
            quality: JPEG quality (1-100)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Convert BGR to RGB if needed (OpenCV uses BGR)
            if len(image_array.shape) == 3 and image_array.shape[2] == 3:
                image_array = cv2.cvtColor(image_array, cv2.COLOR_BGR2RGB)
            
            # Convert to PIL Image and save
            pil_image = Image.fromarray(image_array)
            pil_image.save(save_path, 'JPEG', quality=quality)
            
            return True
            
        except Exception as e:
            print(f"Error saving image: {str(e)}")
            return False
    
    def resize_image_if_needed(
        self, 
        image_array: np.ndarray, 
        max_width: int = 2048, 
        max_height: int = 2048
    ) -> np.ndarray:
        """
        Resize image if it's too large.
        
        Args:
            image_array: Input image array
            max_width: Maximum width
            max_height: Maximum height
            
        Returns:
            Resized image array
        """
        height, width = image_array.shape[:2]
        
        if width <= max_width and height <= max_height:
            return image_array
        
        # Calculate scaling factor
        scale_width = max_width / width
        scale_height = max_height / height
        scale_factor = min(scale_width, scale_height)
        
        # Calculate new dimensions
        new_width = int(width * scale_factor)
        new_height = int(height * scale_factor)
        
        # Resize image
        resized = cv2.resize(image_array, (new_width, new_height), interpolation=cv2.INTER_AREA)
        
        return resized
    
    def preprocess_for_ocr(self, image_array: np.ndarray) -> np.ndarray:
        """
        Preprocess image for better OCR results.
        
        Args:
            image_array: Input image array
            
        Returns:
            Preprocessed image array
        """
        # Convert to grayscale if color
        if len(image_array.shape) == 3:
            gray = cv2.cvtColor(image_array, cv2.COLOR_BGR2GRAY)
        else:
            gray = image_array.copy()
        
        # Apply slight denoising
        denoised = cv2.fastNlMeansDenoising(gray)
        
        # Enhance contrast slightly
        enhanced = cv2.convertScaleAbs(denoised, alpha=1.1, beta=10)
        
        return enhanced
    
    def extract_image_regions(
        self, 
        page_image: np.ndarray, 
        regions: List[Tuple[int, int, int, int]],
        output_dir: str,
        prefix: str = "img"
    ) -> List[str]:
        """
        Extract image regions from a page.
        
        Args:
            page_image: Full page image as numpy array
            regions: List of (x, y, width, height) tuples
            output_dir: Directory to save extracted images
            prefix: Filename prefix
            
        Returns:
            List of saved image file paths
        """
        saved_images = []
        
        for i, (x, y, w, h) in enumerate(regions):
            try:
                # Extract region
                region = page_image[y:y+h, x:x+w]
                
                # Generate filename
                filename = f"{prefix}_region_{i}_{x}_{y}_{w}_{h}.jpg"
                filepath = os.path.join(output_dir, filename)
                
                # Save image
                if self.save_image_from_array(region, filepath):
                    saved_images.append(filepath)
                    
            except Exception as e:
                print(f"Error extracting region {i}: {str(e)}")
        
        return saved_images
    
    def validate_image(self, image_path: str) -> Tuple[bool, Optional[str]]:
        """
        Validate image file.
        
        Args:
            image_path: Path to image file
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Try to load with OpenCV
            image = cv2.imread(image_path)
            if image is None:
                return False, "Cannot load image file"
            
            # Check dimensions
            height, width = image.shape[:2]
            if height == 0 or width == 0:
                return False, "Image has zero dimensions"
            
            return True, None
            
        except Exception as e:
            return False, f"Image validation error: {str(e)}"