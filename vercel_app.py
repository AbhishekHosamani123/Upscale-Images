from flask import Flask, request, jsonify, render_template, send_file
import os
import uuid
import time
import base64
import tempfile
from ImageUpscalePython import ImageUpscaler
from config import get_config
from utils.logging import logger, log_request_duration, handle_exceptions, error_handler
from utils.security import security_validator

# Initialize Flask app with configuration
config_class = get_config()
app = Flask(__name__)
app.config.from_object(config_class)

# Create temporary directories for Vercel
temp_upload_dir = tempfile.mkdtemp()
temp_output_dir = tempfile.mkdtemp()

@app.route('/')
def index():
    """Serve the main page"""
    return render_template('index.html')

@app.route('/health')
def health_check():
    """Health check endpoint for monitoring"""
    return jsonify({
        'status': 'healthy',
        'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ'),
        'version': '1.0.0',
        'environment': 'vercel'
    })

@app.route('/upload', methods=['POST'])
@log_request_duration
@handle_exceptions
def upload_file():
    """Handle file upload and upscaling - Vercel optimized"""
    start_time = time.time()
    
    try:
        # Check if file is present
        if 'file' not in request.files:
            return jsonify(error_handler.validation_error('No file provided')), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify(error_handler.validation_error('No file selected')), 400
        
        # Security validation
        if not security_validator.validate_filename(file.filename):
            return jsonify(error_handler.file_error('Invalid filename')), 400
        
        # Get file extension
        file_ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
        if file_ext not in app.config['ALLOWED_EXTENSIONS']:
            return jsonify(error_handler.file_error(
                f'Invalid file type. Supported formats: {", ".join(app.config["ALLOWED_EXTENSIONS"])}'
            )), 400
        
        # Read file data for validation
        file_data = file.read()
        file.seek(0)  # Reset file pointer
        
        # Validate file signature
        if not security_validator.validate_file_signature(file_data, file_ext):
            return jsonify(error_handler.file_error('File signature does not match extension')), 400
        
        # Check file size
        max_size = security_validator.MAX_FILE_SIZES.get(file_ext, app.config['MAX_CONTENT_LENGTH'])
        if len(file_data) > max_size:
            return jsonify(error_handler.file_error(f'File too large. Maximum size: {max_size // (1024*1024)}MB')), 400
        
        # Get parameters from form
        scale_factor = request.form.get('scale_factor', type=float)
        target_width = request.form.get('target_width', type=int)
        target_height = request.form.get('target_height', type=int)
        interpolation = request.form.get('interpolation', 'ai_enhanced')
        quality = request.form.get('quality', type=int, default=95)
        
        # Validate parameters
        if scale_factor and (scale_factor < 0.1 or scale_factor > app.config['MAX_SCALE_FACTOR']):
            return jsonify(error_handler.validation_error(
                f'Scale factor must be between 0.1 and {app.config["MAX_SCALE_FACTOR"]}'
            )), 400
        
        if target_width and (target_width < 1 or target_width > app.config['MAX_DIMENSION']):
            return jsonify(error_handler.validation_error(
                f'Target width must be between 1 and {app.config["MAX_DIMENSION"]} pixels'
            )), 400
        
        if target_height and (target_height < 1 or target_height > app.config['MAX_DIMENSION']):
            return jsonify(error_handler.validation_error(
                f'Target height must be between 1 and {app.config["MAX_DIMENSION"]} pixels'
            )), 400
        
        if quality < 1 or quality > 100:
            return jsonify(error_handler.validation_error('Quality must be between 1 and 100')), 400
        
        # Generate secure filename
        file_id = str(uuid.uuid4())
        input_filename = f"{file_id}_input.{file_ext}"
        output_filename = f"{file_id}_output.{file_ext}"
        
        # Save uploaded file to temp directory
        input_path = os.path.join(temp_upload_dir, input_filename)
        file.save(input_path)
        
        # Validate image dimensions and content
        img_validation = security_validator.validate_image_dimensions(input_path)
        if not img_validation['valid']:
            os.remove(input_path)  # Clean up
            return jsonify(error_handler.file_error('Invalid image file')), 400
        
        if not img_validation['within_limits']:
            os.remove(input_path)  # Clean up
            return jsonify(error_handler.file_error('Image dimensions exceed maximum limits')), 400
        
        # Check for malicious content
        if security_validator.check_malicious_content(input_path):
            os.remove(input_path)  # Clean up
            return jsonify(error_handler.file_error('Suspicious image content detected')), 400
        
        # Validate scaling parameters
        scale_validation = security_validator.validate_scale_parameters(
            scale_factor, target_width, target_height,
            img_validation['width'], img_validation['height']
        )
        if not scale_validation['valid']:
            os.remove(input_path)  # Clean up
            return jsonify(error_handler.validation_error('; '.join(scale_validation['errors']))), 400
        
        logger.logger.info(f"File uploaded: {file.filename} -> {input_filename}")
        
        # Initialize upscaler
        upscaler = ImageUpscaler()
        
        # Prepare output path
        output_path = os.path.join(temp_output_dir, output_filename)
        
        # Upscale image
        logger.logger.info(f"Starting upscaling with parameters: scale_factor={scale_factor}, interpolation={interpolation}, quality={quality}")
        success = upscaler.upscale_image(
            input_path=input_path,
            output_path=output_path,
            scale_factor=scale_factor,
            target_width=target_width,
            target_height=target_height,
            interpolation=interpolation,
            quality=quality
        )
        
        processing_duration = time.time() - start_time
        logger.log_processing(
            file_id=file_id,
            operation='upscale',
            duration=processing_duration,
            success=success,
            original_size=f"{img_validation['width']}x{img_validation['height']}",
            final_size=f"{scale_validation['final_width']}x{scale_validation['final_height']}",
            interpolation=interpolation
        )
        
        if success:
            # Read the output file and convert to base64 for Vercel
            with open(output_path, 'rb') as f:
                output_data = f.read()
            
            # Convert to base64 for JSON response
            output_base64 = base64.b64encode(output_data).decode('utf-8')
            
            # Clean up files
            os.remove(input_path)
            os.remove(output_path)
            
            return jsonify({
                'success': True,
                'file_id': file_id,
                'original_filename': file.filename,
                'output_filename': output_filename,
                'file_size': len(output_data),
                'original_size': f"{img_validation['width']}x{img_validation['height']}",
                'upscaled_size': f"{scale_validation['final_width']}x{scale_validation['final_height']}",
                'processing_time': round(processing_duration, 2),
                'output_data': output_base64,
                'download_url': f'/download/{file_id}'
            })
        else:
            logger.logger.error("Upscaling failed - cleaning up uploaded file")
            # Clean up uploaded file
            if os.path.exists(input_path):
                os.remove(input_path)
            return jsonify(error_handler.processing_error('Failed to upscale image')), 500
            
    except Exception as e:
        logger.log_error(e, {
            'operation': 'file_upload',
            'filename': file.filename if 'file' in locals() else 'unknown'
        })
        return jsonify(error_handler.processing_error('Server error occurred')), 500

@app.route('/download/<file_id>')
def download_file(file_id):
    """Download the upscaled image - returns base64 data"""
    return jsonify({'error': 'Use the output_data from upload response for Vercel deployment'}), 400

@app.route('/preview/<file_id>')
def preview_file(file_id):
    """Preview the upscaled image - returns base64 data"""
    return jsonify({'error': 'Use the output_data from upload response for Vercel deployment'}), 400

@app.errorhandler(413)
def too_large(e):
    return jsonify(error_handler.file_error('File too large')), 413

@app.errorhandler(404)
def not_found(e):
    return jsonify(error_handler.validation_error('Endpoint not found')), 404

@app.errorhandler(500)
def internal_error(e):
    logger.log_error(e, {'operation': 'internal_error'})
    return jsonify(error_handler.processing_error('Internal server error')), 500

# Security headers
@app.after_request
def add_security_headers(response):
    """Add security headers to all responses"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    return response

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
