@echo off
REM Production deployment script for Image Upscaler (Windows)
setlocal enabledelayedexpansion

echo 🚀 Starting Image Upscaler Production Deployment

REM Check if Docker is installed
docker --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Docker is not installed. Please install Docker Desktop first.
    pause
    exit /b 1
)

docker-compose --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Docker Compose is not installed. Please install Docker Compose first.
    pause
    exit /b 1
)

REM Create necessary directories
echo 📁 Creating necessary directories...
if not exist "uploads" mkdir uploads
if not exist "outputs" mkdir outputs
if not exist "logs" mkdir logs
if not exist "ssl" mkdir ssl

REM Check if .env.production exists
if not exist ".env.production" (
    echo ⚠️  .env.production not found. Creating from template...
    (
        echo # Environment configuration for production
        echo FLASK_ENV=production
        echo FLASK_DEBUG=False
        echo.
        echo # Security
        echo SECRET_KEY=your-super-secret-key-change-this-in-production
        echo.
        echo # File handling
        echo MAX_CONTENT_LENGTH=25165824
        echo UPLOAD_FOLDER=uploads
        echo OUTPUT_FOLDER=outputs
        echo.
        echo # Processing limits
        echo MAX_SCALE_FACTOR=5.0
        echo MAX_DIMENSION=10000
        echo.
        echo # Rate limiting
        echo RATELIMIT_STORAGE_URL=memory://
        echo RATELIMIT_DEFAULT=50 per hour
        echo.
        echo # Caching
        echo CACHE_TYPE=simple
        echo CACHE_DEFAULT_TIMEOUT=300
        echo.
        echo # Monitoring
        echo ENABLE_METRICS=true
        echo.
        echo # Cleanup
        echo FILE_CLEANUP_INTERVAL=3600
        echo FILE_MAX_AGE=86400
        echo.
        echo # Server settings
        echo HOST=0.0.0.0
        echo PORT=5000
    ) > .env.production
    echo ✅ Created .env.production
)

REM Build and start services
echo 🔨 Building Docker images...
docker-compose build

echo 🚀 Starting services...
docker-compose up -d

REM Wait for services to be ready
echo ⏳ Waiting for services to be ready...
timeout /t 10 /nobreak >nul

REM Check health
echo 🏥 Checking service health...
curl -f http://localhost:5000/health >nul 2>&1
if errorlevel 1 (
    echo ❌ Service health check failed!
    echo 📋 Service logs:
    docker-compose logs image-upscaler
    pause
    exit /b 1
) else (
    echo ✅ Service is healthy!
)

echo 🎉 Deployment completed successfully!
echo 📊 Service is running at: http://localhost
echo 🔍 Health check: http://localhost/health
echo 📈 Metrics: http://localhost/metrics

REM Show running containers
echo 📋 Running containers:
docker-compose ps

pause
