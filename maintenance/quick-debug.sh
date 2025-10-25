#!/bin/bash
# Quick Debug Script - Fast troubleshooting for Media Stack
# Usage: ./quick-debug.sh [check|vpn|port|services|all]

set -euo pipefail

# Determine project paths based on where script is called from
if [[ "$(basename "$(pwd)")" == "maintenance" ]]; then
    # Called directly from maintenance directory
    PROJECT_ROOT=".."
    COMPOSE_FILE="../core/podman-compose.yml"
    ENV_FILE="../.env"
else
    # Called via wrapper from root directory
    PROJECT_ROOT="."
    COMPOSE_FILE="core/podman-compose.yml"
    ENV_FILE=".env"
fi

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo_info() { echo -e "${GREEN}✓${NC} $1"; }
echo_warn() { echo -e "${YELLOW}⚠${NC} $1"; }
echo_error() { echo -e "${RED}✗${NC} $1"; }
echo_debug() { echo -e "${BLUE}ℹ${NC} $1"; }

check_basic() {
    echo -e "\n${BLUE}=== Basic System Check ===${NC}"
    
    # Podman
    if command -v podman &> /dev/null; then
        echo_info "Podman installed: $(podman --version | cut -d' ' -f3)"
    else
        echo_error "Podman not found"
    fi
    
    # Podman Compose
    if command -v podman-compose &> /dev/null; then
        echo_info "Podman Compose installed: $(podman-compose --version | cut -d' ' -f4)"
    else
        echo_error "Podman Compose not found"
    fi
    
    # Environment file
    if [[ -f "$ENV_FILE" ]]; then
        echo_info "Environment file exists"
        if grep -q "PIA_USER=" "$ENV_FILE" && grep -q "PIA_PASS=" "$ENV_FILE"; then
            echo_info "PIA credentials configured"
        else
            echo_warn "PIA credentials missing in $ENV_FILE"
        fi
    else
        echo_error "Environment file missing - copy from ${PROJECT_ROOT}/core/.env.example"
    fi
    
    # Media directories
    if [[ -d "/media/Storage" ]]; then
        echo_info "Media storage directory exists"
        echo_debug "Available space: $(df -h /media/Storage | tail -1 | awk '{print $4}')"
    else
        echo_warn "Media storage directory not found: /media/Storage"
    fi
}

check_services() {
    echo -e "\n${BLUE}=== Podman Services Check ===${NC}"
    
    if podman-compose -f "$COMPOSE_FILE" ps &> /dev/null; then
        local running_services=$(podman-compose -f "$COMPOSE_FILE" ps --services --filter status=running | wc -l)
        local total_services=$(podman-compose -f "$COMPOSE_FILE" ps --services | wc -l)
        
        if [[ $running_services -eq $total_services ]]; then
            echo_info "All services running ($running_services/$total_services)"
        else
            echo_warn "Some services not running ($running_services/$total_services)"
            echo_debug "Run: podman-compose -f $COMPOSE_FILE ps"
        fi
        
        # Check for unhealthy services
        local unhealthy=$(podman-compose -f "$COMPOSE_FILE" ps --filter health=unhealthy --format "{{.Service}}" 2>/dev/null || true)
        if [[ -n "$unhealthy" ]]; then
            echo_error "Unhealthy services: $unhealthy"
        fi
    else
        echo_warn "No services running or podman-compose not available"
        echo_debug "Start with: ${PROJECT_ROOT}/start.sh"
    fi
}

check_vpn() {
    echo -e "\n${BLUE}=== VPN Check ===${NC}"
    
    # Check if gluetun is running
    if podman-compose -f "$COMPOSE_FILE" ps gluetun | grep -q "Up"; then
        echo_info "Gluetun VPN service is running"
        
        # Test VPN IP
        local vpn_ip=$(podman-compose -f "$COMPOSE_FILE" exec -T gluetun wget -qO- https://ipinfo.io/ip 2>/dev/null || echo "failed")
        if [[ "$vpn_ip" != "failed" ]]; then
            echo_info "VPN IP: $vpn_ip"
            
            # Compare with host IP
            local host_ip=$(wget -qO- https://ipinfo.io/ip 2>/dev/null || echo "unknown")
            if [[ "$vpn_ip" != "$host_ip" ]]; then
                echo_info "VPN is working correctly (IP differs from host)"
            else
                echo_warn "VPN IP matches host IP - check VPN connection"
            fi
        else
            echo_error "Cannot reach internet through VPN"
        fi
        
        # Check WireGuard config
        if podman-compose -f "$COMPOSE_FILE" exec -T gluetun ls /gluetun/wireguard/wg0.conf &> /dev/null; then
            echo_info "WireGuard config found"
        else
            echo_warn "WireGuard config missing - regenerate with: podman-compose -f $COMPOSE_FILE run --rm pia-wggen"
        fi
    else
        echo_error "Gluetun VPN service not running"
        echo_debug "Check logs with: podman-compose -f $COMPOSE_FILE logs gluetun"
    fi
}

check_port_forwarding() {
    echo -e "\n${BLUE}=== Port Forwarding Check ===${NC}"
    
    # Check if pia-pf is running
    if podman-compose -f "$COMPOSE_FILE" ps pia-pf | grep -q "Up"; then
        echo_info "PIA port forwarding service is running"
        
        # Check for forwarded port
        local port_file="/tmp/gluetun/forwarded_port"
        local forwarded_port=$(podman-compose -f "$COMPOSE_FILE" exec -T gluetun cat "$port_file" 2>/dev/null | tr -d '\r\n' || echo "")
        
        if [[ -n "$forwarded_port" ]] && [[ "$forwarded_port" =~ ^[0-9]+$ ]]; then
            echo_info "Forwarded port: $forwarded_port"
            
            # Check qBittorrent port
            local qb_port=$(podman-compose -f "$COMPOSE_FILE" exec -T gluetun wget -qO- http://127.0.0.1:8080/api/v2/app/preferences 2>/dev/null | grep -o '"listen_port":[0-9]*' | cut -d: -f2 || echo "unknown")
            if [[ "$qb_port" == "$forwarded_port" ]]; then
                echo_info "qBittorrent port matches forwarded port"
            else
                echo_warn "qBittorrent port ($qb_port) doesn't match forwarded port ($forwarded_port)"
            fi
        else
            echo_warn "No valid forwarded port found"
            echo_debug "Check logs with: podman-compose -f $COMPOSE_FILE logs pia-pf"
        fi
    else
        echo_error "PIA port forwarding service not running"
    fi
}

show_quick_commands() {
    echo -e "\n${BLUE}=== Quick Commands ===${NC}"
    echo "Start services:          ${PROJECT_ROOT}/start.sh"
    echo "Restart VPN:             podman-compose -f $COMPOSE_FILE restart gluetun pia-pf"
    echo "Regenerate VPN config:   podman-compose -f $COMPOSE_FILE run --rm pia-wggen"
    echo "View all logs:           podman-compose -f $COMPOSE_FILE logs -f"
    echo "View VPN logs:           podman-compose -f $COMPOSE_FILE logs -f gluetun"
    echo "View port forward logs:  podman-compose -f $COMPOSE_FILE logs -f pia-pf"
    echo "Health check:            ./maintenance.sh health"
    echo "Full diagnostic:         ./maintenance.sh diagnostic"
    echo "Enable debug mode:       ./maintenance.sh debug-enable"
}

case "${1:-all}" in
    "check"|"basic")
        check_basic
        ;;
    "vpn")
        check_vpn
        ;;
    "port")
        check_port_forwarding
        ;;
    "services")
        check_services
        ;;
    "all")
        check_basic
        check_services
        check_vpn
        check_port_forwarding
        show_quick_commands
        ;;
    *)
        echo "Usage: $0 [check|vpn|port|services|all]"
        echo ""
        echo "Commands:"
        echo "  check     - Basic system check"
        echo "  vpn       - VPN connectivity check"
        echo "  port      - Port forwarding check"
        echo "  services  - Podman services check"
        echo "  all       - Run all checks (default)"
        exit 1
        ;;
esac