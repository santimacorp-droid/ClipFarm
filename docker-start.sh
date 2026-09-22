#!/bin/bash

# AutoClip Docker Startup script
# version: 1.0
# Feature: UsingDockerQuick startAutoClipSystem

set -euo pipefail

# =============================================================================
# Configuration region
# =============================================================================

# Color definitions
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m' # No Color

# icon definition
ICON_SUCCESS="✅"
ICON_ERROR="❌"
ICON_WARNING="⚠️"
ICON_INFO="ℹ️"
ICON_ROCKET="🚀"
ICON_DOCKER="🐳"

# =============================================================================
# Utility function
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

# =============================================================================
# Check function
# =============================================================================

check_docker() {
    log_header "CheckDockerEnvironment"
    
    if ! command -v docker >/dev/null 2>&1; then
        log_error "DockerNot installed, please install firstDocker"
        exit 1
    fi
    log_success "Dockeralready installed"
    
    if ! command -v docker-compose >/dev/null 2>&1; then
        log_error "Docker ComposeNot installed, please install firstDocker Compose"
        exit 1
    fi
    log_success "Docker Composealready installed"
    
    if ! docker info >/dev/null 2>&1; then
        log_error "DockerService is not running, please start itDockerService"
        exit 1
    fi
    log_success "DockerService is running normally"
}

check_environment() {
    log_header "Checking environment configuration"
    
    if [[ ! -f ".env" ]]; then
        log_warning ".envFile does not exist, create default configuration..."
        if [[ -f "env.example" ]]; then
            cp env.example .env
            log_success "Default created successfully.envfile(s)"
            log_warning "edit this....envFile, enter necessary configurations (especiallyAPIKey)"
        else
            log_error "env.exampleFile does not exist"
            exit 1
        fi
    else
        log_success ".envfile exists"
    fi
    
    # Check necessary configurations
    if ! grep -q "API_DASHSCOPE_API_KEY" .env || grep -q "API_DASHSCOPE_API_KEY=$" .env; then
        log_warning "API_DASHSCOPE_API_KEYnot configured, AIFunction will be unavailable"
    fi
}

check_ports() {
    log_header "Checking port usage"
    
    local ports=(8000 3000 6379 5555)
    local occupied_ports=()
    
    for port in "${ports[@]}"; do
        if lsof -i ":$port" >/dev/null 2>&1; then
            occupied_ports+=("$port")
        fi
    done
    
    if [[ ${#occupied_ports[@]} -gt 0 ]]; then
        log_warning "The following ports are in use: ${occupied_ports[*]}"
        log_info "DockerWill automatically handle port conflicts but recommend stopping the services that occupy these ports first"
    else
        log_success "All ports available"
    fi
}

# =============================================================================
# Start function
# =============================================================================

start_services() {
    log_header "StartAutoClipService"
    
    # Choose startup mode
    if [[ "${1:-}" == "dev" ]]; then
        log_info "Starting development environment..."
        docker-compose -f docker-compose.dev.yml up -d
        COMPOSE_FILE="docker-compose.dev.yml"
    else
        log_info "Starting production environment..."
        docker-compose up -d
        COMPOSE_FILE="docker-compose.yml"
    fi
    
    # Waiting for service to start
    log_info "Waiting for service to start..."
    sleep 10
    
    # Checking service status
    if docker-compose -f "$COMPOSE_FILE" ps | grep -q "Up"; then
        log_success "Service started successfully"
    else
        log_error "Service startup failed"
        log_info "View logs: docker-compose -f $COMPOSE_FILE logs"
        exit 1
    fi
}

show_status() {
    log_header "Service status"
    
    echo -e "${CYAN}📊 Container status:${NC}"
    docker-compose ps
    
    echo -e "\n${CYAN}🌐 access address:${NC}"
    echo -e "  front‑end interface: http://localhost:3000"
    echo -e "  BackendAPI:  http://localhost:8000"
    echo -e "  APIdocumentation:  http://localhost:8000/docs"
    echo -e "  FlowerMonitoring: http://localhost:5555"
    
    echo -e "\n${CYAN}📝 Common commands:${NC}"
    echo -e "  View logs: docker-compose logs -f"
    echo -e "  Stop service: docker-compose down"
    echo -e "  Restart service: docker-compose restart"
    echo -e "  enter container: docker-compose exec autoclip bash"
}

# =============================================================================
# main function
# =============================================================================

main() {
    log_header "AutoClip Docker launcher v1.0"
    
    # Parse parameters
    local mode="production"
    if [[ "${1:-}" == "dev" ]]; then
        mode="development"
    fi
    
    log_info "startup mode: $mode"
    
    # Run check
    check_docker
    check_environment
    check_ports
    
    # starting service...
    start_services "$mode"
    
    # Show status
    show_status
    
    echo -e "\n${WHITE}🎉 AutoClip Docker deployment complete! ${NC}"
    echo -e "${YELLOW}💡 Tip: The first startup may take several minutes to download and build the image${NC}"
}

# Show help information
show_help() {
    echo "AutoClip Docker Startup script"
    echo ""
    echo "Usage:"
    echo "  $0 [options]"
    echo ""
    echo "options:"
    echo "  dev     Starting development environment"
    echo "  help    Show help information"
    echo ""
    echo "example:"
    echo "  $0          # Starting production environment"
    echo "  $0 dev      # Starting development environment"
    echo "  $0 help     # show help"
}

# processing parameters
case "${1:-}" in
    "help"|"-h"|"--help")
        show_help
        exit 0
        ;;
    *)
        main "$@"
        ;;
esac
