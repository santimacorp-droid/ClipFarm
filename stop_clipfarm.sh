#!/bin/bash

# ClipFarm Studio System stop script
# Version: 2.0
# Function: gracefully stop all ClipFarm services

set -euo pipefail

# =============================================================================
# Configuration
# =============================================================================

BACKEND_PID_FILE="backend.pid"
FRONTEND_PID_FILE="frontend.pid"
CELERY_PID_FILE="celery.pid"

LOG_DIR="logs"

# =============================================================================
# Color and style definitions
# =============================================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m'

ICON_SUCCESS="✅"
ICON_ERROR="❌"
ICON_WARNING="⚠️"
ICON_INFO="ℹ️"
ICON_STOP="🛑"

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
    echo -e "\n${PURPLE}${ICON_STOP} $1${NC}"
    echo -e "${PURPLE}$(printf '=%.0s' {1..50})${NC}"
}

stop_process() {
    local pid_file="$1"
    local service_name="$2"
    
    if [[ -f "$pid_file" ]]; then
        local pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            log_info "Stopping $service_name (PID: $pid)..."
            
            kill "$pid" 2>/dev/null || true
            
            local count=0
            while kill -0 "$pid" 2>/dev/null && [[ $count -lt 10 ]]; do
                sleep 1
                ((count++))
            done
            
            if kill -0 "$pid" 2>/dev/null; then
                log_warning "Force stopping $service_name..."
                kill -9 "$pid" 2>/dev/null || true
                sleep 1
            fi
            
            if kill -0 "$pid" 2>/dev/null; then
                log_error "Cannot stop $service_name"
            else
                log_success "$service_name stopped"
            fi
        else
            log_warning "$service_name process does not exist"
        fi
        rm -f "$pid_file"
    else
        log_info "$service_name PID file does not exist"
    fi
}

stop_all_processes() {
    log_header "Stopping all ClipFarm services"
    
    stop_process "$BACKEND_PID_FILE" "Backend service"
    stop_process "$FRONTEND_PID_FILE" "Frontend service"
    stop_process "$CELERY_PID_FILE" "Celery Worker"
    
    log_info "Stopping all Celery worker processes..."
    pkill -f "celery.*worker" 2>/dev/null || true
    
    log_info "Stopping all backend API processes..."
    pkill -f "uvicorn.*backend.main:app" 2>/dev/null || true
    
    log_info "Stopping all frontend development servers..."
    pkill -f "npm.*dev" 2>/dev/null || true
    pkill -f "vite" 2>/dev/null || true
    
    sleep 2
    log_success "All services stopped"
}

cleanup_temp_files() {
    log_header "Clean temporary files"
    
    rm -f "$BACKEND_PID_FILE" "$FRONTEND_PID_FILE" "$CELERY_PID_FILE"
    log_success "PID files cleaned"
    
    rm -f /tmp/celerybeat-schedule /tmp/celerybeat.pid 2>/dev/null || true
    
    find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
    find . -name "*.pyc" -delete 2>/dev/null || true
    log_success "Python cache cleared"
}

show_system_status() {
    log_header "System status check"
    
    local services_running=false
    
    if pgrep -f "uvicorn.*backend.main:app" >/dev/null; then
        log_warning "Backend service is still running"
        services_running=true
    else
        log_success "Backend service stopped"
    fi
    
    if pgrep -f "npm.*dev\|vite" >/dev/null; then
        log_warning "Frontend service is still running"
        services_running=true
    else
        log_success "Frontend service stopped"
    fi
    
    if pgrep -f "celery.*worker" >/dev/null; then
        log_warning "Celery Worker still running"
        services_running=true
    else
        log_success "Celery Worker stopped"
    fi
    
    if [[ "$services_running" == true ]]; then
        log_warning "Some processes are still running:"
        pgrep -f "uvicorn.*backend.main:app\|npm.*dev\|vite\|celery.*worker" | while read pid; do
            ps -p "$pid" -o pid,ppid,cmd --no-headers 2>/dev/null || true
        done
    else
        log_success "All ClipFarm services have been fully stopped"
    fi
}

main() {
    log_header "ClipFarm System Stopper v2.0"
    
    stop_all_processes
    cleanup_temp_files
    show_system_status
    
    echo ""
    log_success "ClipFarm System has been fully stopped"
    echo ""
    echo "To restart, run: ./start_clipfarm.sh"
}

main "$@"
