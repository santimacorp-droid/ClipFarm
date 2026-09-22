#!/bin/bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

source venv/bin/activate

export BACKEND_PORT=8001
export FRONTEND_PORT=3001
export PYTHONPATH="${DIR}:${PYTHONPATH:-}"

mkdir -p logs

echo "Starting Backend on http://localhost:8001..."
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8001 --reload &
BACKEND_PID=$!

echo "Starting Celery Worker..."
celery -A backend.core.celery_app worker --loglevel=info -Q processing,upload,notification,maintenance &
CELERY_PID=$!

echo "Starting Frontend on http://localhost:3001..."
(cd frontend && npx vite --host 0.0.0.0 --port 3001) &
FRONTEND_PID=$!

cleanup() {
    echo "Stopping all services..."
    kill $BACKEND_PID $CELERY_PID $FRONTEND_PID 2>/dev/null || true
    exit 0
}

trap cleanup SIGINT SIGTERM EXIT

wait
