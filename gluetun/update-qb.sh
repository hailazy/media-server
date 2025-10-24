#!/bin/sh
set -eu

# qBittorrent Port Updater - Enhanced with better error handling and debugging
# This script updates qBittorrent's listening port with the forwarded port from PIA

# Configuration with defaults
PORT_FILE="${PORT_FILE:-/tmp/gluetun/forwarded_port}"
QB_HOST="${QBIT_HOST:-127.0.0.1}"
QB_PORT="${QBIT_WEBUI_PORT:-8080}"
QB_USER="${QBIT_USER:-}"
QB_PASS="${QBIT_PASS:-}"
LOG_FILE="${LOG_FILE:-/tmp/gluetun/update-qb.log}"
TRIES="${TRIES:-120}"
SLEEP="${SLEEP:-2}"
DEBUG="${DEBUG:-false}"

# Derived configuration
BASE="http://${QB_HOST}:${QB_PORT}"
COOK="/tmp/gluetun/qb-cookies.txt"

# Logging functions with consistent format
log() {
    local level="$1"
    local message="$2"
    printf '%s [%s] %s\n' "$(date +'%F %T')" "$level" "$message" >>"$LOG_FILE"
    [ "$level" = "ERROR" ] && printf '%s [%s] %s\n' "$(date +'%F %T')" "$level" "$message" >&2
}

debug_log() {
    [ "$DEBUG" = "true" ] && log "DEBUG" "$1"
}

info_log() {
    log "INFO" "$1"
}

error_log() {
    log "ERROR" "$1"
}

warn_log() {
    log "WARN" "$1"
}

# URL encoding function for safe parameter passing
url_encode() {
    printf %s "$1" | sed -e 's/%/%25/g;s/&/%26/g;s/+/%2B/g;s/ /%20/g;s/"/%22/g;s/'"'"'/%27/g'
}

# Input validation
validate_inputs() {
    # Check if port file exists and is readable
    if [ ! -r "$PORT_FILE" ]; then
        error_log "Port file not found or not readable: $PORT_FILE"
        exit 1
    fi
    
    # Validate port number from file
    local port="$(tr -d '\r\n' <"$PORT_FILE")"
    case "$port" in 
        ''|*[!0-9]*) 
            error_log "Invalid port in file '$PORT_FILE': '$port'"
            exit 1
            ;; 
    esac
    
    if [ "$port" -lt 1024 ] || [ "$port" -gt 65535 ]; then
        error_log "Port out of valid range (1024-65535): $port"
        exit 1
    fi
    
    # Validate qBittorrent connection parameters
    if [ -z "$QB_HOST" ] || [ -z "$QB_PORT" ]; then
        error_log "qBittorrent host and port must be specified"
        exit 1
    fi
    
    debug_log "Input validation passed"
    echo "$port"
}

# qBittorrent authentication
qb_login() {
    if [ -z "$QB_USER" ]; then
        debug_log "No authentication credentials provided, attempting anonymous access"
        return 0
    fi
    
    if [ -z "$QB_PASS" ]; then
        error_log "QB_USER provided but QB_PASS is empty"
        exit 1
    fi
    
    info_log "Authenticating with qBittorrent..."
    debug_log "Attempting login for user: $QB_USER"
    
    # Clean up any existing session
    rm -f "$COOK"
    
    # Prepare authentication data
    local data="username=$(url_encode "$QB_USER")&password=$(url_encode "$QB_PASS")"
    local h1="--header=Referer: ${BASE}/"
    local h2="--header=Origin: ${BASE}"
    
    # Attempt login
    if wget -q -O /dev/null $h1 $h2 --save-cookies "$COOK" --keep-session-cookies \
        --header "Content-Type: application/x-www-form-urlencoded" \
        --post-data "$data" "${BASE}/api/v2/auth/login" 2>/dev/null; then
        debug_log "Authentication successful"
        return 0
    else
        warn_log "Authentication failed - falling back to anonymous access"
        rm -f "$COOK"
        return 1
    fi
}

# Set port in qBittorrent preferences
set_port() {
    local port="$1"
    local json=$(printf '{"random_port":false,"listen_port":%s}' "$port")
    local h1="--header=Referer: ${BASE}/"
    local h2="--header=Origin: ${BASE}"
    
    debug_log "Setting port to $port in qBittorrent"
    
    # Use cookies if available, otherwise try anonymous
    if [ -f "$COOK" ]; then
        wget -q -O /dev/null $h1 $h2 --load-cookies "$COOK" \
            --header "Content-Type: application/x-www-form-urlencoded" \
            --post-data "json=$(url_encode "$json")" "${BASE}/api/v2/app/setPreferences" \
            2>/dev/null
    else
        wget -q -O /dev/null $h1 $h2 \
            --header "Content-Type: application/x-www-form-urlencoded" \
            --post-data "json=$(url_encode "$json")" "${BASE}/api/v2/app/setPreferences" \
            2>/dev/null
    fi
}

# Read current port from qBittorrent
read_port() {
    local h1="--header=Referer: ${BASE}/"
    local h2="--header=Origin: ${BASE}"
    
    debug_log "Reading current port from qBittorrent"
    
    # Use cookies if available, otherwise try anonymous
    if [ -f "$COOK" ]; then
        wget -q -O - $h1 $h2 --load-cookies "$COOK" "${BASE}/api/v2/app/preferences" 2>/dev/null \
            | tr -d '\n' | sed -n 's/.*"listen_port":\([0-9][0-9]*\).*/\1/p'
    else
        wget -q -O - $h1 $h2 "${BASE}/api/v2/app/preferences" 2>/dev/null \
            | tr -d '\n' | sed -n 's/.*"listen_port":\([0-9][0-9]*\).*/\1/p'
    fi
}

# Health check - verify qBittorrent is accessible
health_check() {
    local h1="--header=Referer: ${BASE}/"
    local h2="--header=Origin: ${BASE}"
    
    debug_log "Performing qBittorrent health check"
    
    if wget -q -O /dev/null --timeout=5 $h1 $h2 "${BASE}/api/v2/app/version" 2>/dev/null; then
        debug_log "qBittorrent is accessible"
        return 0
    else
        error_log "qBittorrent is not accessible at $BASE"
        return 1
    fi
}

# Main execution
main() {
    info_log "Starting qBittorrent port update process"
    debug_log "Configuration: HOST=$QB_HOST, PORT=$QB_PORT, USER=${QB_USER:-<none>}"
    debug_log "Port file: $PORT_FILE, Max tries: $TRIES, Sleep: ${SLEEP}s"
    
    # Create log directory if needed
    mkdir -p "$(dirname "$LOG_FILE")"
    
    # Validate inputs and get target port
    local target_port
    target_port="$(validate_inputs)"
    info_log "Target port from PIA: $target_port"
    
    # Health check
    if ! health_check; then
        error_log "qBittorrent health check failed"
        exit 1
    fi
    
    # Attempt authentication
    qb_login
    
    # Try to update port with retry logic
    local attempt=1
    while [ $attempt -le "$TRIES" ]; do
        debug_log "Attempt $attempt/$TRIES to set port $target_port"
        
        # Set the port
        if set_port "$target_port"; then
            debug_log "Port set command executed successfully"
        else
            warn_log "Port set command failed on attempt $attempt"
        fi
        
        # Verify the change
        local current_port
        current_port="$(read_port || true)"
        
        if [ "$current_port" = "$target_port" ]; then
            info_log "qBittorrent listening port successfully updated to $target_port"
            exit 0
        else
            debug_log "Current port ($current_port) does not match target ($target_port)"
        fi
        
        # Sleep before retry (except on last attempt)
        if [ $attempt -lt "$TRIES" ]; then
            sleep "$SLEEP"
        fi
        
        attempt=$((attempt + 1))
    done
    
    # All attempts failed
    error_log "Failed to update qBittorrent port after $TRIES attempts"
    error_log "Target: $target_port, Current: ${current_port:-unknown}"
    exit 1
}

# Execute main function with error handling
if ! main "$@"; then
    error_log "Script execution failed"
    exit 1
fi