#!/bin/bash
# Podman Media Stack Startup Script
# ==================================
# Starts the media stack using Podman with proper error handling and options.

set -e  # Exit on any error

# Configuration
COMPOSE_FILE="core/podman-compose.yml"
ENV_FILE="core/.env"

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

# Check for NVIDIA GPU device availability
check_nvidia_gpu_availability() {
    local timeout=${1:-60}  # Default 60 seconds timeout
    local start_time=$(date +%s)
    
    log_info "Checking NVIDIA GPU device availability..."
    
    # Required NVIDIA device files for GPU acceleration
    local required_devices=(
        "/dev/nvidia-uvm"
        "/dev/nvidia0"
        "/dev/nvidiactl"
    )
    
    local attempts=0
    local max_attempts=$((timeout / 2))  # Check every 2 seconds
    
    while [[ $attempts -lt $max_attempts ]]; do
        # Check all required devices
        local all_devices_available=true
        local missing_devices=()
        
        for device in "${required_devices[@]}"; do
            if [[ ! -e "$device" ]]; then
                all_devices_available=false
                missing_devices+=("$device")
            fi
        done
        
        # If all devices are available, we're good to go
        if [[ "$all_devices_available" == true ]]; then
            log_success "All NVIDIA GPU devices are available"
            log_info "Found devices: ${required_devices[*]}"
            return 0
        fi
        
        # Log missing devices (but only every 5 attempts to avoid spam)
        if [[ $((attempts % 5)) -eq 0 ]] && [[ $attempts -gt 0 ]]; then
            local elapsed=$((attempts * 2))
            log_info "Waiting for NVIDIA devices (${elapsed}s/${timeout}s) - Missing: ${missing_devices[*]}"
        fi
        
        # Wait before next check
        sleep 2
        attempts=$((attempts + 1))
    done
    
    # Timeout reached
    log_warning "GPU availability check timeout after ${timeout}s"
    log_warning "NVIDIA devices not available - proceeding without GPU acceleration"
    return 1
}

# Create temporary compose file without GPU acceleration
create_gpu_fallback_compose() {
    local original_compose="$1"
    local fallback_compose="$2"
    
    log_info "Creating GPU fallback configuration..."
    
    # Copy original compose file and remove GPU-specific configurations
    cp "$original_compose" "$fallback_compose"
    
    # Remove nvidia.com/gpu device mapping and NVIDIA environment variables
    sed -i '/nvidia\.com\/gpu=all/d' "$fallback_compose"
    sed -i '/NVIDIA_VISIBLE_DEVICES/d' "$fallback_compose"
    sed -i '/NVIDIA_DRIVER_CAPABILITIES/d' "$fallback_compose"
    
    log_info "GPU fallback compose file created: $fallback_compose"
    log_warning "Jellyfin will start without GPU acceleration"
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
    SKIP_GPU_CHECK=""
    
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
            --skip-gpu-check)
                SKIP_GPU_CHECK="true"
                shift
                ;;
            --help|-h)
                echo "Usage: $0 [OPTIONS] [SERVICES...]"
                echo ""
                echo "Options:"
                echo "  --build           Build images before starting"
                echo "  --force-recreate  Recreate containers even if config unchanged"
                echo "  --skip-gpu-check  Skip NVIDIA GPU availability check"
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
    
    # GPU availability check and compose file selection
    local ACTIVE_COMPOSE_FILE="$COMPOSE_FILE"
    local FALLBACK_COMPOSE_FILE=""
    local GPU_AVAILABLE=false
    
    # Check if we should skip GPU check or if Jellyfin is specifically requested
    if [[ "$SKIP_GPU_CHECK" != "true" ]] && [[ -z "$SERVICES" || "$SERVICES" =~ jellyfin ]]; then
        log_info "Checking NVIDIA GPU availability for Jellyfin..."
        
        if check_nvidia_gpu_availability 60; then
            log_success "NVIDIA GPU devices available - using full GPU acceleration"
            GPU_AVAILABLE=true
        else
            log_warning "NVIDIA GPU devices not available - creating fallback configuration"
            
            # Create fallback compose file without GPU acceleration
            FALLBACK_COMPOSE_FILE="$(dirname "$COMPOSE_FILE")/podman-compose-no-gpu.yml"
            create_gpu_fallback_compose "$COMPOSE_FILE" "$FALLBACK_COMPOSE_FILE"
            ACTIVE_COMPOSE_FILE="$FALLBACK_COMPOSE_FILE"
            GPU_AVAILABLE=false
        fi
    else
        if [[ "$SKIP_GPU_CHECK" == "true" ]]; then
            log_info "GPU check skipped - using original configuration"
        else
            log_info "Jellyfin not in service list - skipping GPU check"
        fi
        GPU_AVAILABLE=true  # Assume available when skipping check
    fi
    
    # Build the command with the selected compose file
    CMD="$COMPOSE_CMD --env-file $ENV_FILE -f $ACTIVE_COMPOSE_FILE up -d $BUILD_FLAG $FORCE_RECREATE $SERVICES"
    
    log_info "Executing: $CMD"
    
    # Execute the command
    local SUCCESS=false
    if $CMD; then
        SUCCESS=true
        log_success "Media stack started successfully!"
        
        # Display GPU status in success message
        if [[ "$GPU_AVAILABLE" == true ]]; then
            log_success "Jellyfin started with NVIDIA GPU acceleration enabled"
        elif [[ -n "$FALLBACK_COMPOSE_FILE" ]]; then
            log_warning "Jellyfin started without GPU acceleration (GPU devices not available)"
            log_info "GPU acceleration will be available after next restart once NVIDIA drivers are loaded"
        fi
        
        echo ""
        log_info "Service status:"
        $COMPOSE_CMD --env-file $ENV_FILE -f $ACTIVE_COMPOSE_FILE ps
        echo ""
        log_info "Useful commands:"
        echo "  View logs: ./scripts/podman-logs.sh"
        echo "  Stop stack: ./scripts/podman-down.sh"
        echo "  Check status: $COMPOSE_CMD --env-file $ENV_FILE -f $ACTIVE_COMPOSE_FILE ps"
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
    fi
    
    # Cleanup fallback compose file if it was created
    if [[ -n "$FALLBACK_COMPOSE_FILE" ]] && [[ -f "$FALLBACK_COMPOSE_FILE" ]]; then
        log_info "Cleaning up temporary GPU fallback configuration"
        rm -f "$FALLBACK_COMPOSE_FILE"
    fi
    
    # Exit with appropriate code
    if [[ "$SUCCESS" == true ]]; then
        exit 0
    else
        exit 1
    fi
}

# Run main function
main "$@"