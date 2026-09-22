#!/bin/bash

# ClipFarm Studio One-click startup script
# Version: 2.0
# Function: Launch full ClipFarm System (Backend API + Celery Worker + Frontend Interface)

set -euo pipefail

# =============================================================================
# Configuration area
# =============================================================================

# Server port configuration
BACKEND_PORT=${BACKEND_PORT:-8001}
FRONTEND_PORT=${FRONTEND_PORT:-3001}
REDIS_PORT=${REDIS_PORT:-6379}

# Service timeout configuration
BACKEND_STARTUP_TIMEOUT=60
FRONTEND_STARTUP_TIMEOUT=90
HEALTH_CHECK_TIMEOUT=10

# Log configuration
LOG_DIR="logs"
BACKEND_LOG="$LOG_DIR/backend.log"
FRONTEND_LOG="$LOG_DIR/frontend.log"
CELERY_LOG="$LOG_DIR/celery.log"

# PID File
BACKEND_PID_FILE="backend.pid"
FRONTEND_PID_FILE="frontend.pid"
CELERY_PID_FILE="celery.pid"

# =============================================================================
# Color and style definitions
# =============================================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m' # No Color

# Icon definition
ICON_SUCCESS="✅"
ICON_ERROR="❌"
ICON_WARNING="⚠️"
ICON_INFO="ℹ️"
ICON_ROCKET="🚀"
ICON_GEAR="⚙️"
ICON_DATABASE="🗄️"
ICON_WORKER="👷"
ICON_WEB="🌐"
ICON_HEALTH="💚"

# =============================================================================
# Utility functions
# =============================================================================

log_info() {
    echo -e "${BLUE}${ICON_INFO} $1${NC}"
}

log_success() {
    echo -e "${GREEN}${ICON_SUCCESS} $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}${ICON_WARNING} $1${NC}"
}

log_error() {
    echo -e "${RED}${ICON_ERROR} $1${NC}"
}

log_header() {
    echo -e "\n${PURPLE}${ICON_ROCKET} $1${NC}"
    echo -e "${PURPLE}$(printf '=%.0s' {1..50})${NC}"
}

log_step() {
    echo -e "\n${CYAN}${ICON_GEAR} $1${NC}"
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Checking if port is in use
port_in_use() {
    lsof -i ":$1" >/dev/null 2>&1
}

# Waiting for service startup
wait_for_service() {
    local url="$1"
    local timeout="$2"
    local service_name="$3"
    
    log_info "Waiting for $service_name to start..."
    
    for i in $(seq 1 "$timeout"); do
        if curl -fsS "$url" >/dev/null 2>&1; then
            log_success "$service_name Started"
            return 0
        fi
        sleep 1
    done
    
    log_error "$service_name Startup timeout"
    return 1
}

# Check if process is running
process_running() {
    local pid_file="$1"
    if [[ -f "$pid_file" ]]; then
        local pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            return 0
        else
            rm -f "$pid_file"
        fi
    fi
    return 1
}

# Stop process
stop_process() {
    local pid_file="$1"
    local service_name="$2"
    
    if [[ -f "$pid_file" ]]; then
        local pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            log_info "Stopping $service_name (PID: $pid)..."
            kill "$pid" 2>/dev/null || true
            sleep 2
            if kill -0 "$pid" 2>/dev/null; then
                log_warning "Force stopping $service_name..."
                kill -9 "$pid" 2>/dev/null || true
            fi
        fi
        rm -f "$pid_file"
    fi
}

# =============================================================================
# Environment check function
# =============================================================================

check_environment() {
    log_header "Environment check"
    
    if [[ "$OSTYPE" == "darwin"* ]]; then
        log_success "Detected macOS System"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        log_success "Detected Linux System"
    else
        log_warning "Operating system: $OSTYPE"
    fi
    
    if [[ "${ENVIRONMENT:-}" != "production" ]] || [[ ! -f "/.dockerenv" ]]; then
        local required_commands=("python3" "node" "npm" "redis-cli")
        for cmd in "${required_commands[@]}"; do
            if command_exists "$cmd"; then
                log_success "$cmd Already installed"
            else
                log_error "$cmd Not installed, please install first"
                exit 1
            fi
        done
    else
        log_info "Docker environment detected, skipping node environment check"
        local required_commands=("python3" "redis-cli")
        for cmd in "${required_commands[@]}"; do
            if command_exists "$cmd"; then
                log_success "$cmd Already installed"
            else
                log_error "$cmd Not installed, please install first"
                exit 1
            fi
        done
    fi
    
    local python_version=$(python3 --version 2>&1 | cut -d' ' -f2)
    log_info "Python Version: $python_version"
    
    local node_version=$(node --version)
    log_info "Node.js Version: $node_version"
    
    if [[ ! -d "venv" ]]; then
        log_error "Virtual environment does not exist. Create first: python3 -m venv venv"
        exit 1
    fi
    log_success "Virtual environment exists"
    
    local required_dirs=("backend" "frontend" "data")
    for dir in "${required_dirs[@]}"; do
        if [[ -d "$dir" ]]; then
            log_success "Directory $dir exists"
        else
            log_error "Directory $dir does not exist"
            exit 1
        fi
    done
}

# =============================================================================
# Service startup functions
# =============================================================================

start_redis() {
    log_step "Start Redis Service"
    
    if redis-cli ping >/dev/null 2>&1; then
        log_success "Redis Service is already running"
        return 0
    fi
    
    log_info "Starting Redis Service..."
    
    if [[ "$OSTYPE" == "darwin"* ]]; then
        if command_exists brew; then
            brew services start redis
            sleep 3
        else
            log_error "Please start Redis Service manually"
            exit 1
        fi
    else
        systemctl start redis-server 2>/dev/null || service redis-server start 2>/dev/null || {
            log_error "Cannot start Redis Service, please start manually"
            exit 1
        }
    fi
    
    if redis-cli ping >/dev/null 2>&1; then
        log_success "Redis Service startup successful"
    else
        log_error "Redis Service startup failed"
        exit 1
    fi
}

setup_environment() {
    log_step "Set environment"
    
    mkdir -p "$LOG_DIR"
    
    log_info "Activating virtual environment..."
    source venv/bin/activate
    
    : "${PYTHONPATH:=}"
    export PYTHONPATH="${PWD}:${PYTHONPATH}"
    log_info "Set Python Path: $PYTHONPATH"
    
    if [[ -f ".env" ]]; then
        log_info "Loading environment variables..."
        set -a
        source .env
        set +a
        log_success "Environment variables loaded successfully"
    else
        log_warning ".env file not found. Creating from .env.example..."
        if [[ -f ".env.example" ]]; then
            cp .env.example .env
            log_success "Created .env from .env.example"
        fi
    fi
    
    log_info "Checking Python dependencies..."
    if ! python -c "import fastapi, celery, sqlalchemy" 2>/dev/null; then
        log_warning "Missing dependencies. Installing now..."
        pip install -r requirements.txt
    fi
    log_success "Python Dependency check completed"
}

init_database() {
    log_step "Initializing database"
    
    mkdir -p data
    
    log_info "Creating database tables..."
    if python -c "
import sys
sys.path.insert(0, '.')
from backend.core.database import engine, Base
from backend.models import project, task, clip, collection, bilibili, campaign
try:
    Base.metadata.create_all(bind=engine)
    print('Database tables created successfully')
except Exception as e:
    print(f'Database initialization failed: {e}')
    sys.exit(1)
" 2>/dev/null; then
        log_success "Database initialized successfully"
    else
        log_error "Database initialization failed"
        exit 1
    fi
}

start_celery() {
    log_step "Start Celery Worker"
    
    pkill -f "celery.*worker" 2>/dev/null || true
    sleep 2
    
    log_info "Check and clean up duplicate Whisper processes..."
    python scripts/monitor_whisper.py --kill-duplicates 2>/dev/null || true
    
    log_info "Starting Celery Worker..."
    nohup celery -A backend.core.celery_app worker \
        --loglevel=info \
        --concurrency=1 \
        --prefetch-multiplier=1 \
        -Q processing,upload,notification,maintenance \
        --hostname=worker@%h \
        > "$CELERY_LOG" 2>&1 &
    
    local celery_pid=$!
    echo "$celery_pid" > "$CELERY_PID_FILE"
    
    sleep 5
    
    if pgrep -f "celery.*worker" >/dev/null; then
        log_success "Celery Worker Started (PID: $celery_pid)"
    else
        log_error "Celery Worker Startup failed"
        log_info "View logs: tail -f $CELERY_LOG"
        exit 1
    fi
}

start_backend() {
    log_step "Start backend API Service"
    
    if port_in_use "$BACKEND_PORT"; then
        log_warning "Port $BACKEND_PORT already in use. Attempting to stop existing service..."
        stop_process "$BACKEND_PID_FILE" "Backend service"
    fi
    
    log_info "Starting backend service (port: $BACKEND_PORT)..."
    nohup python -m uvicorn backend.main:app \
        --host 0.0.0.0 \
        --port "$BACKEND_PORT" \
        --reload \
        --reload-dir backend \
        --reload-include '*.py' \
        --reload-exclude 'data/*' \
        --reload-exclude 'logs/*' \
        --reload-exclude 'uploads/*' \
        --reload-exclude '*.log' \
        > "$BACKEND_LOG" 2>&1 &
    
    local backend_pid=$!
    echo "$backend_pid" > "$BACKEND_PID_FILE"
    
    if wait_for_service "http://localhost:$BACKEND_PORT/api/v1/health/" "$BACKEND_STARTUP_TIMEOUT" "Backend service"; then
        log_success "Backend service started (PID: $backend_pid)"
    else
        log_error "Backend service failed to start"
        log_info "View logs: tail -f $BACKEND_LOG"
        exit 1
    fi
}

start_frontend() {
    log_step "Start frontend service"
    
    if port_in_use "$FRONTEND_PORT"; then
        log_warning "Port $FRONTEND_PORT already in use. Attempting to stop existing service..."
        stop_process "$FRONTEND_PID_FILE" "Frontend service"
    fi
    
    cd frontend || {
        log_error "Unable to enter frontend directory"
        exit 1
    }
    
    if [[ ! -d "node_modules" ]]; then
        log_info "Installing frontend dependencies..."
        npm install
    fi
    
    log_info "Starting frontend service (port: $FRONTEND_PORT)..."
    nohup npm run dev -- --host 0.0.0.0 --port "$FRONTEND_PORT" \
        > "../$FRONTEND_LOG" 2>&1 &
    
    local frontend_pid=$!
    echo "$frontend_pid" > "../$FRONTEND_PID_FILE"
    
    cd ..
    
    if wait_for_service "http://localhost:$FRONTEND_PORT/" "$FRONTEND_STARTUP_TIMEOUT" "Frontend service"; then
        log_success "Frontend service started (PID: $frontend_pid)"
    else
        log_error "Frontend service failed to start"
        log_info "View logs: tail -f $FRONTEND_LOG"
        exit 1
    fi
}

# =============================================================================
# Health check function
# =============================================================================

health_check() {
    log_header "System health check"
    
    local all_healthy=true
    
    log_info "Checking backend service..."
    if curl -fsS "http://localhost:$BACKEND_PORT/api/v1/health/" >/dev/null 2>&1; then
        log_success "Backend service healthy"
    else
        log_error "Backend service unhealthy"
        all_healthy=false
    fi
    
    log_info "Checking frontend service..."
    if curl -fsS "http://localhost:$FRONTEND_PORT/" >/dev/null 2>&1; then
        log_success "Frontend service healthy"
    else
        log_error "Frontend service unhealthy"
        all_healthy=false
    fi
    
    log_info "Checking Redis Service..."
    if redis-cli ping >/dev/null 2>&1; then
        log_success "Redis Service healthy"
    else
        log_error "Redis Service unhealthy"
        all_healthy=false
    fi
    
    log_info "Checking Celery Worker..."
    if pgrep -f "celery.*worker" >/dev/null; then
        log_success "Celery Worker healthy"
    else
        log_error "Celery Worker unhealthy"
        all_healthy=false
    fi
    
    if [[ "$all_healthy" == true ]]; then
        log_success "All services pass health checks"
        return 0
    else
        log_error "Some services fail health checks"
        return 1
    fi
}

# =============================================================================
# Cleanup function
# =============================================================================

cleanup() {
    log_header "Cleanup service"
    
    stop_process "$BACKEND_PID_FILE" "Backend service"
    stop_process "$FRONTEND_PID_FILE" "Frontend service"
    stop_process "$CELERY_PID_FILE" "Celery Worker"
    
    pkill -f "celery.*worker" 2>/dev/null || true
    pkill -f "uvicorn.*backend.main:app" 2>/dev/null || true
    pkill -f "npm.*dev" 2>/dev/null || true
    
    log_success "Cleanup complete"
}

# =============================================================================
# Display system information
# =============================================================================

show_system_info() {
    log_header "System startup complete"
    
    echo -e "${WHITE}🎉 ClipFarm Studio successfully started! ${NC}"
    echo ""
    echo -e "${CYAN}📊 Service status:${NC}"
    echo -e "  ${ICON_WEB} Backend API:        http://localhost:$BACKEND_PORT"
    echo -e "  ${ICON_WEB} Frontend Interface:  http://localhost:$FRONTEND_PORT"
    echo -e "  ${ICON_WEB} API Documentation:  http://localhost:$BACKEND_PORT/docs"
    echo -e "  ${ICON_HEALTH} Health Check:      http://localhost:$BACKEND_PORT/api/v1/health/"
    echo ""
    echo -e "${CYAN}📝 Log files:${NC}"
    echo -e "  Backend logs:  tail -f $BACKEND_LOG"
    echo -e "  Frontend logs: tail -f $FRONTEND_LOG"
    echo -e "  Celery logs:   tail -f $CELERY_LOG"
    echo ""
    echo -e "${CYAN}🛑 Stop system:${NC}"
    echo -e "  ./stop_clipfarm.sh or press Ctrl+C"
    echo ""
    echo -e "${YELLOW}💡 Usage instructions:${NC}"
    echo -e "  1. Access http://localhost:$FRONTEND_PORT to open ClipFarm Studio"
    echo -e "  2. Upload long video or paste a video link"
    echo -e "  3. ClipFarm AI detects moments, crops 9:16 smart framing, burns subtitles & exports clips"
    echo ""
}

# =============================================================================
# Signal handling
# =============================================================================

trap cleanup EXIT INT TERM

# =============================================================================
# Main function
# =============================================================================

main() {
    log_header "ClipFarm Studio Starter v2.0"
    
    check_environment
    start_redis
    setup_environment
    init_database
    start_celery
    start_backend
    start_frontend
    
    if health_check; then
        show_system_info
        
        log_info "ClipFarm Studio is running... Press Ctrl+C to stop"
        log_info "Run to check status: ./status_clipfarm.sh"
        while true; do
            sleep 3600
        done
    else
        log_error "System startup failed. Check logs"
        exit 1
    fi
}

main "$@"
