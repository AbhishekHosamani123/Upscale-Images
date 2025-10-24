# AI Image Upscaler - Production Ready

A high-performance, production-ready AI-powered image upscaling service built with Flask and OpenCV. Features advanced security, monitoring, rate limiting, and scalable deployment options.

## 🚀 Features

- **AI-Enhanced Upscaling**: Multiple algorithms including AI-enhanced, Lanczos, Cubic, and Super-resolution
- **Production Security**: Input validation, rate limiting, file signature verification, and security headers
- **Scalable Architecture**: Docker containerization with Nginx reverse proxy
- **Monitoring & Health Checks**: Built-in health endpoints and metrics collection
- **Automatic Cleanup**: Background file cleanup to prevent disk space issues
- **Rate Limiting**: Configurable rate limits to prevent abuse
- **Caching**: Response caching for improved performance
- **Structured Logging**: JSON-formatted logs for production monitoring

## 📋 Requirements

- Python 3.11+
- Docker & Docker Compose (for production deployment)
- 2GB+ RAM recommended
- 10GB+ disk space for file storage

## 🛠️ Installation

### Development Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd image-upscaler
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application**
   ```bash
   python app.py
   ```

4. **Access the application**
   - Web Interface: http://localhost:5000
   - Health Check: http://localhost:5000/health
   - Metrics: http://localhost:5000/metrics

### Production Deployment

#### Option 1: Docker Compose (Recommended)

1. **Run the deployment script**
   ```bash
   # Linux/Mac
   ./deploy.sh
   
   # Windows
   deploy.bat
   ```

2. **Manual deployment**
   ```bash
   # Create environment file
   cp .env.production.example .env.production
   # Edit .env.production with your settings
   
   # Start services
   docker-compose up -d
   ```

#### Option 2: Docker Only

```bash
# Build the image
docker build -t image-upscaler .

# Run the container
docker run -d \
  --name image-upscaler \
  -p 5000:5000 \
  -v $(pwd)/uploads:/app/uploads \
  -v $(pwd)/outputs:/app/outputs \
  -e FLASK_ENV=production \
  -e SECRET_KEY=your-secret-key \
  image-upscaler
```

#### Option 3: Traditional Server

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export FLASK_ENV=production
export SECRET_KEY=your-secret-key

# Run with Gunicorn
gunicorn --bind 0.0.0.0:5000 --workers 4 --timeout 120 app:app
```

## ⚙️ Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FLASK_ENV` | `development` | Environment (development/production) |
| `SECRET_KEY` | `dev-secret-key` | Flask secret key |
| `MAX_CONTENT_LENGTH` | `50MB` | Maximum file upload size |
| `MAX_SCALE_FACTOR` | `10.0` | Maximum scale factor |
| `MAX_DIMENSION` | `20000` | Maximum image dimension |
| `RATELIMIT_DEFAULT` | `100 per hour` | Default rate limit |
| `ENABLE_METRICS` | `false` | Enable metrics endpoint |
| `FILE_MAX_AGE` | `86400` | File cleanup age (seconds) |

### Security Configuration

The application includes multiple security layers:

- **Input Validation**: File type, size, and signature verification
- **Rate Limiting**: Per-IP request limits
- **Security Headers**: XSS protection, content type sniffing prevention
- **File Sanitization**: Secure filename handling
- **Malicious Content Detection**: Image content validation

## 📊 API Endpoints

### Web Interface
- `GET /` - Main application interface

### API Endpoints
- `POST /upload` - Upload and upscale image
- `GET /download/<file_id>` - Download upscaled image
- `GET /preview/<file_id>` - Preview upscaled image
- `DELETE /cleanup/<file_id>` - Clean up files

### Monitoring
- `GET /health` - Health check endpoint
- `GET /metrics` - Application metrics (if enabled)

## 🔧 API Usage

### Upload and Upscale

```bash
curl -X POST http://localhost:5000/upload \
  -F "file=@image.jpg" \
  -F "scale_factor=2.0" \
  -F "interpolation=ai_enhanced" \
  -F "quality=95"
```

### Response Format

```json
{
  "success": true,
  "file_id": "uuid-string",
  "original_filename": "image.jpg",
  "output_filename": "uuid_output.jpg",
  "file_size": 1024000,
  "original_size": "800x600",
  "upscaled_size": "1600x1200",
  "processing_time": 2.5,
  "download_url": "/download/uuid-string"
}
```

## 🏥 Health Monitoring

### Health Check Response

```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T00:00:00Z",
  "version": "1.0.0",
  "environment": "production"
}
```

### Metrics Response

```json
{
  "timestamp": "2024-01-01T00:00:00Z",
  "files": {
    "uploads": 5,
    "outputs": 3
  },
  "system": {
    "uptime": 3600
  }
}
```

## 🔒 Security Features

### File Validation
- File signature verification
- File size limits
- Image dimension validation
- Malicious content detection

### Rate Limiting
- Per-IP request limits
- Configurable time windows
- Burst handling

### Security Headers
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Strict-Transport-Security`

## 📈 Performance Optimization

### Caching
- Response caching for static content
- Configurable cache timeouts
- Redis support (optional)

### File Management
- Automatic cleanup of old files
- Background processing
- Disk space management

### Resource Limits
- Memory limits in Docker
- CPU limits
- Request timeouts

## 🐳 Docker Configuration

### Dockerfile Features
- Multi-stage build for smaller images
- Non-root user for security
- Health checks
- Optimized layer caching

### Docker Compose Services
- **image-upscaler**: Main application
- **nginx**: Reverse proxy and load balancer
- **redis**: Caching and rate limiting (optional)

## 📝 Logging

### Structured Logging
- JSON-formatted logs in production
- Request/response logging
- Error tracking with context
- Performance metrics

### Log Levels
- `INFO`: Normal operations
- `WARNING`: Non-critical issues
- `ERROR`: Application errors
- `DEBUG`: Detailed debugging (development only)

## 🔧 Troubleshooting

### Common Issues

1. **Service won't start**
   - Check Docker is running
   - Verify port 5000 is available
   - Check logs: `docker-compose logs image-upscaler`

2. **File upload fails**
   - Check file size limits
   - Verify file format is supported
   - Check disk space

3. **Rate limiting issues**
   - Adjust rate limits in configuration
   - Check IP-based limits

4. **Performance issues**
   - Increase worker processes
   - Add Redis for caching
   - Monitor resource usage

### Debug Mode

Enable debug mode for development:
```bash
export FLASK_ENV=development
export FLASK_DEBUG=True
```

## 🚀 Scaling

### Horizontal Scaling
- Use load balancer (Nginx)
- Multiple application instances
- Shared file storage

### Vertical Scaling
- Increase memory limits
- Add more CPU cores
- Use faster storage

### Database Integration
- Add PostgreSQL/MySQL for metadata
- User session management
- File tracking and analytics

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📞 Support

For support and questions:
- Create an issue on GitHub
- Check the troubleshooting section
- Review the logs for error details