#!/bin/bash
# Podman Media Stack Shutdown Script
# ===================================
# Stops the media stack using Podman with proper cleanup options.

set -e  # Exit on any error

# Configuration
COMPOSE_FILE="podman-compose.yml"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if podman-compose is available
check_podman_compose() {
    if command -v podman-compose >/dev/null 2>&1; then
        COMPOSE_CMD="podman-compose"
    elif command -v docker-compose >/dev/null 2>&1 && command -v podman >/dev/null 2>&1; then
        COMPOSE_CMD="docker-compose"
        log_warning "Using docker-compose with podman backend"
    else
        log_error "Neither podman-compose nor docker-compose found!"
        exit 1
    fi
}

# Main execution
main() {
    log_info "Stopping Podman Media Stack..."
    
    # Pre-flight checks
    check_podman_compose
    
    # Check if compose file exists
    if [[ ! -f "$COMPOSE_FILE" ]]; then
        log_error "Compose file $COMPOSE_FILE not found!"
        exit 1
    fi
    
    # Parse command line arguments
    SERVICES=""
    REMOVE_VOLUMES=""
    REMOVE_IMAGES=""
    TIMEOUT=""
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --volumes|-v)
                REMOVE_VOLUMES="--volumes"
                shift
                ;;
            --rmi)
                if [[ -n "$2" && "$2" =~ ^(all|local)$ ]]; then
                    REMOVE_IMAGES="--rmi $2"
                    shift 2
                else
                    REMOVE_IMAGES="--rmi local"
                    shift
                fi
                ;;
            --timeout|-t)
                if [[ -n "$2" && "$2" =~ ^[0-9]+$ ]]; then
                    TIMEOUT="--timeout $2"
                    shift 2
                else
                    log_error "Invalid timeout value: $2"
                    exit 1
                fi
                ;;
            --help|-h)
                echo "Usage: $0 [OPTIONS] [SERVICES...]"
                echo ""
                echo "Options:"
                echo "  --volumes, -v        Remove named volumes declared in volumes section"
                echo "  --rmi [all|local]    Remove images (all: all images, local: only local images)"
                echo "  --timeout, -t TIME   Specify timeout for container stop (default: 10)"
                echo "  --help, -h           Show this help message"
                echo ""
                echo "Services:"
                echo "  If no services specified, all services will be stopped"
                echo "  Available services: pia-wggen, flaresolverr, prowlarr, sonarr,"
                echo "                     radarr, bazarr, gluetun, pia-pf, qbittorrent, jellyfin"
                echo ""
                echo "Examples:"
                echo "  $0                    # Stop all services"
                echo "  $0 jellyfin qbittorrent  # Stop specific services"
                echo "  $0 --volumes          # Stop all and remove volumes"
                echo "  $0 --rmi local        # Stop all and remove local images"
                exit 0
                ;;
            -*)
                log_error "Unknown option: $1"
                exit 1
                ;;
            *)
                SERVICES="$SERVICES $1"
                shift
                ;;
        esac
    done
    
    # Show current status before stopping
    log_info "Current service status:"
    $COMPOSE_CMD -f $COMPOSE_FILE ps 2>/dev/null || log_warning "No services currently running"
    echo ""
    
    # Build the command
    CMD="$COMPOSE_CMD -f $COMPOSE_FILE down $TIMEOUT $REMOVE_VOLUMES $REMOVE_IMAGES"
    
    # If specific services are mentioned, stop them individually
    if [[ -n "$SERVICES" ]]; then
        log_info "Stopping specific services:$SERVICES"
        if $COMPOSE_CMD -f $COMPOSE_FILE stop $TIMEOUT $SERVICES; then
            log_success "Services stopped successfully!"
        else
            log_error "Failed to stop some services!"
            exit 1
        fi
    else
        log_info "Executing: $CMD"
        
        # Execute the command
        if $CMD; then
            log_success "Media stack stopped successfully!"
            
            # Additional cleanup information
            if [[ -n "$REMOVE_VOLUMES" ]]; then
                log_info "Named volumes have been removed"
            fi
            
            if [[ -n "$REMOVE_IMAGES" ]]; then
                log_info "Images have been removed"
            fi
            
            # Show final status
            echo ""
            log_info "Final service status:"
            $COMPOSE_CMD -f $COMPOSE_FILE ps -a 2>/dev/null || echo "No containers found"
            
        else
            log_error "Failed to stop media stack!"
            exit 1
        fi
    fi
    
    echo ""
    log_info "Useful commands:"
    echo "  Start stack: ./podman-up.sh"
    echo "  Check logs: ./podman-logs.sh"
    echo "  Clean up containers: podman container prune"
    echo "  Clean up images: podman image prune"
    echo "  Clean up volumes: podman volume prune"
}

# Run main function
main "$@"