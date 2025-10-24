#!/bin/bash

# Production deployment script for Image Upscaler
set -e

echo "🚀 Starting Image Upscaler Production Deployment"

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Create necessary directories
echo "📁 Creating necessary directories..."
mkdir -p uploads outputs logs ssl

# Set proper permissions
echo "🔐 Setting permissions..."
chmod 755 uploads outputs logs
chmod 700 ssl

# Check if .env.production exists
if [ ! -f .env.production ]; then
    echo "⚠️  .env.production not found. Creating from template..."
    cat > .env.production << EOF
# Environment configuration for production
FLASK_ENV=production
FLASK_DEBUG=False

# Security
SECRET_KEY=$(openssl rand -hex 32)

# File handling
MAX_CONTENT_LENGTH=25165824
UPLOAD_FOLDER=uploads
OUTPUT_FOLDER=outputs

# Processing limits
MAX_SCALE_FACTOR=5.0
MAX_DIMENSION=10000

# Rate limiting
RATELIMIT_STORAGE_URL=memory://
RATELIMIT_DEFAULT=50 per hour

# Caching
CACHE_TYPE=simple
CACHE_DEFAULT_TIMEOUT=300

# Monitoring
ENABLE_METRICS=true

# Cleanup
FILE_CLEANUP_INTERVAL=3600
FILE_MAX_AGE=86400

# Server settings
HOST=0.0.0.0
PORT=5000
EOF
    echo "✅ Created .env.production with random SECRET_KEY"
fi

# Build and start services
echo "🔨 Building Docker images..."
docker-compose build

echo "🚀 Starting services..."
docker-compose up -d

# Wait for services to be ready
echo "⏳ Waiting for services to be ready..."
sleep 10

# Check health
echo "🏥 Checking service health..."
if curl -f http://localhost:5000/health > /dev/null 2>&1; then
    echo "✅ Service is healthy!"
else
    echo "❌ Service health check failed!"
    echo "📋 Service logs:"
    docker-compose logs image-upscaler
    exit 1
fi

echo "🎉 Deployment completed successfully!"
echo "📊 Service is running at: http://localhost"
echo "🔍 Health check: http://localhost/health"
echo "📈 Metrics: http://localhost/metrics"

# Show running containers
echo "📋 Running containers:"
docker-compose ps
