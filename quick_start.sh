#!/bin/bash

# AutoClip Fast start script
# version: 2.0
# Feature: Fast-start development environment, skipping detailed checks

set -euo pipefail

# =============================================================================
# Configuration area
# =============================================================================

BACKEND_PORT=${BACKEND_PORT:-8001}
FRONTEND_PORT=${FRONTEND_PORT:-3001}

# =============================================================================
# color definitions
# =============================================================================

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

# =============================================================================
# util function
# =============================================================================

log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# =============================================================================
# main function
# =============================================================================

main() {
    echo -e "${GREEN}🚀 ClipFarm Studio quick launch${NC}"
    echo ""
    
    # Checking virtual environment
    if [[ ! -d "venv" ]]; then
        log_warning "Virtual environment does not exist. Please run first: python3 -m venv venv"
        exit 1
    fi
    
    # Activating virtual environment
    log_info "Activating virtual environment..."
    source venv/bin/activate
    
    # settingsPythonpath
    : "${PYTHONPATH:=}"
    export PYTHONPATH="${PWD}:${PYTHONPATH}"
    
    # Loading environment variables
    if [[ -f ".env" ]]; then
        set -a
        source .env
        set +a
    fi
    
    # startRedis(if needed)
    if ! redis-cli ping >/dev/null 2>&1; then
        log_info "startRedis..."
        if command -v brew >/dev/null; then
            brew services start redis
            sleep 2
        fi
    fi
    
    # Creating log directory
    mkdir -p logs
    
    export BACKEND_PORT
    export FRONTEND_PORT
    
    # launch backend
    log_info "Starting backend service (port: $BACKEND_PORT)..."
    nohup python -m uvicorn backend.main:app --host 0.0.0.0 --port "$BACKEND_PORT" </dev/null > logs/backend.log 2>&1 &
    echo $! > backend.pid
    disown || true
    
    # startCelery Worker
    log_info "startCelery Worker..."
    nohup celery -A backend.core.celery_app worker --loglevel=info --concurrency=1 --prefetch-multiplier=1 -Q processing,upload,notification,maintenance </dev/null > logs/celery.log 2>&1 &
    echo $! > celery.pid
    disown || true
    
    # launch frontend
    log_info "Starting frontend service (port: $FRONTEND_PORT)..."
    cd frontend
    nohup npx vite --host 0.0.0.0 --port "$FRONTEND_PORT" </dev/null > ../logs/frontend.log 2>&1 &
    echo $! > ../frontend.pid
    disown || true
    cd ..
    
    # Waiting for service to start
    log_info "Waiting for service to start..."
    sleep 5
    
    # Checking service status
    if curl -fsS "http://localhost:$BACKEND_PORT/api/v1/health/" >/dev/null 2>&1; then
        log_success "Backend service started"
    else
        log_warning "Backend service may have startup issues"
    fi
    
    if curl -fsS "http://localhost:$FRONTEND_PORT/" >/dev/null 2>&1; then
        log_success "Frontend service started"
    else
        log_warning "Frontend service may have startup issues"
    fi
    
    echo ""
    log_success "Fast start complete! "
    echo ""
    echo "🌐 access address:"
    echo "  frontend: http://localhost:$FRONTEND_PORT"
    echo "  backend: http://localhost:$BACKEND_PORT"
    echo "  APIdocs: http://localhost:$BACKEND_PORT/docs"
    echo ""
    echo "📝 View logs:"
    echo "  tail -f logs/backend.log"
    echo "  tail -f logs/frontend.log"
    echo "  tail -f logs/celery.log"
    echo ""
    echo "🛑 Stop services: ./stop_clipfarm.sh"
}

# Running main function
main "$@"
