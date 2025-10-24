from flask import Flask, request, jsonify, render_template, send_file
import os
import uuid
from werkzeug.utils import secure_filename
import logging
from ImageUpscalePython import ImageUpscaler
import tempfile
import shutil

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['OUTPUT_FOLDER'] = 'outputs'

# Create necessary directories
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

# Allowed file extensions
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'bmp', 'tiff', 'tif', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    """Serve the main page"""
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload and upscaling"""
    try:
        # Check if file is present
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'Invalid file type. Supported formats: PNG, JPG, JPEG, BMP, TIFF, WebP'}), 400
        
        # Get parameters from form
        scale_factor = request.form.get('scale_factor', type=float)
        target_width = request.form.get('target_width', type=int)
        target_height = request.form.get('target_height', type=int)
        interpolation = request.form.get('interpolation', 'lanczos')
        quality = request.form.get('quality', type=int, default=95)
        
        # Validate parameters
        if scale_factor and (scale_factor < 0.1 or scale_factor > 10):
            return jsonify({'error': 'Scale factor must be between 0.1 and 10'}), 400
        
        if target_width and (target_width < 1 or target_width > 20000):
            return jsonify({'error': 'Target width must be between 1 and 20000 pixels'}), 400
        
        if target_height and (target_height < 1 or target_height > 20000):
            return jsonify({'error': 'Target height must be between 1 and 20000 pixels'}), 400
        
        if quality < 1 or quality > 100:
            return jsonify({'error': 'Quality must be between 1 and 100'}), 400
        
        # Generate unique filename
        file_id = str(uuid.uuid4())
        filename = secure_filename(file.filename)
        file_ext = filename.rsplit('.', 1)[1].lower()
        input_filename = f"{file_id}_input.{file_ext}"
        output_filename = f"{file_id}_output.{file_ext}"
        
        # Save uploaded file
        input_path = os.path.join(app.config['UPLOAD_FOLDER'], input_filename)
        file.save(input_path)
        
        logger.info(f"File uploaded: {filename} -> {input_filename}")
        
        # Initialize upscaler
        upscaler = ImageUpscaler()
        
        # Prepare output path
        output_path = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)
        
        # Upscale image
        success = upscaler.upscale_image(
            input_path=input_path,
            output_path=output_path,
            scale_factor=scale_factor,
            target_width=target_width,
            target_height=target_height,
            interpolation=interpolation,
            quality=quality
        )
        
        if success:
            # Get file info
            file_size = os.path.getsize(output_path)
            
            return jsonify({
                'success': True,
                'file_id': file_id,
                'original_filename': filename,
                'output_filename': output_filename,
                'file_size': file_size,
                'download_url': f'/download/{file_id}'
            })
        else:
            # Clean up uploaded file
            if os.path.exists(input_path):
                os.remove(input_path)
            return jsonify({'error': 'Failed to upscale image'}), 500
            
    except Exception as e:
        logger.error(f"Error processing file: {e}")
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/download/<file_id>')
def download_file(file_id):
    """Download the upscaled image"""
    try:
        # Find the output file
        output_dir = app.config['OUTPUT_FOLDER']
        for filename in os.listdir(output_dir):
            if filename.startswith(f"{file_id}_output."):
                file_path = os.path.join(output_dir, filename)
                return send_file(file_path, as_attachment=True)
        
        return jsonify({'error': 'File not found'}), 404
        
    except Exception as e:
        logger.error(f"Error downloading file: {e}")
        return jsonify({'error': 'Download failed'}), 500

@app.route('/preview/<file_id>')
def preview_file(file_id):
    """Preview the upscaled image"""
    try:
        # Find the output file
        output_dir = app.config['OUTPUT_FOLDER']
        for filename in os.listdir(output_dir):
            if filename.startswith(f"{file_id}_output."):
                file_path = os.path.join(output_dir, filename)
                return send_file(file_path)
        
        return jsonify({'error': 'File not found'}), 404
        
    except Exception as e:
        logger.error(f"Error previewing file: {e}")
        return jsonify({'error': 'Preview failed'}), 500

@app.route('/cleanup/<file_id>', methods=['DELETE'])
def cleanup_files(file_id):
    """Clean up uploaded and output files"""
    try:
        # Clean up input file
        input_dir = app.config['UPLOAD_FOLDER']
        for filename in os.listdir(input_dir):
            if filename.startswith(f"{file_id}_input."):
                file_path = os.path.join(input_dir, filename)
                if os.path.exists(file_path):
                    os.remove(file_path)
        
        # Clean up output file
        output_dir = app.config['OUTPUT_FOLDER']
        for filename in os.listdir(output_dir):
            if filename.startswith(f"{file_id}_output."):
                file_path = os.path.join(output_dir, filename)
                if os.path.exists(file_path):
                    os.remove(file_path)
        
        return jsonify({'success': True})
        
    except Exception as e:
        logger.error(f"Error cleaning up files: {e}")
        return jsonify({'error': 'Cleanup failed'}), 500

@app.errorhandler(413)
def too_large(e):
    return jsonify({'error': 'File too large. Maximum size is 50MB.'}), 413

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
