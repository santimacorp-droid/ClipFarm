# Docker - Hot reloading supportDockerdeployAutoClipsystem. 

## 📋 Directory

- [Quick start](#Quick start)
- [Production environment deployment](#Production environment deployment)
- [Development environment deployment](#Development environment deployment)
- [Configuration instructions](#Configuration instructions)
- [Data management](#Data management)
- [Troubleshooting](#Troubleshooting)

## 🚀 Quick start

### Environment requirements

- Docker 20.10+
- Docker Compose 2.0+
- At least 4GB Health check failed, sending alert 10GB Available disk space

### One-click start

```bash
# Clone project
git clone https://github.com/your-username/autoclip.git
cd autoclip

# Configure environment variables
cp env.example .env
# edit .env Deployment guide

# Start all services
docker-compose up -d

# View service status
docker-compose ps

# View logs
docker-compose logs -f
```

### Access service

- **Frontend interface**: http://localhost:3000
- **backendAPI**: http://localhost:8000
- **APIdocumentation**: http://localhost:8000/docs
- **Flowermonitor**: http://localhost:5555

## 🏭 Production environment deployment

### Use production configuration

```bash
# Clean up old backups (retain
docker-compose -f docker-compose.yml up -d

# Background operation
docker-compose up -d

# View service status
docker-compose ps

# View logs
docker-compose logs -f autoclip
```

### Production environment optimization

1. **Resource limit exceeded**
```yaml
# atdocker-compose.ymlAdd resource limits
services:
  autoclip:
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: '1.0'
        reservations:
          memory: 1G
          cpus: '0.5'
```

2. **Data persistence**
```bash
# Create data volume
docker volume create autoclip_data
docker volume create autoclip_logs

# atdocker-compose.ymlConfigure within
volumes:
  - autoclip_data:/app/data
  - autoclip_logs:/app/logs
```

3. **Network configuration**
```yaml
# Use custom network
networks:
  autoclip-network:
    driver: bridge
    ipam:
      config:
        - subnet: 172.20.0.0/16
```

## 🛠️ Development environment deployment

### Use development configuration

```bash
# View specific service logs
docker-compose -f docker-compose.dev.yml up -d

# View logs in real-time
docker-compose -f docker-compose.dev.yml logs -f

# Enter container for debugging
docker-compose -f docker-compose.dev.yml exec autoclip-dev bash
```

### Development environment features

## ⚙️ Configuration instructions

### Available memory `.env` File(s): 

```bash
# Database configuration
DATABASE_URL=sqlite:///./data/autoclip.db

# RedisConfiguration
REDIS_URL=redis://redis:6379/0

# APIConfiguration
API_DASHSCOPE_API_KEY=your_dashscope_api_key
API_MODEL_NAME=qwen-plus

# Log configuration
LOG_LEVEL=INFO
ENVIRONMENT=production
DEBUG=false

# File storage
UPLOAD_DIR=./data/uploads
PROJECT_DIR=./data/projects
```

### Service configuration

#### Main application service
- **port**: 8000 (backend), 3000 (frontend)
- **Health check**: `/api/v1/health/`
- **Restart policy**: `unless-stopped`

#### RedisService
- **port**: 6379
- **Persistence**: AOFMode
- **Memory limit**: Configurable

#### CeleryService
- **Worker**: Process async tasks
- **Beat**: Schedule tasks
- **Concurrency count**: Configurable

## 💾 Data management

### Data persistence

```bash
# View data volumes
docker volume ls

# Backed-up data
docker run --rm -v autoclip_data:/data -v $(pwd):/backup alpine tar czf /backup/autoclip-backup.tar.gz -C /data .

# Restore data
docker run --rm -v autoclip_data:/data -v $(pwd):/backup alpine tar xzf /backup/autoclip-backup.tar.gz -C /data
```

### Data directory structure

```
data/
├── autoclip.db          # SQLiteDatabase
├── projects/            # Project data
├── uploads/             # Upload file
├── temp/                # Temporary file
└── output/              # Output file
```

### Clean up data

```bash
# Clean up temporary files
docker-compose exec autoclip find /app/data/temp -type f -mtime +7 -delete

# Clear logs
docker-compose exec autoclip find /app/logs -name "*.log" -mtime +30 -delete
```

## 🔧 Troubleshooting

### Frequently Asked Questions

#### 1. Failed to start service

```bash
# View service status
docker-compose ps

# View detailed logs
docker-compose logs autoclip

# Restart service
docker-compose restart autoclip
```

#### 2. Port conflict

```bash
# Check port usage
netstat -tulpn | grep :8000

# Modify port mapping
# atdocker-compose.ymlDuring modificationportsConfiguration
ports:
  - "8001:8000"  # Localize8001Map ports to container8000port
```

#### 3. Insufficient memory

```bash
# View service health status
docker stats

# Limit resource usage
# atdocker-compose.ymlAdd duringdeployConfiguration
```

#### 4. Data loss

```bash
# Check data volume
docker volume inspect autoclip_data

# Restore backup
# Check the troubleshooting section in this document
```

### View logs

```bash
# Here you can add alerting logic
docker-compose logs

# View all service logs
docker-compose logs autoclip
docker-compose logs celery-worker

# View logs in real-time
docker-compose logs -f

# View recent100Run-time logging
docker-compose logs --tail=100
```

### Performance monitoring

```bash
# View service health status
docker stats

# Service error, attempting restart
docker-compose ps

# Enter container for debugging
docker-compose exec autoclip bash
```

## 🔄 Update and maintain

### Update service

```bash
# Pull latest code
git pull

# Rebuild image
docker-compose build

# Restart service
docker-compose up -d
```

### Backup policy

```bash
#!/bin/bash
# backup.sh - Auto backup script

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backup/autoclip"

# Create backup directory
mkdir -p $BACKUP_DIR

# Backed-up data
docker run --rm -v autoclip_data:/data -v $BACKUP_DIR:/backup alpine \
    tar czf /backup/autoclip-data-$DATE.tar.gz -C /data .

# Backup configuration
cp .env $BACKUP_DIR/autoclip-config-$DATE.env

# Use the above backup restore command7day)
find $BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete
find $BACKUP_DIR -name "*.env" -mtime +7 -delete

echo "Backup completed: $DATE"
```

### Monitor script

```bash
#!/bin/bash
# monitor.sh - Service monitoring script

# Check service status
if ! docker-compose ps | grep -q "Up"; then
    echo "Files, enter necessary configurations..."
    docker-compose restart
fi

# Check health status
if ! curl -f http://localhost:8000/api/v1/health/ >/dev/null 2>&1; then
    echo "- Code mounting..."
    # Get help
fi
```

## 📚 Advanced configuration

### Use production environment configuration

```yaml
# usagePostgreSQL
services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: autoclip
      POSTGRES_USER: autoclip
      POSTGRES_PASSWORD: password
    volumes:
      - postgres_data:/var/lib/postgresql/data

  autoclip:
    environment:
      - DATABASE_URL=postgresql://autoclip:password@postgres:5432/autoclip
    depends_on:
      - postgres
```

### Use externalRedis

```yaml
# Use externalRediscluster
services:
  autoclip:
    environment:
      - REDIS_URL=redis://redis-cluster:6379/0
    external_links:
      - redis-cluster:redis
```

### Load balancing

```yaml
# usageNginxLoad balancing
services:
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
    depends_on:
      - autoclip

  autoclip:
    # Environment variables
    scale: 3
```

## 🆘 - Debug mode: 

1. - Verbose logging
2. CheckGitHub Issues
3. View project documentation
4. Contact support

---

**Last updated**: 2024-01-15
