import os
import re
import hashlib
import secrets
from typing import Optional, Dict, Any
from werkzeug.utils import secure_filename
from PIL import Image
import cv2
import numpy as np

class SecurityValidator:
    """Security validation utilities"""
    
    # File signature patterns for validation
    FILE_SIGNATURES = {
        'png': [b'\x89PNG\r\n\x1a\n'],
        'jpg': [b'\xff\xd8\xff\xe0', b'\xff\xd8\xff\xe1', b'\xff\xd8\xff\xdb'],
        'jpeg': [b'\xff\xd8\xff\xe0', b'\xff\xd8\xff\xe1', b'\xff\xd8\xff\xdb'],
        'bmp': [b'BM'],
        'tiff': [b'II*\x00', b'MM\x00*'],
        'webp': [b'RIFF', b'WEBP']
    }
    
    # Maximum file sizes by type (in bytes)
    MAX_FILE_SIZES = {
        'png': 50 * 1024 * 1024,  # 50MB
        'jpg': 25 * 1024 * 1024,  # 25MB
        'jpeg': 25 * 1024 * 1024,  # 25MB
        'bmp': 100 * 1024 * 1024,  # 100MB
        'tiff': 200 * 1024 * 1024,  # 200MB
        'webp': 30 * 1024 * 1024   # 30MB
    }
    
    @staticmethod
    def validate_filename(filename: str) -> bool:
        """Validate filename for security"""
        if not filename or len(filename) > 255:
            return False
        
        # Check for dangerous patterns
        dangerous_patterns = [
            r'\.\.',  # Path traversal
            r'[<>:"|?*]',  # Invalid characters
            r'^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])$',  # Windows reserved names
            r'^\.',  # Hidden files
            r'\.(exe|bat|cmd|scr|pif|com)$'  # Executable extensions
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, filename, re.IGNORECASE):
                return False
        
        return True
    
    @staticmethod
    def validate_file_signature(file_data: bytes, expected_ext: str) -> bool:
        """Validate file signature matches extension"""
        if expected_ext.lower() not in SecurityValidator.FILE_SIGNATURES:
            return False
        
        signatures = SecurityValidator.FILE_SIGNATURES[expected_ext.lower()]
        return any(file_data.startswith(sig) for sig in signatures)
    
    @staticmethod
    def validate_image_dimensions(image_path: str, max_width: int = 20000, 
                                 max_height: int = 20000) -> Dict[str, Any]:
        """Validate image dimensions"""
        try:
            with Image.open(image_path) as img:
                width, height = img.size
                
                return {
                    'valid': True,
                    'width': width,
                    'height': height,
                    'aspect_ratio': width / height,
                    'pixel_count': width * height,
                    'within_limits': width <= max_width and height <= max_height
                }
        except Exception as e:
            return {
                'valid': False,
                'error': str(e)
            }
    
    @staticmethod
    def validate_scale_parameters(scale_factor: Optional[float] = None,
                                target_width: Optional[int] = None,
                                target_height: Optional[int] = None,
                                original_width: int = 1,
                                original_height: int = 1) -> Dict[str, Any]:
        """Validate scaling parameters"""
        errors = []
        
        if scale_factor is not None:
            if scale_factor < 0.1 or scale_factor > 10:
                errors.append("Scale factor must be between 0.1 and 10")
        
        if target_width is not None:
            if target_width < 1 or target_width > 20000:
                errors.append("Target width must be between 1 and 20000 pixels")
        
        if target_height is not None:
            if target_height < 1 or target_height > 20000:
                errors.append("Target height must be between 1 and 20000 pixels")
        
        # Calculate final dimensions
        if scale_factor:
            final_width = int(original_width * scale_factor)
            final_height = int(original_height * scale_factor)
        elif target_width and target_height:
            final_width = target_width
            final_height = target_height
        elif target_width:
            aspect_ratio = original_height / original_width
            final_width = target_width
            final_height = int(target_width * aspect_ratio)
        elif target_height:
            aspect_ratio = original_width / original_height
            final_width = int(target_height * aspect_ratio)
            final_height = target_height
        else:
            final_width = original_width * 2
            final_height = original_height * 2
        
        # Check final dimensions
        if final_width > 20000 or final_height > 20000:
            errors.append("Final image dimensions exceed maximum limit (20000x20000)")
        
        pixel_count = final_width * final_height
        if pixel_count > 400_000_000:  # 400 megapixels
            errors.append("Final image pixel count exceeds maximum limit")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'final_width': final_width,
            'final_height': final_height,
            'pixel_count': pixel_count
        }
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize filename for safe storage"""
        # Remove path components
        filename = os.path.basename(filename)
        
        # Secure the filename
        filename = secure_filename(filename)
        
        # Add random prefix to prevent conflicts
        random_prefix = secrets.token_hex(4)
        name, ext = os.path.splitext(filename)
        
        return f"{random_prefix}_{name}{ext}"
    
    @staticmethod
    def generate_file_hash(file_data: bytes) -> str:
        """Generate SHA-256 hash of file data"""
        return hashlib.sha256(file_data).hexdigest()
    
    @staticmethod
    def check_malicious_content(image_path: str) -> bool:
        """Check for potentially malicious image content"""
        try:
            # Try to load with OpenCV
            img = cv2.imread(image_path)
            if img is None:
                return True  # Suspicious if can't load
            
            # Check for extremely large dimensions that might cause DoS
            height, width = img.shape[:2]
            if width > 50000 or height > 50000:
                return True
            
            # Check for unusual aspect ratios
            aspect_ratio = width / height
            if aspect_ratio > 100 or aspect_ratio < 0.01:
                return True
            
            return False
            
        except Exception:
            return True  # Suspicious if any error occurs

class RateLimiter:
    """Simple in-memory rate limiter"""
    
    def __init__(self):
        self.requests = {}
        self.cleanup_interval = 3600  # 1 hour
        self.last_cleanup = 0
    
    def is_allowed(self, identifier: str, limit: int = 100, 
                  window: int = 3600) -> Dict[str, Any]:
        """Check if request is allowed based on rate limit"""
        current_time = time.time()
        
        # Cleanup old entries periodically
        if current_time - self.last_cleanup > self.cleanup_interval:
            self._cleanup_old_entries(current_time, window)
            self.last_cleanup = current_time
        
        # Get or create request history for identifier
        if identifier not in self.requests:
            self.requests[identifier] = []
        
        request_times = self.requests[identifier]
        
        # Remove old requests outside the window
        cutoff_time = current_time - window
        request_times[:] = [t for t in request_times if t > cutoff_time]
        
        # Check if limit exceeded
        if len(request_times) >= limit:
            return {
                'allowed': False,
                'limit': limit,
                'remaining': 0,
                'reset_time': min(request_times) + window
            }
        
        # Add current request
        request_times.append(current_time)
        
        return {
            'allowed': True,
            'limit': limit,
            'remaining': limit - len(request_times),
            'reset_time': current_time + window
        }
    
    def _cleanup_old_entries(self, current_time: float, window: int):
        """Clean up old entries to prevent memory leaks"""
        cutoff_time = current_time - window
        for identifier in list(self.requests.keys()):
            self.requests[identifier] = [
                t for t in self.requests[identifier] if t > cutoff_time
            ]
            if not self.requests[identifier]:
                del self.requests[identifier]

# Global instances
security_validator = SecurityValidator()
rate_limiter = RateLimiter()
