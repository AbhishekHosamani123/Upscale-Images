from flask import Flask, request, jsonify
import os
import uuid
import time
import base64
import tempfile
from werkzeug.utils import secure_filename

# Initialize Flask app
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 25 * 1024 * 1024  # 25MB max file size

# Allowed file extensions
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'bmp', 'tiff', 'tif', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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
        'environment': 'debug'
    })

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload and upscaling - Debug version"""
    start_time = time.time()
    
    try:
        print("=== UPLOAD REQUEST START ===")
        
        # Check if file is present
        if 'file' not in request.files:
            print("ERROR: No file in request")
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            print("ERROR: Empty filename")
            return jsonify({'error': 'No file selected'}), 400
        
        print(f"File received: {file.filename}")
        
        if not allowed_file(file.filename):
            print(f"ERROR: Invalid file type: {file.filename}")
            return jsonify({'error': 'Invalid file type. Supported formats: PNG, JPG, JPEG, BMP, TIFF, WebP'}), 400
        
        # Get parameters from form
        scale_factor = request.form.get('scale_factor', type=float, default=2.0)
        target_width = request.form.get('target_width', type=int)
        target_height = request.form.get('target_height', type=int)
        interpolation = request.form.get('interpolation', 'ai_enhanced')
        quality = request.form.get('quality', type=int, default=95)
        
        print(f"Parameters: scale_factor={scale_factor}, interpolation={interpolation}, quality={quality}")
        
        # Validate parameters
        if scale_factor and (scale_factor < 0.1 or scale_factor > 5.0):
            print(f"ERROR: Invalid scale factor: {scale_factor}")
            return jsonify({'error': 'Scale factor must be between 0.1 and 5.0'}), 400
        
        # Generate secure filename
        file_id = str(uuid.uuid4())
        file_ext = file.filename.rsplit('.', 1)[1].lower()
        input_filename = f"{file_id}_input.{file_ext}"
        
        # Create temp directory
        temp_dir = tempfile.mkdtemp()
        input_path = os.path.join(temp_dir, input_filename)
        
        print(f"Saving file to: {input_path}")
        
        # Save uploaded file
        file.save(input_path)
        
        print(f"File saved successfully")
        
        # Test if we can import ImageUpscalePython
        try:
            print("Testing ImageUpscalePython import...")
            from ImageUpscalePython import ImageUpscaler
            print("ImageUpscalePython imported successfully")
            
            # Initialize upscaler
            upscaler = ImageUpscaler()
            print("ImageUpscaler initialized successfully")
            
            # Test basic functionality
            output_filename = f"{file_id}_output.{file_ext}"
            output_path = os.path.join(temp_dir, output_filename)
            
            print(f"Starting upscaling to: {output_path}")
            
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
            
            if success and os.path.exists(output_path):
                # Read the output file and convert to base64
                with open(output_path, 'rb') as f:
                    output_data = f.read()
                
                # Convert to base64 for JSON response
                output_base64 = base64.b64encode(output_data).decode('utf-8')
                
                print(f"Success! Output size: {len(output_data)} bytes")
                
                # Clean up files
                try:
                    os.remove(input_path)
                    os.remove(output_path)
                    os.rmdir(temp_dir)
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
                print("Upscaling failed or output file not created")
                # Clean up uploaded file
                try:
                    os.remove(input_path)
                    os.rmdir(temp_dir)
                except:
                    pass
                return jsonify({'error': 'Failed to upscale image'}), 500
                
        except Exception as e:
            print(f"ERROR in ImageUpscalePython: {e}")
            import traceback
            traceback.print_exc()
            
            # Clean up uploaded file
            try:
                os.remove(input_path)
                os.rmdir(temp_dir)
            except:
                pass
            
            return jsonify({'error': f'Image processing error: {str(e)}'}), 500
            
    except Exception as e:
        print(f"EXCEPTION in upload_file: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Server error: {str(e)}'}), 500

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
    print("Starting DEBUG Image Upscaler...")
    app.run(debug=True, host='0.0.0.0', port=5001)
