"""
Remote OCR Service - Flask application for PaddleOCR processing.
"""
import os
import sys
import uuid
import traceback
import base64
from pathlib import Path
from flask import Flask, request, jsonify, send_file
from werkzeug.utils import secure_filename

from shared.config import OCRServiceConfig
from shared.logging import setup_logging
from shared.auth import require_api_key, get_client_ip
from processor import OCRProcessor
from utils.file_handler import FileHandler


# Initialize Flask app
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = OCRServiceConfig.MAX_CONTENT_LENGTH

# Setup logging
logger = setup_logging('ocr_service', OCRServiceConfig.LOG_LEVEL, OCRServiceConfig.LOG_FILE)

# Initialize components
file_handler = FileHandler(OCRServiceConfig.TEMP_DIR, OCRServiceConfig.RESULTS_DIR)
ocr_processor = OCRProcessor()


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'service': 'ocr_service',
        'version': '1.0.0'
    })


@app.route('/api/ocr/process', methods=['POST'])
@require_api_key
def process_ocr():
    """
    Process PDF file using PaddleOCR.
    
    Expected form data:
    - file: PDF file
    - max_pages: (optional) Maximum pages to process
    - arxiv_id: (optional) ArXiv paper ID for naming
    """
    client_ip = get_client_ip()
    logger.info(f"OCR processing request from {client_ip}")
    
    try:
        # Check if file was uploaded
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Get parameters
        max_pages = int(request.form.get('max_pages', OCRServiceConfig.MAX_PAGES))
        arxiv_id = request.form.get('arxiv_id', 'unknown')
        
        logger.info(f"Processing PDF: {file.filename}, max_pages: {max_pages}, arxiv_id: {arxiv_id}")
        
        # Generate job ID
        job_id = str(uuid.uuid4())
        
        # Save uploaded file
        file_data = file.read()
        temp_file_path = file_handler.save_uploaded_file(file_data, file.filename)
        
        try:
            # Validate PDF
            is_valid, error_msg = file_handler.validate_pdf(temp_file_path)
            if not is_valid:
                return jsonify({'error': error_msg}), 400
            
            # Create results directory using arxiv_id for consistency
            results_dir = file_handler.create_results_directory(arxiv_id, job_id)
            
            # Process PDF with OCR
            ocr_result, status_info = ocr_processor.process_pdf(
                pdf_path=temp_file_path,
                max_pages=max_pages,
                output_path=results_dir,
                arxiv_id=arxiv_id
            )
            
            if ocr_result is None:
                return jsonify({
                    'error': 'OCR processing failed',
                    'status_info': status_info
                }), 500
            
            # Read and encode images for transmission
            images_data = {}
            imgs_dir = Path(results_dir) / "imgs"
            if imgs_dir.exists():
                for img_file in imgs_dir.glob("*.jpg"):
                    try:
                        with open(img_file, 'rb') as f:
                            img_base64 = base64.b64encode(f.read()).decode('utf-8')
                            images_data[img_file.name] = img_base64
                    except Exception as e:
                        logger.warning(f"Failed to encode image {img_file}: {e}")
            
            logger.info(f"OCR processing completed successfully for job {job_id}, images: {len(images_data)}")
            
            # Return response with embedded images for remote transmission
            return jsonify({
                'job_id': job_id,
                'arxiv_id': arxiv_id,
                'ocr_result': ocr_result,
                'status_info': status_info,
                'images': images_data,
                'success': True
            })
            
        finally:
            # Cleanup temporary file
            file_handler.cleanup_temp_files([temp_file_path])
    
    except Exception as e:
        logger.error(f"OCR processing error: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            'error': f'Internal server error: {str(e)}',
            'success': False
        }), 500


@app.route('/api/ocr/download/<job_id>', methods=['GET'])
@require_api_key
def download_results(job_id):
    """Download OCR results for a job."""
    try:
        results_dir = os.path.join(OCRServiceConfig.RESULTS_DIR, job_id)
        
        if not os.path.exists(results_dir):
            return jsonify({'error': 'Job not found'}), 404
        
        # Find the analysis markdown file
        analysis_files = [f for f in os.listdir(results_dir) if f.endswith('_analysis.md')]
        
        if not analysis_files:
            return jsonify({'error': 'No results available'}), 404
        
        analysis_file = os.path.join(results_dir, analysis_files[0])
        return send_file(analysis_file, as_attachment=True)
        
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        return jsonify({'error': 'Download failed'}), 500


@app.errorhandler(413)
def request_entity_too_large(error):
    """Handle file too large error."""
    return jsonify({'error': 'File too large'}), 413


@app.errorhandler(Exception)
def handle_exception(e):
    """Handle unexpected exceptions."""
    logger.error(f"Unhandled exception: {str(e)}")
    logger.error(traceback.format_exc())
    return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    logger.info("Starting OCR Service...")
    logger.info(f"Config: Max pages={OCRServiceConfig.MAX_PAGES}, GPU={OCRServiceConfig.USE_GPU}")
    
    # Cleanup old files on startup
    file_handler.cleanup_old_files()
    
    app.run(
        host=OCRServiceConfig.HOST,
        port=OCRServiceConfig.PORT,
        debug=OCRServiceConfig.DEBUG
    )