#!/bin/bash
# Shared library for home-server scripts.
# Source via: source "${SCRIPT_DIR}/_lib.sh"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $1"; }

check_podman_setup() {
    if ! command -v podman >/dev/null 2>&1; then
        log_error "Podman not found"
        exit 1
    fi
    if [[ $EUID -ne 0 ]] && ! podman info >/dev/null 2>&1; then
        log_warning "Rootless podman not configured — try: podman system migrate"
    fi
}

check_podman_compose() {
    if command -v podman-compose >/dev/null 2>&1; then
        COMPOSE_CMD="podman-compose"
    elif command -v docker-compose >/dev/null 2>&1 && command -v podman >/dev/null 2>&1; then
        COMPOSE_CMD="docker-compose"
        log_warning "Using docker-compose with podman backend"
    else
        log_error "Neither podman-compose nor docker-compose found"
        exit 1
    fi
}

check_section_env() {
    local section="$1"
    local env_file="${ROOT_DIR}/${section}/.env"
    local example_file="${ROOT_DIR}/${section}/.env.example"

    if [[ ! -f "$env_file" && -f "$example_file" ]]; then
        log_warning ".env missing for ${section}"
        log_info "  cp ${example_file} ${env_file} && \$EDITOR ${env_file}"
        exit 1
    fi
}

ensure_home_network() {
    # Shared network for cross-section service discovery (forge ↔ sillytavern ↔ dashboard)
    if ! podman network exists home-net 2>/dev/null; then
        log_info "Creating home-net podman network"
        podman network create home-net >/dev/null
    fi
}

# NVIDIA GPU helpers — for media (Jellyfin NVENC) and forge (SD generation)

check_nvidia_gpu_availability() {
    local timeout=${1:-60}
    local required=("/dev/nvidia-uvm" "/dev/nvidia0" "/dev/nvidiactl")
    local elapsed=0

    log_info "Checking NVIDIA GPU devices (timeout ${timeout}s)..."
    while (( elapsed < timeout )); do
        local missing=0
        for d in "${required[@]}"; do
            [[ -e "$d" ]] || missing=$((missing+1))
        done
        if (( missing == 0 )); then
            log_success "NVIDIA devices available"
            return 0
        fi
        sleep 2
        elapsed=$((elapsed + 2))
    done
    log_error "NVIDIA devices not available after ${timeout}s — GPU required"
    exit 1
}

check_nvidia_cdi_configuration() {
    local cdi_dir="${HOME}/.config/containers/cdi"
    local cdi_file="${cdi_dir}/nvidia.yaml"
    local state_file="${cdi_dir}/nvidia-driver-version.txt"
    local current_ver stored_ver

    current_ver=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader,nounits 2>/dev/null | head -1 | tr -d '[:space:]')
    [[ -z "$current_ver" ]] && { log_warning "Cannot detect NVIDIA driver — skipping CDI check"; return 0; }

    [[ -f "$state_file" ]] && stored_ver=$(cat "$state_file" 2>/dev/null) || stored_ver=""

    if [[ "$stored_ver" != "$current_ver" || ! -f "$cdi_file" ]]; then
        log_info "Regenerating CDI for driver $current_ver (was: ${stored_ver:-none})"
        mkdir -p "$cdi_dir"
        if ! command -v nvidia-ctk >/dev/null 2>&1; then
            log_error "nvidia-ctk not found — install nvidia-container-toolkit"
            exit 1
        fi
        if nvidia-ctk cdi generate --output="$cdi_file"; then
            echo "$current_ver" > "$state_file"
            log_success "CDI configuration updated"
        else
            log_error "Failed to generate CDI config"
            exit 1
        fi
    else
        log_success "CDI config up to date (driver $current_ver)"
    fi
}
