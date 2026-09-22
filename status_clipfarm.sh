#!/bin/bash

# ClipFarm Studio System status check script
# Version: 2.0
# Function: Check status of all ClipFarm services

set -euo pipefail

# =============================================================================
# Configuration
# =============================================================================

BACKEND_PORT=${BACKEND_PORT:-8001}
FRONTEND_PORT=${FRONTEND_PORT:-3001}
REDIS_PORT=${REDIS_PORT:-6379}

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
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m'

ICON_SUCCESS="✅"
ICON_ERROR="❌"
ICON_WARNING="⚠️"
ICON_INFO="ℹ️"
ICON_HEALTH="💚"
ICON_SICK="🤒"
ICON_ROCKET="🚀"
ICON_DATABASE="🗄️"
ICON_WORKER="👷"
ICON_WEB="🌐"

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

check_service_health() {
    local url="$1"
    local service_name="$2"
    
    if curl -fsS "$url" >/dev/null 2>&1; then
        echo -e "${GREEN}${ICON_HEALTH} $service_name Healthy${NC}"
        return 0
    else
        echo -e "${RED}${ICON_SICK} $service_name Unhealthy${NC}"
        return 1
    fi
}

check_process_status() {
    local pid_file="$1"
    local service_name="$2"
    local process_pattern="$3"
    
    if [[ -f "$pid_file" ]]; then
        local pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            echo -e "${GREEN}${ICON_SUCCESS} $service_name Running (PID: $pid)${NC}"
            return 0
        else
            echo -e "${RED}${ICON_ERROR} $service_name Not Running (Stale PID file)${NC}"
            return 1
        fi
    else
        if pgrep -f "$process_pattern" >/dev/null; then
            local pids=$(pgrep -f "$process_pattern" | tr '\n' ' ')
            echo -e "${YELLOW}${ICON_WARNING} $service_name Running (PID: $pids, no PID file)${NC}"
            return 0
        else
            echo -e "${RED}${ICON_ERROR} $service_name Not Running${NC}"
            return 1
        fi
    fi
}

check_backend() {
    log_header "Backend API Status"
    local process_ok=0
    local health_ok=0
    
    check_process_status "$BACKEND_PID_FILE" "Backend API Service" "uvicorn.*backend.main:app" || process_ok=1
    check_service_health "http://localhost:$BACKEND_PORT/api/v1/health/" "Backend API Health" || health_ok=1
    
    return $((process_ok || health_ok))
}

check_frontend() {
    log_header "Frontend Service Status"
    local process_ok=0
    local health_ok=0
    
    check_process_status "$FRONTEND_PID_FILE" "Frontend Service" "npm.*dev\|vite" || process_ok=1
    check_service_health "http://localhost:$FRONTEND_PORT/" "Frontend Service" || health_ok=1
    
    return $((process_ok || health_ok))
}

check_celery() {
    log_header "Celery Worker Status"
    check_process_status "$CELERY_PID_FILE" "Celery Worker" "celery.*worker"
}

check_redis() {
    log_header "Redis Service Status"
    if redis-cli -p "$REDIS_PORT" ping >/dev/null 2>&1; then
        log_success "Redis Service Running (Port: $REDIS_PORT)"
        return 0
    else
        log_error "Redis Service Not Running"
        return 1
    fi
}

check_database() {
    log_header "Database Status"
    local python_bin="python3"
    [[ -f "venv/bin/python" ]] && python_bin="venv/bin/python"
    
    if "$python_bin" -c "
import sys
sys.path.insert(0, '.')
from backend.core.database import test_connection
if test_connection():
    print('Database connection is normal')
else:
    sys.exit(1)
" 2>/dev/null; then
        log_success "Database connection is normal"
        return 0
    else
        log_error "Database connection failed"
        return 1
    fi
}

check_logs() {
    log_header "Log file status"
    if [[ -d "$LOG_DIR" ]]; then
        log_success "Log directory exists"
        echo -e "\n${CYAN}📊 Log files:${NC}"
        ls -la "$LOG_DIR"/*.log 2>/dev/null | while read line; do
            echo "  $line"
        done
    fi
}

main() {
    log_header "ClipFarm System Status Check v2.0"
    
    local overall_status=0
    check_redis || overall_status=1
    check_database || overall_status=1
    check_celery || overall_status=1
    check_backend || overall_status=1
    check_frontend || overall_status=1
    check_logs
    
    log_header "Overall System Status"
    if [[ $overall_status -eq 0 ]]; then
        log_success "All services are running normally"
        echo ""
        echo -e "${WHITE}🎉 ClipFarm System fully healthy! ${NC}"
        echo ""
        echo -e "${CYAN}🌐 Access endpoints:${NC}"
        echo -e "  Frontend Interface: http://localhost:$FRONTEND_PORT"
        echo -e "  Backend API:        http://localhost:$BACKEND_PORT"
        echo -e "  API Documentation:  http://localhost:$BACKEND_PORT/docs"
    else
        log_error "Some services are not running"
        echo ""
        echo -e "${YELLOW}💡 Suggested operations:${NC}"
        echo -e "  1. Check log files: tail -f $LOG_DIR/*.log"
        echo -e "  2. Restart system: ./stop_clipfarm.sh && ./start_clipfarm.sh"
    fi
    echo ""
}

main "$@"
