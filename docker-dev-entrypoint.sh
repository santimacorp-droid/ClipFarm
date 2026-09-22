#!/bin/bash

# DockerDevelopment environment startup script
# Designed for development environment, addresses frontend issuesviteIssues

set -euo pipefail

echo "🚀 StartAutoClipDevelopment environment..."

# Set environment variables
export PYTHONPATH=/app
export PYTHONUNBUFFERED=1

# Ensure data directory exists
mkdir -p /app/data/projects /app/data/uploads /app/data/temp /app/data/output /app/logs

# Activate virtual environment
source /app/venv/bin/activate

# Check and install frontend dependencies
echo "📦 Check frontend dependencies..."
cd /app/frontend
if [ ! -d node_modules ] || [ ! -f node_modules/.bin/vite ]; then
    echo "Install frontend dependencies..."
    npm install
fi

# CheckviteIs correctly installed?
if [ ! -f node_modules/.bin/vite ]; then
    echo "❌ viteNot installed correctly, reinstall..."
    npm install vite
fi

# Return to root directory
cd /app

# Start backend service
echo "🔧 Start backend service..."
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# Wait for backend to start
sleep 3

# Start frontend service
echo "🌐 Start frontend service..."
cd /app/frontend
npx vite --host 0.0.0.0 --port 3000 &
FRONTEND_PID=$!

# Return to root directory
cd /app

echo "✅ Service startup complete"
echo "  BackendAPI: http://localhost:8000"
echo "  Frontend interface: http://localhost:3000"

# Wait for all processes
wait