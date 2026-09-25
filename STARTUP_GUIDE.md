# 🚀 ClipFarm Studio — System Startup & Operations Guide

This guide walks you through launching, managing, and troubleshooting the full ClipFarm Studio system across local development and production environments.

---

## 📋 System Architecture Overview

ClipFarm Studio consists of four interconnected services:
- **FastAPI Core (`backend/`)**: RESTful API endpoints, WebSocket progress notifications, and video analysis orchestration on port `8001`.
- **Celery Worker**: Distributed background task queue executing Faster-Whisper ASR, LLM candidate scoring, and FFmpeg render jobs.
- **Redis Server**: High-performance message broker and task result cache on port `6379`.
- **React Frontend (`frontend/`)**: Modern responsive web dashboard built with React 18, TypeScript, and Ant Design on port `3001`.
- **Tauri / Python GUI**: Standalone native desktop application wrappers.

---

## ⚡ Quick Start Options

### Option 1: Consolidated Foreground Runner (Recommended for Testing)
Runs Redis, backend, Celery worker, and frontend dev server together in one terminal:
```bash
./run_all.sh
```
*Press `Ctrl+C` at any time to gracefully stop all services simultaneously.*

### Option 2: Production Background Daemons
Runs backend and worker processes in the background with PID tracking:
```bash
# 1. Start all daemons
./start_clipfarm.sh

# 2. Check health and process status
./status_clipfarm.sh

# 3. Stop all daemons cleanly
./stop_clipfarm.sh
```

---

## 🔧 Environment Requirements & Setup

### System Prerequisites
- **Operating System**: Linux (Ubuntu, Debian, Fedora, Arch) or macOS (Apple Silicon M1–M4 / Intel) or Windows 10/11
- **Python**: 3.10+ (virtual environment recommended)
- **Node.js**: 18+ & `npm`
- **FFmpeg & FFprobe**: Available in system `PATH`
- **Redis Server**: Installed and running

### Step-by-Step Installation

```bash
# 1. Clone the repository
git clone https://github.com/santimacorp-droid/ClipFarm.git
cd ClipFarm

# 2. Create and activate Python virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install backend dependencies
pip install -r requirements.txt

# 4. Install and build frontend
cd frontend
npm install
npm run build
cd ..

# 5. Configure environment variables
cp .env.example .env
```

---

## 🌐 Default Ports & Access Points

| Service | Port | URL / Binding | Description |
| :--- | :--- | :--- | :--- |
| **Studio Web UI** | `3001` | [http://localhost:3001](http://localhost:3001) | Primary creator studio dashboard |
| **Backend API** | `8001` | [http://localhost:8001](http://localhost:8001) | FastAPI core application |
| **Swagger UI** | `8001` | [http://localhost:8001/docs](http://localhost:8001/docs) | Interactive API exploration |
| **Redis Broker** | `6379` | `redis://localhost:6379/0` | Celery message broker |

*(If port conflicts occur, modify `PORT` and `FRONTEND_PORT` inside your `.env` file).*

---

## 🛠️ Service Management & Logs

### Checking System Health
```bash
./status_clipfarm.sh
```
Output inspects:
- Backend PID and `/health` HTTP response
- Celery worker PID and queue status
- Frontend dev server status
- Redis connection availability

### Viewing Service Logs
```bash
# Backend server logs:
tail -f backend.log

# Background Celery task logs:
tail -f worker.log
```

---

## 🐳 Running with Docker

Deploy ClipFarm with a single command without configuring local dependencies:

```bash
# Build and start all services in the background:
docker compose up -d

# Follow container logs:
docker compose logs -f

# Shut down containers:
docker compose down
```

For NVIDIA GPU acceleration in Docker, ensure the NVIDIA Container Toolkit is installed and enable the GPU capabilities section in `docker-compose.yml`.

---

## ❓ Frequently Asked Operational Questions

### How do I restart only the Celery worker?
```bash
kill $(cat celery.pid)
source venv/bin/activate
celery -A backend.tasks.celery_worker worker --loglevel=info --concurrency=2 > worker.log 2>&1 &
echo $! > celery.pid
```

### How do I clean up temporary video cache and logs?
```bash
# Remove temporary downloaded videos and renders:
rm -rf output/* data/temp/*
```

---

<div align="center">
  <sub>ClipFarm Studio • Open-Source Video Automation</sub>
</div>
