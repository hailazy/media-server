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
    
    # Timeout reached - fail since GPU is required
    log_error "GPU availability check timeout after ${timeout}s"
    log_error "NVIDIA devices not available - GPU acceleration is required"
    exit 1
}

# Get current NVIDIA driver version
get_nvidia_driver_version() {
    local driver_version=""
    
    # Try nvidia-smi first (most reliable)
    if command -v nvidia-smi >/dev/null 2>&1; then
        driver_version=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader,nounits 2>/dev/null | head -1 | tr -d '[:space:]')
    fi
    
    # Fallback to /proc/driver/nvidia/version if nvidia-smi fails
    if [[ -z "$driver_version" ]] && [[ -f "/proc/driver/nvidia/version" ]]; then
        driver_version=$(grep "NVRM version" /proc/driver/nvidia/version 2>/dev/null | awk '{print $NF}' | tr -d '[:space:]')
    fi
    
    echo "$driver_version"
}

# Check and maintain NVIDIA CDI configuration for rootless Podman
check_nvidia_cdi_configuration() {
    local driver_version
    local cdi_config_dir="${HOME}/.config/containers/cdi"
    local cdi_config_file="${cdi_config_dir}/nvidia.yaml"
    local state_file="${cdi_config_dir}/nvidia-driver-version.txt"
    local stored_version=""
    
    log_info "Checking NVIDIA CDI configuration for rootless Podman..."
    
    # Get current driver version
    driver_version=$(get_nvidia_driver_version)
    if [[ -z "$driver_version" ]]; then
        log_warning "Unable to determine NVIDIA driver version"
        log_warning "Skipping CDI configuration check"
        return 0
    fi
    
    log_info "Current NVIDIA driver version: $driver_version"
    
    # Read stored version from state file if it exists
    if [[ -f "$state_file" ]]; then
        stored_version=$(cat "$state_file" 2>/dev/null || echo "")
        log_info "Previously stored driver version: $stored_version"
    else
        log_info "No state file found - will create CDI configuration"
    fi
    
    # Check if we need to regenerate CDI configuration
    if [[ "$stored_version" != "$driver_version" ]]; then
        log_info "Driver version change detected (old: ${stored_version:-none}, new: $driver_version)"
        log_info "Regenerating rootless CDI configuration..."
        
        # Ensure CDI directory exists
        mkdir -p "$cdi_config_dir"
        
        # Check if nvidia-ctk is available
        if ! command -v nvidia-ctk >/dev/null 2>&1; then
            log_error "nvidia-ctk command not found - cannot generate CDI configuration"
            log_error "Please install nvidia-container-toolkit"
            return 1
        fi
        
        # Generate CDI configuration without sudo (rootless)
        if nvidia-ctk cdi generate --output="$cdi_config_file"; then
            log_success "Rootless CDI configuration generated successfully"
            
            # Update state file with new version
            echo "$driver_version" > "$state_file"
            log_success "Driver version state updated: $driver_version"
            
            # Verify the configuration was created
            if [[ -f "$cdi_config_file" ]]; then
                log_success "CDI configuration file created: $cdi_config_file"
                return 0
            else
                log_error "CDI configuration file was not created"
                return 1
            fi
        else
            log_error "Failed to generate CDI configuration with nvidia-ctk"
            log_error "Command: nvidia-ctk cdi generate --output=\"$cdi_config_file\""
            return 1
        fi
    else
        log_success "Driver version unchanged - CDI configuration is up to date"
        
        # Verify CDI config exists even if versions match
        if [[ ! -f "$cdi_config_file" ]]; then
            log_warning "CDI configuration file missing but versions match - regenerating..."
            mkdir -p "$cdi_config_dir"
            if nvidia-ctk cdi generate --output="$cdi_config_file"; then
                log_success "CDI configuration regenerated successfully"
            else
                log_error "Failed to regenerate missing CDI configuration"
                return 1
            fi
        fi
    fi
    
    return 0
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
                echo "  Available services: flaresolverr, prowlarr, sonarr,"
                echo "                     radarr, bazarr, gluetun, qbittorrent, jellyfin"
                echo ""
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
    
    # GPU availability check - required for Jellyfin
    if [[ -z "$SERVICES" || "$SERVICES" =~ jellyfin ]]; then
        log_info "Checking NVIDIA GPU availability for Jellyfin..."
        check_nvidia_gpu_availability 60
        log_success "NVIDIA GPU verified - proceeding with GPU acceleration"
        
        # Check and maintain NVIDIA CDI configuration for rootless Podman
        check_nvidia_cdi_configuration
    fi
    
    # Build the command
    CMD="$COMPOSE_CMD --env-file $ENV_FILE -f $COMPOSE_FILE up -d $BUILD_FLAG $FORCE_RECREATE $SERVICES"
    
    log_info "Executing: $CMD"
    
    # Execute the command
    local SUCCESS=false
    if $CMD; then
        SUCCESS=true
        log_success "Media stack started successfully!"
    
        echo ""
        log_info "Service status:"
        $COMPOSE_CMD --env-file $ENV_FILE -f $COMPOSE_FILE ps
        echo ""
        log_info "Useful commands:"
        echo "  View logs: ./scripts/podman-logs.sh"
        echo "  Stop stack: ./scripts/podman-down.sh"
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