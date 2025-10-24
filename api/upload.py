from http.server import BaseHTTPRequestHandler
import json
import os
import uuid
import base64
import cv2
import numpy as np
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ImageUpscaler:
    """Simplified Image Upscaler for Vercel deployment"""
    
    def __init__(self):
        self.interpolation_methods = {
            'cubic': cv2.INTER_CUBIC,
            'lanczos': cv2.INTER_LANCZOS4,
            'linear': cv2.INTER_LINEAR,
            'area': cv2.INTER_AREA,
            'nearest': cv2.INTER_NEAREST,
            'ai_enhanced': 'ai_enhanced',
            'super_resolution': 'super_resolution'
        }
    
    def apply_ai_enhancement(self, img: np.ndarray, scale_factor: float) -> np.ndarray:
        """Apply AI-powered enhancement techniques"""
        try:
            # Step 1: Noise reduction using bilateral filter
            img_denoised = cv2.bilateralFilter(img, 9, 75, 75)
            
            # Step 2: Edge enhancement using unsharp masking
            gaussian = cv2.GaussianBlur(img_denoised, (0, 0), 2.0)
            img_enhanced = cv2.addWeighted(img_denoised, 1.5, gaussian, -0.5, 0)
            
            # Step 3: Contrast enhancement using CLAHE
            lab = cv2.cvtColor(img_enhanced, cv2.COLOR_BGR2LAB)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            lab[:,:,0] = clahe.apply(lab[:,:,0])
            img_contrast = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
            
            # Step 4: Detail enhancement
            img_detail = self._enhance_details_fast(img_contrast)
            
            return img_detail
            
        except Exception as e:
            logger.warning(f"AI enhancement failed, using fallback: {e}")
            return self._apply_enhanced_sharpening(img)
    
    def _enhance_details_fast(self, img: np.ndarray) -> np.ndarray:
        """Fast detail enhancement using OpenCV"""
        try:
            # Convert to grayscale for processing
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Apply Laplacian for edge detection
            laplacian = cv2.Laplacian(gray, cv2.CV_64F)
            laplacian = np.uint8(np.absolute(laplacian))
            
            # Create enhancement mask
            kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
            enhanced = cv2.filter2D(img, -1, kernel)
            
            # Blend original with enhanced version
            result = cv2.addWeighted(img, 0.7, enhanced, 0.3, 0)
            
            return np.clip(result, 0, 255).astype(np.uint8)
            
        except Exception as e:
            logger.warning(f"Detail enhancement failed: {e}")
            return img
    
    def _apply_enhanced_sharpening(self, img: np.ndarray) -> np.ndarray:
        """Apply enhanced sharpening with multiple techniques"""
        try:
            # Method 1: Unsharp masking
            gaussian = cv2.GaussianBlur(img, (0, 0), 2.0)
            unsharp_mask = cv2.addWeighted(img, 1.5, gaussian, -0.5, 0)
            
            # Method 2: Laplacian sharpening
            laplacian = cv2.Laplacian(img, cv2.CV_64F)
            laplacian_sharpened = img.astype(np.float64) + 0.3 * laplacian
            
            # Combine methods
            result = cv2.addWeighted(unsharp_mask, 0.7, laplacian_sharpened.astype(np.uint8), 0.3, 0)
            
            return np.clip(result, 0, 255).astype(np.uint8)
            
        except Exception as e:
            logger.warning(f"Sharpening failed: {e}")
            return img

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/api/upload':
            self.handle_upload()
        else:
            self.send_error(404, "Not Found")
    
    def handle_upload(self):
        try:
            # Parse request
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            # Parse multipart form data
            boundary = self.headers['Content-Type'].split('boundary=')[1]
            parts = post_data.split(f'--{boundary}'.encode())
            
            file_data = None
            scale_factor = 2.0
            interpolation = 'ai_enhanced'
            quality = 95
            
            for part in parts:
                if b'Content-Disposition: form-data' in part:
                    if b'name="file"' in part:
                        # Extract file data
                        file_start = part.find(b'\r\n\r\n') + 4
                        file_data = part[file_start:-2]  # Remove trailing \r\n
                    elif b'name="scale_factor"' in part:
                        value_start = part.find(b'\r\n\r\n') + 4
                        scale_factor = float(part[value_start:-2])
                    elif b'name="interpolation"' in part:
                        value_start = part.find(b'\r\n\r\n') + 4
                        interpolation = part[value_start:-2].decode()
                    elif b'name="quality"' in part:
                        value_start = part.find(b'\r\n\r\n') + 4
                        quality = int(part[value_start:-2])
            
            if not file_data:
                self.send_error(400, "No file provided")
                return
            
            # Decode image from bytes
            nparr = np.frombuffer(file_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if img is None:
                self.send_error(400, "Invalid image file")
                return
            
            # Initialize upscaler
            upscaler = ImageUpscaler()
            
            # Calculate target size
            height, width = img.shape[:2]
            new_height, new_width = int(height * scale_factor), int(width * scale_factor)
            
            # Upscale image
            if interpolation == 'ai_enhanced':
                # First upscale with Lanczos
                upscaled_img = cv2.resize(img, (new_width, new_height), interpolation=cv2.INTER_LANCZOS4)
                # Then apply AI enhancement
                upscaled_img = upscaler.apply_ai_enhancement(upscaled_img, scale_factor)
            else:
                # Traditional interpolation methods
                interp_method = upscaler.interpolation_methods.get(interpolation, cv2.INTER_LANCZOS4)
                upscaled_img = cv2.resize(img, (new_width, new_height), interpolation=interp_method)
                if interpolation in ['cubic', 'lanczos']:
                    upscaled_img = upscaler._apply_enhanced_sharpening(upscaled_img)
            
            # Encode result as PNG
            success, encoded_img = cv2.imencode('.png', upscaled_img)
            
            if success:
                # Convert to base64
                output_base64 = base64.b64encode(encoded_img).decode()
                
                # Send response
                response = {
                    'success': True,
                    'file_id': str(uuid.uuid4()),
                    'output_data': output_base64,
                    'file_size': len(encoded_img),
                    'original_size': f"{width}x{height}",
                    'upscaled_size': f"{new_width}x{new_height}"
                }
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
                self.send_header('Access-Control-Allow-Headers', 'Content-Type')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())
                
            else:
                self.send_error(500, "Failed to encode upscaled image")
                
        except Exception as e:
            logger.error(f"Error in upload handler: {e}")
            self.send_error(500, f"Server error: {str(e)}")
    
    def do_OPTIONS(self):
        # Handle CORS preflight requests
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
