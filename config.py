import os
from typing import Optional

class Config:
    """Base configuration class"""
    # Security
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # File handling
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 50 * 1024 * 1024))  # 50MB
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'uploads')
    OUTPUT_FOLDER = os.environ.get('OUTPUT_FOLDER', 'outputs')
    
    # Allowed file extensions
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'bmp', 'tiff', 'tif', 'webp'}
    
    # Processing limits
    MAX_SCALE_FACTOR = float(os.environ.get('MAX_SCALE_FACTOR', 10.0))
    MAX_DIMENSION = int(os.environ.get('MAX_DIMENSION', 20000))
    
    # Rate limiting
    RATELIMIT_STORAGE_URL = os.environ.get('RATELIMIT_STORAGE_URL', 'memory://')
    RATELIMIT_DEFAULT = os.environ.get('RATELIMIT_DEFAULT', '100 per hour')
    
    # Caching
    CACHE_TYPE = os.environ.get('CACHE_TYPE', 'simple')
    CACHE_DEFAULT_TIMEOUT = int(os.environ.get('CACHE_DEFAULT_TIMEOUT', 300))
    
    # Database
    DATABASE_URL = os.environ.get('DATABASE_URL')
    
    # Monitoring
    ENABLE_METRICS = os.environ.get('ENABLE_METRICS', 'false').lower() == 'true'
    
    # Cleanup
    FILE_CLEANUP_INTERVAL = int(os.environ.get('FILE_CLEANUP_INTERVAL', 3600))  # 1 hour
    FILE_MAX_AGE = int(os.environ.get('FILE_MAX_AGE', 86400))  # 24 hours

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False
    
    # Stricter limits for production
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 25 * 1024 * 1024))  # 25MB
    MAX_SCALE_FACTOR = float(os.environ.get('MAX_SCALE_FACTOR', 5.0))
    MAX_DIMENSION = int(os.environ.get('MAX_DIMENSION', 10000))
    
    # Production security
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    DEBUG = True
    WTF_CSRF_ENABLED = False

# Configuration mapping
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

def get_config(config_name: Optional[str] = None) -> Config:
    """Get configuration based on environment"""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'default')
    
    return config.get(config_name, DevelopmentConfig)
