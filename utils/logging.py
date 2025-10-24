import os
import logging
import json
from datetime import datetime
from typing import Dict, Any, Optional
import traceback
from functools import wraps
import time

class StructuredLogger:
    """Structured logging for production environments"""
    
    def __init__(self, name: str, level: str = 'INFO'):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, level.upper()))
        
        # Create formatter
        if os.environ.get('FLASK_ENV') == 'production':
            # JSON formatter for production
            formatter = logging.Formatter(
                '{"timestamp": "%(asctime)s", "level": "%(levelname)s", '
                '"logger": "%(name)s", "message": "%(message)s", '
                '"module": "%(module)s", "function": "%(funcName)s", '
                '"line": %(lineno)d}'
            )
        else:
            # Human-readable formatter for development
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
    
    def log_request(self, method: str, path: str, status_code: int, 
                   duration: float, user_agent: str = None, 
                   file_size: int = None, **kwargs):
        """Log HTTP request details"""
        log_data = {
            'event': 'http_request',
            'method': method,
            'path': path,
            'status_code': status_code,
            'duration_ms': round(duration * 1000, 2),
            'user_agent': user_agent,
            'file_size': file_size,
            **kwargs
        }
        
        if status_code >= 400:
            self.logger.warning(json.dumps(log_data))
        else:
            self.logger.info(json.dumps(log_data))
    
    def log_error(self, error: Exception, context: Dict[str, Any] = None):
        """Log error with context"""
        log_data = {
            'event': 'error',
            'error_type': type(error).__name__,
            'error_message': str(error),
            'traceback': traceback.format_exc(),
            'context': context or {}
        }
        self.logger.error(json.dumps(log_data))
    
    def log_processing(self, file_id: str, operation: str, 
                      duration: float, success: bool, **kwargs):
        """Log image processing operations"""
        log_data = {
            'event': 'image_processing',
            'file_id': file_id,
            'operation': operation,
            'duration_ms': round(duration * 1000, 2),
            'success': success,
            **kwargs
        }
        
        if success:
            self.logger.info(json.dumps(log_data))
        else:
            self.logger.error(json.dumps(log_data))

# Global logger instance
logger = StructuredLogger('image_upscaler')

def log_request_duration(f):
    """Decorator to log request duration"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        start_time = time.time()
        result = f(*args, **kwargs)
        duration = time.time() - start_time
        
        # Extract request info if available
        from flask import request
        if request:
            logger.log_request(
                method=request.method,
                path=request.path,
                status_code=getattr(result, 'status_code', 200),
                duration=duration,
                user_agent=request.headers.get('User-Agent'),
                file_size=request.content_length
            )
        
        return result
    return decorated_function

def handle_exceptions(f):
    """Decorator to handle exceptions gracefully"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            logger.log_error(e, {
                'function': f.__name__,
                'args': str(args)[:200],  # Truncate for logging
                'kwargs': str(kwargs)[:200]
            })
            
            from flask import jsonify
            return jsonify({
                'error': 'Internal server error',
                'error_id': str(hash(str(e)))[:8]  # Short error ID for tracking
            }), 500
    
    return decorated_function

class ErrorHandler:
    """Centralized error handling"""
    
    @staticmethod
    def validation_error(message: str, field: str = None) -> Dict[str, Any]:
        """Create validation error response"""
        return {
            'error': 'Validation error',
            'message': message,
            'field': field,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def file_error(message: str, file_type: str = None) -> Dict[str, Any]:
        """Create file-related error response"""
        return {
            'error': 'File error',
            'message': message,
            'file_type': file_type,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def processing_error(message: str, operation: str = None) -> Dict[str, Any]:
        """Create processing error response"""
        return {
            'error': 'Processing error',
            'message': message,
            'operation': operation,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def rate_limit_error(message: str = "Rate limit exceeded") -> Dict[str, Any]:
        """Create rate limit error response"""
        return {
            'error': 'Rate limit exceeded',
            'message': message,
            'retry_after': 3600,  # 1 hour
            'timestamp': datetime.utcnow().isoformat()
        }

# Global error handler instance
error_handler = ErrorHandler()
