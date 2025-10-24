#!/bin/sh
set -Eeuo pipefail

# PIA Port Forwarding Runner - Optimized for use with pia-wggen
# This script focuses solely on port forwarding keepalive functionality
# Server selection and authentication are handled by pia-wggen

# Configuration with defaults
GLUETUN_DIR=${GLUETUN_DIR:-/gluetun}
STATUS_FILE=${VPN_PORT_FORWARDING_STATUS_FILE:-/tmp/gluetun/forwarded_port}
QB_SCRIPT=${QB_SCRIPT:-$GLUETUN_DIR/update-qb.sh}
QB_PORT=${QBIT_WEBUI_PORT:-8090}
CERT=${CERT:-$GLUETUN_DIR/ca.rsa.4096.crt}
CFG=${CFG:-$GLUETUN_DIR/wireguard/wg0.conf}
SLEEP_KEEPALIVE=${SLEEP_KEEPALIVE:-900}
RETRY_MAX=${RETRY_MAX:-30}
DEBUG=${DEBUG:-false}

# Logging function with timestamps
log() { 
    printf '%s [%s] %s\n' "$(date +'%F %T')" "${1:-INFO}" "${2:-$1}" >&2
}

debug_log() {
    [ "$DEBUG" = "true" ] && log "DEBUG" "$1"
}

error_exit() {
    log "ERROR" "$1"
    sleep 30
    exec "$0"
}

# Create required directories
mkdir -p "$(dirname "$STATUS_FILE")"

# Input validation
[ -f "$CFG" ] || error_exit "WireGuard config not found: $CFG"
[ -x "$QB_SCRIPT" ] || error_exit "qBittorrent script not found or not executable: $QB_SCRIPT"

# Wait for network connectivity
log "INFO" "Waiting for network connectivity..."
i=0
until getent hosts serverlist.piaservers.net >/dev/null 2>&1; do
    i=$((i+1))
    [ $i -gt 60 ] && error_exit "Network connectivity timeout after 120 seconds"
    sleep 2
done
debug_log "Network connectivity established"

# Extract endpoint information from WireGuard config
EP="$(awk -F'=' '/^Endpoint/ {gsub(/ /,""); print $2}' "$CFG" | head -n1)"
[ -n "$EP" ] || error_exit "No Endpoint found in $CFG"

EP_HOST=${EP%:*}
EP_PORT=${EP##*:}
log "INFO" "Using WireGuard endpoint: $EP_HOST:$EP_PORT"

# Resolve hostname to IP for port forwarding gateway
case "$EP_HOST" in
    *[a-zA-Z]*) 
        PF_GATEWAY="$(getent hosts "$EP_HOST" | awk '{print $1}' | head -n1 || true)"
        PF_HOSTNAME="$EP_HOST"
        ;;
    *) 
        PF_GATEWAY="$EP_HOST"
        # For IP endpoints, we need to determine the hostname
        # This should be rare since pia-wggen provides hostnames
        PF_HOSTNAME="$EP_HOST"
        ;;
esac

[ -n "$PF_GATEWAY" ] || error_exit "Cannot resolve gateway IP from endpoint: $EP_HOST"
debug_log "Port forwarding gateway: $PF_GATEWAY"
debug_log "Port forwarding hostname: $PF_HOSTNAME"

# Download CA certificate if needed
if [ ! -s "$CERT" ]; then
    log "INFO" "Downloading PIA CA certificate..."
    wget -qO "$CERT" https://raw.githubusercontent.com/pia-foss/manual-connections/master/ca.rsa.4096.crt || \
        error_exit "Failed to download CA certificate"
    debug_log "CA certificate downloaded successfully"
fi

# Authentication token handling
get_token() {
    if [ -n "${PIA_TOKEN:-}" ]; then
        debug_log "Using provided PIA_TOKEN"
        return 0
    fi
    
    if [ -z "${PIA_USER:-}" ] || [ -z "${PIA_PASS:-}" ]; then
        error_exit "Authentication required: set PIA_TOKEN or both PIA_USER and PIA_PASS"
    fi
    
    log "INFO" "Authenticating with PIA..."
    PIA_TOKEN="$(curl -fsS --location --request POST \
        'https://www.privateinternetaccess.com/api/client/v2/token' \
        --form "username=$PIA_USER" --form "password=$PIA_PASS" | jq -r '.token')"
    
    [ -n "$PIA_TOKEN" ] && [ "$PIA_TOKEN" != "null" ] || \
        error_exit "Authentication failed - check PIA_USER and PIA_PASS"
    
    debug_log "Authentication successful"
}

# Request port forwarding signature
request_signature() {
    local host="$1" gateway="$2"
    debug_log "Requesting signature from $host via $gateway"
    
    curl -fsS -m 10 \
        --connect-to "$host::$gateway:" \
        --cacert "$CERT" \
        -G --data-urlencode "token=$PIA_TOKEN" \
        "https://$host:19999/getSignature"
}

# Update qBittorrent with new port
update_qbittorrent() {
    local port="$1"
    debug_log "Updating qBittorrent with port $port"
    
    PORT_FILE="$STATUS_FILE" QBIT_HOST=127.0.0.1 QBIT_WEBUI_PORT="$QB_PORT" \
        QBIT_USER="${QBIT_USER:-}" QBIT_PASS="${QBIT_PASS:-}" sh "$QB_SCRIPT" || {
        log "WARN" "Failed to update qBittorrent - will retry later"
        return 1
    }
}

# Main execution
log "INFO" "Starting PIA port forwarding for endpoint $EP_HOST"

# Get authentication token
get_token

# Request initial port forwarding signature
log "INFO" "Requesting port forwarding signature..."
SIGJSON="$(request_signature "$PF_HOSTNAME" "$PF_GATEWAY")" || \
    error_exit "Failed to get port forwarding signature from $PF_HOSTNAME"

# Validate and extract signature data
[ "$(echo "$SIGJSON" | jq -r '.status // empty')" = "OK" ] || \
    error_exit "Port forwarding not available for this server"

payload="$(echo "$SIGJSON" | jq -r '.payload')"
signature="$(echo "$SIGJSON" | jq -r '.signature')"
port="$(echo "$payload" | base64 -d | jq -r '.port')"
expires_at="$(echo "$payload" | base64 -d | jq -r '.expires_at')"

# Validate extracted data
[ -n "$port" ] && [ "$port" != "null" ] || error_exit "Invalid port in signature response"
[ -n "$expires_at" ] && [ "$expires_at" != "null" ] || error_exit "Invalid expiration in signature response"

# Save port and update qBittorrent
echo "$port" > "$STATUS_FILE"
log "INFO" "Port forwarding established: $port (expires: $expires_at)"
update_qbittorrent "$port"

# Port forwarding keepalive loop
log "INFO" "Starting keepalive loop (interval: ${SLEEP_KEEPALIVE}s)"
n=0
while :; do
    debug_log "Keepalive attempt $((n+1))"
    
    # Send keepalive request
    resp="$(curl -fsS -m 10 -G \
        --connect-to "$PF_HOSTNAME::$PF_GATEWAY:" \
        --cacert "$CERT" \
        --data-urlencode "payload=$payload" \
        --data-urlencode "signature=$signature" \
        "https://$PF_HOSTNAME:19999/bindPort" || true)"
    
    if [ "$(echo "$resp" | jq -r '.status // empty')" != "OK" ]; then
        log "WARN" "Keepalive failed, requesting new signature..."
        
        # Request new signature with retry logic
        for retry in 1 2 3 5 8; do
            new_sig="$(request_signature "$PF_HOSTNAME" "$PF_GATEWAY" || true)"
            if [ "$(echo "$new_sig" | jq -r '.status // empty')" = "OK" ]; then
                payload="$(echo "$new_sig" | jq -r '.payload')"
                signature="$(echo "$new_sig" | jq -r '.signature')"
                port="$(echo "$payload" | base64 -d | jq -r '.port')"
                
                echo "$port" > "$STATUS_FILE"
                log "INFO" "Port forwarding renewed: $port"
                update_qbittorrent "$port"
                break
            fi
            
            log "WARN" "Signature renewal failed, retrying in ${retry}s..."
            sleep "$retry"
        done
    else
        debug_log "Keepalive successful"
        
        # Refresh qBittorrent periodically (every hour)
        if [ $((n % (3600 / SLEEP_KEEPALIVE))) -eq 0 ] && [ $n -gt 0 ]; then
            log "INFO" "Periodic qBittorrent refresh"
            update_qbittorrent "$port"
        fi
    fi
    
    n=$((n+1))
    sleep "$SLEEP_KEEPALIVE"
done