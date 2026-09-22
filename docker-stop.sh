#!/bin/bash

# AutoClip Docker Stop script
# Version: 1.0
# Feature: StopAutoClip DockerService

set -euo pipefail

# =============================================================================
# Configuration zone
# =============================================================================

# Color definitions
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Icon definition
ICON_SUCCESS="✅"
ICON_ERROR="❌"
ICON_WARNING="⚠️"
ICON_INFO="ℹ️"
ICON_STOP="🛑"

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
    echo -e "\n${PURPLE}${ICON_STOP} $1${NC}"
    echo -e "${PURPLE}$(printf '=%.0s' {1..50})${NC}"
}

# =============================================================================
# Stop function
# =============================================================================

stop_services() {
    log_header "StopAutoClipService"
    
    local mode="${1:-production}"
    local compose_file="docker-compose.yml"
    
    if [[ "$mode" == "dev" ]]; then
        compose_file="docker-compose.dev.yml"
    fi
    
    log_info "Stop service (mode: $mode)..."
    
    # Stopping service...
    if docker-compose -f "$compose_file" down; then
        log_success "Service has stopped"
    else
        log_error "Failed to stop service"
        exit 1
    fi
}

cleanup_containers() {
    log_header "Clean container"
    
    # Stop all related containers
    local containers=$(docker ps -a --filter "name=autoclip" --format "{{.Names}}" 2>/dev/null || true)
    
    if [[ -n "$containers" ]]; then
        log_info "Found the followingAutoClipContainer:"
        echo "$containers"
        
        if [[ "${1:-}" == "--force" ]]; then
            log_info "Forcefully stop all containers..."
            echo "$containers" | xargs docker stop 2>/dev/null || true
            echo "$containers" | xargs docker rm 2>/dev/null || true
            log_success "Container cleanup completed"
        else
            log_warning "Usage --force Parameter forces container cleanup"
        fi
    else
        log_success "Not foundAutoClipContainer"
    fi
}

cleanup_images() {
    log_header "Clean images"
    
    if [[ "${1:-}" == "--force" ]]; then
        log_info "Clean up unused images..."
        docker image prune -f
        log_success "Image cleanup completed"
    else
        log_info "Usage --force Parameter deletes unused images"
    fi
}

cleanup_volumes() {
    log_header "Clean data volumes"
    
    if [[ "${1:-}" == "--force" ]]; then
        log_warning "This will delete all data, including project files and database! "
        read -p "Are you sure you want to continue?? (y/N): " -n 1 -r
        echo
        
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            log_info "Clean data volumes..."
            docker volume prune -f
            log_success "Data volume cleanup complete"
        else
            log_info "Cancel deleting data volumes"
        fi
    else
        log_info "Usage --force Parameter deletes unused data volumes"
    fi
}

show_status() {
    log_header "Current state"
    
    echo -e "${BLUE}📊 Container status:${NC}"
    docker-compose ps 2>/dev/null || echo "  No services running"
    
    echo -e "\n${BLUE}🐳 AutoClipRelated containers:${NC}"
    docker ps -a --filter "name=autoclip" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || echo "  No related containers found"
    
    echo -e "\n${BLUE}💾 Data volume:${NC}"
    docker volume ls --filter "name=autoclip" --format "table {{.Name}}\t{{.Driver}}\t{{.Size}}" 2>/dev/null || echo "  No related data volumes found"
}

# =============================================================================
# Main function
# =============================================================================

main() {
    local mode="production"
    local cleanup=false
    local force=false
    
    # Parsing parameters
    while [[ $# -gt 0 ]]; do
        case $1 in
            "dev")
                mode="development"
                shift
                ;;
            "--cleanup")
                cleanup=true
                shift
                ;;
            "--force")
                force=true
                shift
                ;;
            "help"|"-h"|"--help")
                show_help
                exit 0
                ;;
            *)
                log_error "Unknown parameter: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    log_header "AutoClip Docker Stopper v1.0"
    
    # Stopping service...
    stop_services "$mode"
    
    # Clean (if needed))
    if [[ "$cleanup" == true ]]; then
        cleanup_containers "$force"
        cleanup_images "$force"
        cleanup_volumes "$force"
    fi
    
    # Display status
    show_status
    
    echo -e "\n${GREEN}🎉 AutoClip Docker Service has stopped${NC}"
}

# Display help information
show_help() {
    echo "AutoClip Docker Stop script"
    echo ""
    echo "Usage:"
    echo "  $0 [Options]"
    echo ""
    echo "Options:"
    echo "  dev          Stopping development environment"
    echo "  --cleanup    Stop then clean up resources"
    echo "  --force      Forcefully clean up (including data))"
    echo "  help         Display help information"
    echo ""
    echo "Example:"
    echo "  $0                    # Stopping production environment"
    echo "  $0 dev                # Stopping development environment"
    echo "  $0 --cleanup          # Stop and clean up resources"
    echo "  $0 --cleanup --force  # Stop and forcefully clean up all resources"
    echo "  $0 help               # Show help"
    echo ""
    echo "Note:"
    echo "  --force Parameters will delete all data, please use with caution! "
}

# Run main function
main "$@"
