# AutoClip System startup guide

## 📋 Overview

AutoClip is based onAIVideo slicing processing system using front-end/backend separation architecture. This guide will help you quickly start and run the entire system. 

## 🚀 Quick start

### 1. One-click startup (recommended))

```bash
# Full startup (includes detailed checks and health monitoring))
./start_autoclip.sh

# Quick startup (development environment, skip detailed checks))
./quick_start.sh
```

### 2. System management

```bash
# Check system status
./status_autoclip.sh

# Stop all services
./stop_autoclip.sh
```

## 📊 System architecture

### Backend service
- **FastAPI**: RESTful API And WebSocket Support
- **Celery**: Asynchronous task queue
- **Redis**: Message broker and cache
- **SQLite**: Data storage

### Frontend service
- **React**: User interface
- **Vite**: Development server
- **TypeScript**: Type safety

## 🔧 Environment requirements

### System requirements
- macOS Or Linux
- Python 3.8+
- Node.js 16+
- Redis Server

### Dependency installation

```bash
# 1. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 2. InstallPythonDependencies
pip install -r requirements.txt

# 3. Install front-end dependencies
cd frontend
npm install
cd ..

# 4. InstallRedis(macOS)
brew install redis
brew services start redis

# 5. Configure environment variables
cp env.example .env
# Edit .env File, enter necessary configurations
```

## 📝 Configuration file

### Environment variables (.env)

```bash
# Database configuration
DATABASE_URL=sqlite:///./data/autoclip.db

# RedisConfiguration
REDIS_URL=redis://localhost:6379/0

# APIConfiguration
API_DASHSCOPE_API_KEY=your_api_key_here
API_MODEL_NAME=qwen-plus

# Logging configuration
LOG_LEVEL=INFO
ENVIRONMENT=development
DEBUG=true
```

## 🌐 Service port

| Service | Port | Description |
|------|------|------|
| Frontend interface | 3000 | React Development server |
| Backend(s)API | 8000 | FastAPI Server |
| Redis | 6379 | Message broker |
| APIDocument(s) | 8000/docs | Swagger UI |

## 📁 Directory structure

```
autoclip/
├── backend/                 # Backend code
│   ├── api/                # APIRoute(s)
│   ├── core/               # Core configuration
│   ├── models/             # Data model
│   ├── services/           # Business logic
│   └── tasks/              # CeleryTask
├── frontend/               # Frontend code
│   ├── src/                # Source code
│   └── public/             # Static resources
├── data/                   # Data storage
│   ├── projects/           # Project data
│   └── uploads/            # File upload
├── logs/                   # Log file
├── scripts/                # Utility scripts
└── *.sh                    # Startup script
```

## 🔍 Troubleshooting

### Frequently asked questions

1. **Port is in use**
   ```bash
   # Check port usage
   lsof -i :8000
   lsof -i :3000
   
   # Stop processes using ports
   kill -9 <PID>
   ```

2. **RedisConnection failed**
   ```bash
   # CheckRedisStatus
   redis-cli ping
   
   # Startup/launchingRedis
   brew services start redis  # macOS
   systemctl start redis      # Linux
   ```

3. **PythonDependency issues**
   ```bash
   # Reinstall dependencies
   pip install -r requirements.txt --force-reinstall
   ```

4. **Front-end dependency issues**
   ```bash
   # Clean and reinstall
   cd frontend
   rm -rf node_modules package-lock.json
   npm install
   ```

### Log viewing

```bash
# View all logs
tail -f logs/*.log

# View specific service logs
tail -f logs/backend.log
tail -f logs/frontend.log
tail -f logs/celery.log
```

### System status check

```bash
# Detailed status check
./status_autoclip.sh

# Manually check services
curl http://localhost:8000/api/v1/health/
curl http://localhost:3000/
redis-cli ping
```

## 🛠️ Development mode

### Backend development

```bash
# Activate virtual environment
source venv/bin/activate

# Set(s)PythonPath(s)
export PYTHONPATH="${PWD}:${PYTHONPATH}"

# Start backend (development mode))
python -m uvicorn backend.main:app --reload --port 8000
```

### Frontend development

```bash
# Enter front-end directory
cd frontend

# Start development server
npm run dev
```

### Celery Worker

```bash
# Startup/launchingWorker
celery -A backend.core.celery_app worker --loglevel=info

# Startup/launchingBeatScheduler
celery -A backend.core.celery_app beat --loglevel=info

# Startup/launchingFlowerMonitor
celery -A backend.core.celery_app flower --port=5555
```

## 📈 Performance optimization

### Production environment configuration

1. **Database optimization**
   - UsagePostgreSQLAlternativeSQLite
   - Configure connection pool

2. **RedisOptimize/optimization**
   - Configure memory limit

3. **CeleryOptimize/optimization**
   - Adjust concurrency

## 🔒 Security configuration

### Production environment security

1. **Environment variables**
   - Use strong passwordsAPIAccess

2. **Network security**
   - Configure firewallHTTPS
   - LimitCORS

3. **Data security**
   - Regular backups

## 📞 Support: 

1. View log file
2. Run status check script
3. Check environment configuration
4. See troubleshooting section

## 📄 License MIT License. 
