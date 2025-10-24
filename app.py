from flask import Flask, request, jsonify, render_template, send_file, g
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_caching import Cache
import os
import uuid
import time
import threading
from datetime import datetime, timedelta
from ImageUpscalePython import ImageUpscaler
from config import get_config
from utils.logging import logger, log_request_duration, handle_exceptions, error_handler
from utils.security import security_validator, rate_limiter

# Initialize Flask app with configuration
config_class = get_config()
app = Flask(__name__)
app.config.from_object(config_class)

# Initialize extensions
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    storage_uri=app.config['RATELIMIT_STORAGE_URL'],
    default_limits=[app.config['RATELIMIT_DEFAULT']]
)

cache = Cache(app, config={
    'CACHE_TYPE': app.config['CACHE_TYPE'],
    'CACHE_DEFAULT_TIMEOUT': app.config['CACHE_DEFAULT_TIMEOUT']
})

# Create necessary directories
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

# File cleanup thread
cleanup_thread = None
cleanup_lock = threading.Lock()

def cleanup_old_files():
    """Clean up old files in background thread"""
    global cleanup_thread
    
    with cleanup_lock:
        if cleanup_thread and cleanup_thread.is_alive():
            return  # Cleanup already running
        
        def cleanup_task():
            try:
                current_time = time.time()
                max_age = app.config['FILE_MAX_AGE']
                
                # Clean up uploads
                for filename in os.listdir(app.config['UPLOAD_FOLDER']):
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    if os.path.isfile(file_path):
                        file_age = current_time - os.path.getmtime(file_path)
                        if file_age > max_age:
                            os.remove(file_path)
                            logger.logger.info(f"Cleaned up old upload file: {filename}")
                
                # Clean up outputs
                for filename in os.listdir(app.config['OUTPUT_FOLDER']):
                    file_path = os.path.join(app.config['OUTPUT_FOLDER'], filename)
                    if os.path.isfile(file_path):
                        file_age = current_time - os.path.getmtime(file_path)
                        if file_age > max_age:
                            os.remove(file_path)
                            logger.logger.info(f"Cleaned up old output file: {filename}")
                            
            except Exception as e:
                logger.log_error(e, {'operation': 'file_cleanup'})
        
        cleanup_thread = threading.Thread(target=cleanup_task, daemon=True)
        cleanup_thread.start()

@app.route('/')
@cache.cached(timeout=300)  # Cache for 5 minutes
def index():
    """Serve the main page"""
    return render_template('index.html')

@app.route('/health')
def health_check():
    """Health check endpoint for monitoring"""
    try:
        # Check if directories exist and are writable
        upload_dir = app.config['UPLOAD_FOLDER']
        output_dir = app.config['OUTPUT_FOLDER']
        
        if not os.path.exists(upload_dir) or not os.path.exists(output_dir):
            return jsonify({'status': 'unhealthy', 'error': 'Directories not accessible'}), 503
        
        # Test file operations
        test_file = os.path.join(upload_dir, f'test_{uuid.uuid4()}.txt')
        try:
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
        except Exception as e:
            return jsonify({'status': 'unhealthy', 'error': f'File operations failed: {str(e)}'}), 503
        
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'version': '1.0.0',
            'environment': os.environ.get('FLASK_ENV', 'development')
        })
    except Exception as e:
        logger.log_error(e, {'operation': 'health_check'})
        return jsonify({'status': 'unhealthy', 'error': 'Internal error'}), 503

@app.route('/metrics')
def metrics():
    """Basic metrics endpoint"""
    if not app.config['ENABLE_METRICS']:
        return jsonify({'error': 'Metrics disabled'}), 404
    
    try:
        # Basic system metrics
        upload_count = len([f for f in os.listdir(app.config['UPLOAD_FOLDER']) if os.path.isfile(os.path.join(app.config['UPLOAD_FOLDER'], f))])
        output_count = len([f for f in os.listdir(app.config['OUTPUT_FOLDER']) if os.path.isfile(os.path.join(app.config['OUTPUT_FOLDER'], f))])
        
        return jsonify({
            'timestamp': datetime.utcnow().isoformat(),
            'files': {
                'uploads': upload_count,
                'outputs': output_count
            },
            'system': {
                'uptime': time.time() - app.start_time if hasattr(app, 'start_time') else 0
            }
        })
    except Exception as e:
        logger.log_error(e, {'operation': 'metrics'})
        return jsonify({'error': 'Failed to collect metrics'}), 500

@app.route('/upload', methods=['POST'])
@app.route('/api/upload', methods=['POST'])
@limiter.limit("10 per minute")  # Rate limiting
@log_request_duration
@handle_exceptions
def upload_file():
    """Handle file upload and upscaling"""
    start_time = time.time()
    
    try:
        # Rate limiting check
        client_ip = get_remote_address()
        rate_check = rate_limiter.is_allowed(client_ip, limit=10, window=3600)
        if not rate_check['allowed']:
            logger.logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            return jsonify(error_handler.rate_limit_error()), 429
        
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
        secure_filename_base = security_validator.sanitize_filename(file.filename)
        input_filename = f"{file_id}_input.{file_ext}"
        output_filename = f"{file_id}_output.{file_ext}"
        
        # Save uploaded file
        input_path = os.path.join(app.config['UPLOAD_FOLDER'], input_filename)
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
        output_path = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)
        
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
            # Get file info
            file_size = os.path.getsize(output_path)
            
            # Schedule cleanup
            cleanup_old_files()
            
            return jsonify({
                'success': True,
                'file_id': file_id,
                'original_filename': file.filename,
                'output_filename': output_filename,
                'file_size': file_size,
                'original_size': f"{img_validation['width']}x{img_validation['height']}",
                'upscaled_size': f"{scale_validation['final_width']}x{scale_validation['final_height']}",
                'processing_time': round(processing_duration, 2),
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
            'filename': file.filename if 'file' in locals() else 'unknown',
            'client_ip': get_remote_address()
        })
        return jsonify(error_handler.processing_error('Server error occurred')), 500

@app.route('/download/<file_id>')
@limiter.limit("20 per minute")
@log_request_duration
@handle_exceptions
def download_file(file_id):
    """Download the upscaled image"""
    try:
        # Validate file_id format
        if not file_id or len(file_id) != 36:  # UUID length
            return jsonify(error_handler.validation_error('Invalid file ID')), 400
        
        # Find the output file
        output_dir = app.config['OUTPUT_FOLDER']
        for filename in os.listdir(output_dir):
            if filename.startswith(f"{file_id}_output."):
                file_path = os.path.join(output_dir, filename)
                if os.path.exists(file_path):
                    return send_file(file_path, as_attachment=True)
        
        return jsonify(error_handler.file_error('File not found')), 404
        
    except Exception as e:
        logger.log_error(e, {'operation': 'file_download', 'file_id': file_id})
        return jsonify(error_handler.processing_error('Download failed')), 500

@app.route('/preview/<file_id>')
@limiter.limit("30 per minute")
@log_request_duration
@handle_exceptions
def preview_file(file_id):
    """Preview the upscaled image"""
    try:
        # Validate file_id format
        if not file_id or len(file_id) != 36:  # UUID length
            return jsonify(error_handler.validation_error('Invalid file ID')), 400
        
        # Find the output file
        output_dir = app.config['OUTPUT_FOLDER']
        for filename in os.listdir(output_dir):
            if filename.startswith(f"{file_id}_output."):
                file_path = os.path.join(output_dir, filename)
                if os.path.exists(file_path):
                    return send_file(file_path)
        
        return jsonify(error_handler.file_error('File not found')), 404
        
    except Exception as e:
        logger.log_error(e, {'operation': 'file_preview', 'file_id': file_id})
        return jsonify(error_handler.processing_error('Preview failed')), 500

@app.route('/cleanup/<file_id>', methods=['DELETE'])
@limiter.limit("5 per minute")
@log_request_duration
@handle_exceptions
def cleanup_files(file_id):
    """Clean up uploaded and output files"""
    try:
        # Validate file_id format
        if not file_id or len(file_id) != 36:  # UUID length
            return jsonify(error_handler.validation_error('Invalid file ID')), 400
        
        files_removed = 0
        
        # Clean up input file
        input_dir = app.config['UPLOAD_FOLDER']
        for filename in os.listdir(input_dir):
            if filename.startswith(f"{file_id}_input."):
                file_path = os.path.join(input_dir, filename)
                if os.path.exists(file_path):
                    os.remove(file_path)
                    files_removed += 1
        
        # Clean up output file
        output_dir = app.config['OUTPUT_FOLDER']
        for filename in os.listdir(output_dir):
            if filename.startswith(f"{file_id}_output."):
                file_path = os.path.join(output_dir, filename)
                if os.path.exists(file_path):
                    os.remove(file_path)
                    files_removed += 1
        
        logger.logger.info(f"Cleaned up {files_removed} files for file_id: {file_id}")
        return jsonify({'success': True, 'files_removed': files_removed})
        
    except Exception as e:
        logger.log_error(e, {'operation': 'file_cleanup', 'file_id': file_id})
        return jsonify(error_handler.processing_error('Cleanup failed')), 500

@app.errorhandler(413)
def too_large(e):
    return jsonify(error_handler.file_error('File too large')), 413

@app.errorhandler(429)
def rate_limit_handler(e):
    return jsonify(error_handler.rate_limit_error()), 429

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
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    return response

if __name__ == '__main__':
    # Set startup time for metrics
    app.start_time = time.time()
    
    # Start cleanup thread
    cleanup_old_files()
    
    # Determine host and port
    host = os.environ.get('HOST', '0.0.0.0')
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    logger.logger.info(f"Starting Image Upscaler server on {host}:{port}")
    logger.logger.info(f"Environment: {os.environ.get('FLASK_ENV', 'development')}")
    logger.logger.info(f"Debug mode: {debug}")
    
    app.run(debug=debug, host=host, port=port)
