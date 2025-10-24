from flask import Flask, request, jsonify, render_template
import os
import uuid
import time
import base64
import tempfile
from ImageUpscalePython import ImageUpscaler
from werkzeug.utils import secure_filename

# Initialize Flask app
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 25 * 1024 * 1024  # 25MB max file size

# Allowed file extensions
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'bmp', 'tiff', 'tif', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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
def upload_file():
    """Handle file upload and upscaling - Vercel optimized"""
    start_time = time.time()
    
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
        scale_factor = request.form.get('scale_factor', type=float, default=2.0)
        target_width = request.form.get('target_width', type=int)
        target_height = request.form.get('target_height', type=int)
        interpolation = request.form.get('interpolation', 'ai_enhanced')
        quality = request.form.get('quality', type=int, default=95)
        
        # Validate parameters
        if scale_factor and (scale_factor < 0.1 or scale_factor > 5.0):
            return jsonify({'error': 'Scale factor must be between 0.1 and 5.0'}), 400
        
        if target_width and (target_width < 1 or target_width > 10000):
            return jsonify({'error': 'Target width must be between 1 and 10000 pixels'}), 400
        
        if target_height and (target_height < 1 or target_height > 10000):
            return jsonify({'error': 'Target height must be between 1 and 10000 pixels'}), 400
        
        if quality < 1 or quality > 100:
            return jsonify({'error': 'Quality must be between 1 and 100'}), 400
        
        # Generate secure filename
        file_id = str(uuid.uuid4())
        file_ext = file.filename.rsplit('.', 1)[1].lower()
        input_filename = f"{file_id}_input.{file_ext}"
        output_filename = f"{file_id}_output.{file_ext}"
        
        # Save uploaded file to temp directory
        input_path = os.path.join(temp_upload_dir, input_filename)
        file.save(input_path)
        
        print(f"File saved to: {input_path}")
        
        # Initialize upscaler
        upscaler = ImageUpscaler()
        
        # Prepare output path
        output_path = os.path.join(temp_output_dir, output_filename)
        
        print(f"Starting upscaling...")
        
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
        
        processing_duration = time.time() - start_time
        print(f"Upscaling completed: success={success}, duration={processing_duration:.2f}s")
        
        if success:
            # Read the output file and convert to base64 for Vercel
            with open(output_path, 'rb') as f:
                output_data = f.read()
            
            # Convert to base64 for JSON response
            output_base64 = base64.b64encode(output_data).decode('utf-8')
            
            # Clean up files
            try:
                os.remove(input_path)
                os.remove(output_path)
            except:
                pass  # Ignore cleanup errors
            
            return jsonify({
                'success': True,
                'file_id': file_id,
                'original_filename': file.filename,
                'output_filename': output_filename,
                'file_size': len(output_data),
                'processing_time': round(processing_duration, 2),
                'output_data': output_base64,
                'download_url': f'/download/{file_id}'
            })
        else:
            print("Upscaling failed")
            # Clean up uploaded file
            try:
                os.remove(input_path)
            except:
                pass
            return jsonify({'error': 'Failed to upscale image'}), 500
            
    except Exception as e:
        print(f"Exception in upload_file: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Server error: {str(e)}'}), 500

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
    return jsonify({'error': 'File too large'}), 413

@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(e):
    print(f"Internal error: {e}")
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    print("Starting Vercel-optimized Image Upscaler...")
    print(f"Temp upload dir: {temp_upload_dir}")
    print(f"Temp output dir: {temp_output_dir}")
    app.run(debug=True, host='0.0.0.0', port=5000)
