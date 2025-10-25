#!/bin/bash
# Podman Media Stack Startup Script
# ==================================
# Starts the media stack using Podman with proper error handling and options.

set -e  # Exit on any error

# Configuration
COMPOSE_FILE="core/podman-compose.yml"
ENV_FILE=".env"

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
        log_error "Install podman-compose: pip install podman-compose"
        exit 1
    fi
}

# Check if environment file exists
check_env_file() {
    if [[ ! -f "$ENV_FILE" ]]; then
        log_warning "Environment file $ENV_FILE not found!"
        if [[ -f "core/.env.example" ]]; then
            log_info "Creating $ENV_FILE from core/.env.example"
            cp core/.env.example "$ENV_FILE"
            log_warning "Please edit $ENV_FILE with your settings before running again!"
            exit 1
        else
            log_error "No .env.example file found. Please create $ENV_FILE manually."
            exit 1
        fi
    fi
}

# Check Podman setup
check_podman_setup() {
    if ! command -v podman >/dev/null 2>&1; then
        log_error "Podman not found! Please install Podman first."
        exit 1
    fi

    # Check if rootless or rootful
    if [[ $EUID -eq 0 ]]; then
        log_info "Running as root (rootful Podman)"
        PODMAN_MODE="rootful"
    else
        log_info "Running as user (rootless Podman)"
        PODMAN_MODE="rootless"
        
        # Check if user can create containers
        if ! podman info >/dev/null 2>&1; then
            log_warning "Podman not properly configured for rootless operation"
            log_info "Run: podman system migrate"
        fi
    fi
}

# Main execution
main() {
    log_info "Starting Podman Media Stack..."
    
    # Pre-flight checks
    check_podman_setup
    check_podman_compose
    check_env_file
    
    # Check if compose file exists
    if [[ ! -f "$COMPOSE_FILE" ]]; then
        log_error "Compose file $COMPOSE_FILE not found!"
        exit 1
    fi
    
    # Parse command line arguments
    SERVICES=""
    BUILD_FLAG=""
    FORCE_RECREATE=""
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --build)
                BUILD_FLAG="--build"
                shift
                ;;
            --force-recreate)
                FORCE_RECREATE="--force-recreate"
                shift
                ;;
            --help|-h)
                echo "Usage: $0 [OPTIONS] [SERVICES...]"
                echo ""
                echo "Options:"
                echo "  --build           Build images before starting"
                echo "  --force-recreate  Recreate containers even if config unchanged"
                echo "  --help, -h        Show this help message"
                echo ""
                echo "Services:"
                echo "  If no services specified, all services will be started"
                echo "  Available services: pia-wggen, flaresolverr, prowlarr, sonarr,"
                echo "                     radarr, bazarr, gluetun, pia-pf, qbittorrent, jellyfin"
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
    
    # Build the command
    CMD="$COMPOSE_CMD --env-file $ENV_FILE -f $COMPOSE_FILE up -d $BUILD_FLAG $FORCE_RECREATE $SERVICES"
    
    log_info "Executing: $CMD"
    
    # Execute the command
    if $CMD; then
        log_success "Media stack started successfully!"
        echo ""
        log_info "Service status:"
        $COMPOSE_CMD --env-file $ENV_FILE -f $COMPOSE_FILE ps
        echo ""
        log_info "Useful commands:"
        echo "  View logs: ./logs.sh"
        echo "  Stop stack: ./stop.sh"
        echo "  Check status: $COMPOSE_CMD --env-file $ENV_FILE -f $COMPOSE_FILE ps"
        echo ""
        log_info "Web interfaces:"
        echo "  Prowlarr:    http://localhost:9696"
        echo "  Sonarr:      http://localhost:8989"
        echo "  Radarr:      http://localhost:7878"
        echo "  Bazarr:      http://localhost:6767"
        echo "  qBittorrent: http://localhost:8080"
        echo "  Jellyfin:    http://localhost:8096"
        echo "  FlareSolverr: http://localhost:8191"
    else
        log_error "Failed to start media stack!"
        exit 1
    fi
}

# Run main function
main "$@"