#!/bin/bash

# AutoClip Docker Status check script
# Version: 1.0
# Function: CheckAutoClip DockerService status

set -euo pipefail

# =============================================================================
# configuration region
# =============================================================================

# color definitions
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
ICON_HEALTH="💚"
ICON_SICK="🤒"
ICON_ROCKET="🚀"
ICON_DOCKER="🐳"

# =============================================================================
# utility functions
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
# check function
# =============================================================================

check_docker() {
    log_header "Dockerenvironment check"
    
    if ! command -v docker >/dev/null 2>&1; then
        log_error "DockerNot installed"
        return 1
    fi
    log_success "DockerInstalled"
    
    if ! command -v docker-compose >/dev/null 2>&1; then
        log_error "Docker ComposeNot installed"
        return 1
    fi
    log_success "Docker ComposeInstalled"
    
    if ! docker info >/dev/null 2>&1; then
        log_error "Dockerservice not running"
        return 1
    fi
    log_success "DockerService is running normally"
    
    return 0
}

check_containers() {
    log_header "Container status check"
    
    local containers=$(docker ps -a --filter "name=autoclip" --format "{{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || true)
    
    if [[ -z "$containers" ]]; then
        log_warning "Not foundAutoClipcontainer"
        return 1
    fi
    
    echo -e "${CYAN}📊 container status:${NC}"
    echo "$containers" | while IFS=$'\t' read -r name status ports; do
        if [[ "$status" == *"Up"* ]]; then
            echo -e "  ${GREEN}${ICON_HEALTH} $name${NC} - $status"
        else
            echo -e "  ${RED}${ICON_SICK} $name${NC} - $status"
        fi
    done
    
    return 0
}

check_services() {
    log_header "Service health check"
    
    # Check backendAPI
    if curl -fsS "http://localhost:8000/api/v1/health/" >/dev/null 2>&1; then
        log_success "backendAPIservice healthy"
    else
        log_error "backendAPIservice unhealthy"
    fi
    
    # Check frontend service
    if curl -fsS "http://localhost:3000/" >/dev/null 2>&1; then
        log_success "Frontend service healthy"
    else
        log_error "Frontend service is unhealthy"
    fi
    
    # checkRedis
    if docker exec autoclip-redis redis-cli ping >/dev/null 2>&1; then
        log_success "Redisservice healthy"
    else
        log_error "Redisservice unhealthy"
    fi
}

check_volumes() {
    log_header "data volume check"
    
    local volumes=$(docker volume ls --filter "name=autoclip" --format "{{.Name}}\t{{.Driver}}\t{{.Size}}" 2>/dev/null || true)
    
    if [[ -z "$volumes" ]]; then
        log_warning "Not foundAutoClipData volume"
        return 1
    fi
    
    echo -e "${CYAN}💾 Data volume:${NC}"
    echo "$volumes" | while IFS=$'\t' read -r name driver size; do
        echo -e "  ${ICON_INFO} $name ($driver) - $size"
    done
    
    return 0
}

check_networks() {
    log_header "Network check"
    
    local networks=$(docker network ls --filter "name=autoclip" --format "{{.Name}}\t{{.Driver}}\t{{.Scope}}" 2>/dev/null || true)
    
    if [[ -z "$networks" ]]; then
        log_warning "Not foundAutoClipnetwork"
        return 1
    fi
    
    echo -e "${CYAN}🌐 network:${NC}"
    echo "$networks" | while IFS=$'\t' read -r name driver scope; do
        echo -e "  ${ICON_INFO} $name ($driver) - $scope"
    done
    
    return 0
}

check_resources() {
    log_header "Resource usage details"
    
    echo -e "${CYAN}📊 Container resource usage:${NC}"
    docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}" $(docker ps --filter "name=autoclip" --format "{{.Names}}" 2>/dev/null || true) 2>/dev/null || log_warning "Failed to retrieve resource usage"
}

show_access_info() {
    log_header "access information"
    
    echo -e "${CYAN}🌐 Service access address:${NC}"
    echo -e "  Frontend interface: http://localhost:3000"
    echo -e "  backendAPI:  http://localhost:8000"
    echo -e "  APIDocumentation:  http://localhost:8000/docs"
    echo -e "  Flowermonitoring: http://localhost:5555"
    
    echo -e "\n${CYAN}📝 common commands:${NC}"
    echo -e "  view logs: docker-compose logs -f"
    echo -e "  stop service: docker-compose down"
    echo -e "  restart service: docker-compose restart"
    echo -e "  Enter container: docker-compose exec autoclip bash"
}

# =============================================================================
# Main function
# =============================================================================

main() {
    log_header "AutoClip Docker status check v1.0"
    
    local overall_status=0
    
    # checkDockerenvironment
    if ! check_docker; then
        overall_status=1
    fi
    
    # Check container status
    if ! check_containers; then
        overall_status=1
    fi
    
    # Check service health status
    check_services
    
    # check data volume
    check_volumes
    
    # Check network
    check_networks
    
    # Check resource usage
    check_resources
    
    # display access information
    show_access_info
    
    # Display overall status
    log_header "Overall status"
    
    if [[ $overall_status -eq 0 ]]; then
        log_success "AutoClip DockerService is running normally"
        echo -e "\n${WHITE}🎉 All services are healthy! ${NC}"
    else
        log_error "Some services have problems"
        echo -e "\n${YELLOW}💡 Suggested action:${NC}"
        echo -e "  1. view detailed logs: docker-compose logs"
        echo -e "  2. restart service: docker-compose restart"
        echo -e "  3. restart: ./docker-start.sh"
    fi
}

# Show help information
show_help() {
    echo "AutoClip Docker Status check script"
    echo ""
    echo "usage:"
    echo "  $0 [Options]"
    echo ""
    echo "Options:"
    echo "  help    Show help information"
    echo ""
    echo "Example:"
    echo "  $0          # Check service status"
    echo "  $0 help     # Show help"
}

# Process parameters
case "${1:-}" in
    "help"|"-h"|"--help")
        show_help
        exit 0
        ;;
    *)
        main "$@"
        ;;
esac
