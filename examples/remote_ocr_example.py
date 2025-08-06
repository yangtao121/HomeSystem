"""
Remote OCR Service Usage Example

This example demonstrates how to use the remote OCR functionality
with the ArxivTool class.
"""

import os
import sys
import asyncio

# Add HomeSystem to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from HomeSystem.utility.arxiv import ArxivTool

def main():
    """Test remote OCR functionality."""
    
    # Set up remote OCR configuration
    os.environ['REMOTE_OCR_ENDPOINT'] = 'http://localhost:5000'
    os.environ['REMOTE_OCR_TIMEOUT'] = '300'
    # Optional: Set API key if required
    # os.environ['REMOTE_OCR_API_KEY'] = 'your-api-key-here'
    
    print("Remote OCR Service Example")
    print("=" * 40)
    
    # Example ArXiv ID to test with
    arxiv_id = "2412.12091"  # This should be an existing paper
    
    # Create ArxivTool instance
    print(f"Testing with ArXiv ID: {arxiv_id}")
    arxiv_tool = ArxivTool()
    
    try:
        # Search for the paper
        print("Searching for paper...")
        results = arxiv_tool.search(f"id:{arxiv_id}", max_results=1)
        
        if not results:
            print("Paper not found!")
            return
        
        paper = results[0]
        print(f"Found paper: {paper['title']}")
        
        # Download PDF
        print("Downloading PDF...")
        success = arxiv_tool.downloadPdf(arxiv_id)
        
        if not success:
            print("Failed to download PDF!")
            return
        
        print("PDF downloaded successfully")
        
        # Test 1: Local PyMuPDF (default)
        print("\n" + "=" * 40)
        print("Test 1: Local PyMuPDF OCR")
        print("=" * 40)
        
        ocr_result, status_info = arxiv_tool.performOCR(max_pages=5)
        
        if ocr_result:
            print(f"Local PyMuPDF Success!")
            print(f"Method: {status_info['method']}")
            print(f"Pages processed: {status_info['processed_pages']}/{status_info['total_pages']}")
            print(f"Characters extracted: {status_info['char_count']}")
            print(f"Text preview: {ocr_result[:200]}...")
        else:
            print(f"Local PyMuPDF Failed: {status_info.get('error', 'Unknown error')}")
        
        # Test 2: Remote OCR Service
        print("\n" + "=" * 40)
        print("Test 2: Remote PaddleOCR Service")
        print("=" * 40)
        
        # Check if remote service is configured
        remote_endpoint = os.getenv('REMOTE_OCR_ENDPOINT')
        if not remote_endpoint:
            print("Remote OCR endpoint not configured!")
            print("Please set REMOTE_OCR_ENDPOINT environment variable")
            return
        
        print(f"Using remote service: {remote_endpoint}")
        
        try:
            # Test remote OCR
            ocr_result, status_info = arxiv_tool.performOCR(
                max_pages=5, 
                use_remote_ocr=True,
                auto_save=True  # Save results locally
            )
            
            if ocr_result:
                print(f"Remote OCR Success!")
                print(f"Method: {status_info['method']}")
                print(f"Pages processed: {status_info['processed_pages']}/{status_info['total_pages']}")
                print(f"Characters extracted: {status_info['char_count']}")
                print(f"Saved files: {len(status_info.get('saved_files', []))}")
                
                if status_info.get('saved_files'):
                    print(f"Results saved to: {status_info['saved_files'][0]}")
                
                print(f"Text preview: {ocr_result[:200]}...")
            else:
                print(f"Remote OCR Failed: {status_info.get('error', 'Unknown error')}")
                
        except Exception as e:
            print(f"Remote OCR Exception: {str(e)}")
        
        # Test 3: Local PaddleOCR (fallback comparison)
        print("\n" + "=" * 40)
        print("Test 3: Local PaddleOCR (for comparison)")
        print("=" * 40)
        
        try:
            ocr_result, status_info = arxiv_tool.performOCR(
                max_pages=5,
                use_paddleocr=True
            )
            
            if ocr_result:
                print(f"Local PaddleOCR Success!")
                print(f"Method: {status_info['method']}")
                print(f"Pages processed: {status_info['processed_pages']}/{status_info['total_pages']}")
                print(f"Characters extracted: {status_info['char_count']}")
                print(f"Text preview: {ocr_result[:200]}...")
            else:
                print(f"Local PaddleOCR Failed: {status_info.get('error', 'Unknown error')}")
                
        except Exception as e:
            print(f"Local PaddleOCR Exception: {str(e)}")
        
    except Exception as e:
        print(f"Example failed with exception: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Clean up
        arxiv_tool.clearPdf()
        print("\nExample completed")


if __name__ == "__main__":
    main()