#!/bin/bash
set -euo pipefail

# =============================================================================
#                         MEDIA STACK MAINTENANCE SCRIPT
# =============================================================================
# Comprehensive maintenance, debugging, and health check tool for media-stack
# Provides automated troubleshooting, system monitoring, and cleanup utilities
#
# Usage: ./maintenance.sh [COMMAND] [OPTIONS]
# Commands: health, logs, diagnostic, cleanup, debug-enable, debug-disable
# =============================================================================

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${SCRIPT_DIR}/logs"
TEMP_DIR="${SCRIPT_DIR}/tmp"
COMPOSE_FILE="${SCRIPT_DIR}/podman-compose.yml"
ENV_FILE="${SCRIPT_DIR}/.env"
DEBUG_LOG_FILE="${LOG_DIR}/maintenance-debug.log"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') $1" | tee -a "${DEBUG_LOG_FILE}"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $(date '+%Y-%m-%d %H:%M:%S') $1" | tee -a "${DEBUG_LOG_FILE}"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') $1" | tee -a "${DEBUG_LOG_FILE}"
}

log_debug() {
    echo -e "${BLUE}[DEBUG]${NC} $(date '+%Y-%m-%d %H:%M:%S') $1" | tee -a "${DEBUG_LOG_FILE}"
}

log_section() {
    echo -e "\n${PURPLE}=== $1 ===${NC}" | tee -a "${DEBUG_LOG_FILE}"
}

# Initialize log directory
mkdir -p "${LOG_DIR}" "${TEMP_DIR}"

# =============================================================================
#                            HEALTH CHECK FUNCTIONS
# =============================================================================

check_podman_compose() {
    log_debug "Checking podman-compose availability..."
    if ! command -v podman-compose &> /dev/null; then
        log_error "podman-compose not found. Please install Podman Compose."
        return 1
    fi
    log_info "Podman Compose: $(podman-compose --version)"
    return 0
}

check_environment_file() {
    log_debug "Checking environment configuration..."
    if [[ ! -f "$ENV_FILE" ]]; then
        log_error "Environment file not found: $ENV_FILE"
        log_info "Create it from .env.example: cp .env.example .env"
        return 1
    fi
    
    # Check for required variables
    local required_vars=("PIA_USER" "PIA_PASS" "QBIT_USER" "QBIT_PASS")
    local missing_vars=()
    
    for var in "${required_vars[@]}"; do
        if ! grep -q "^${var}=" "$ENV_FILE" || grep -q "^${var}=$" "$ENV_FILE"; then
            missing_vars+=("$var")
        fi
    done
    
    if [[ ${#missing_vars[@]} -gt 0 ]]; then
        log_error "Missing required environment variables: ${missing_vars[*]}"
        return 1
    fi
    
    log_info "Environment configuration: ✓"
    return 0
}

check_services_status() {
    log_debug "Checking Podman services status..."
    local services_output
    services_output=$(podman-compose ps --format table 2>/dev/null || true)
    
    if [[ -z "$services_output" ]]; then
        log_warn "No services found or podman-compose not running"
        return 1
    fi
    
    echo "$services_output"
    
    # Check if any services are unhealthy
    local unhealthy_services
    unhealthy_services=$(podman-compose ps --filter status=unhealthy --format "{{.Service}}" 2>/dev/null || true)
    
    if [[ -n "$unhealthy_services" ]]; then
        log_warn "Unhealthy services detected: $unhealthy_services"
        return 1
    fi
    
    log_info "All services appear healthy"
    return 0
}

check_vpn_connectivity() {
    log_debug "Testing VPN connectivity..."
    local vpn_ip
    vpn_ip=$(podman-compose exec -T gluetun wget -qO- https://ipinfo.io/ip 2>/dev/null || echo "failed")
    
    if [[ "$vpn_ip" == "failed" ]]; then
        log_error "VPN connectivity test failed"
        return 1
    fi
    
    log_info "VPN IP: $vpn_ip"
    
    # Check if IP is different from host IP
    local host_ip
    host_ip=$(wget -qO- https://ipinfo.io/ip 2>/dev/null || echo "unknown")
    
    if [[ "$vpn_ip" == "$host_ip" ]]; then
        log_warn "VPN IP matches host IP - VPN may not be working correctly"
        return 1
    fi
    
    log_info "VPN connectivity: ✓"
    return 0
}

check_port_forwarding() {
    log_debug "Checking port forwarding status..."
    local forwarded_port_file="/tmp/gluetun/forwarded_port"
    
    # Try to get forwarded port from container
    local forwarded_port
    forwarded_port=$(podman-compose exec -T gluetun cat "$forwarded_port_file" 2>/dev/null | tr -d '\r\n' || echo "")
    
    if [[ -z "$forwarded_port" ]] || [[ ! "$forwarded_port" =~ ^[0-9]+$ ]]; then
        log_warn "No valid forwarded port found"
        return 1
    fi
    
    log_info "Forwarded port: $forwarded_port"
    
    # Test port accessibility
    log_debug "Testing port accessibility..."
    local port_test_result
    port_test_result=$(podman-compose exec -T gluetun timeout 10 nc -z portchecker.co 80 2>/dev/null && echo "success" || echo "failed")
    
    if [[ "$port_test_result" == "failed" ]]; then
        log_warn "Port connectivity test failed"
        return 1
    fi
    
    log_info "Port forwarding: ✓"
    return 0
}

check_qbittorrent_connectivity() {
    log_debug "Testing qBittorrent connectivity..."
    local qb_response
    qb_response=$(podman-compose exec -T gluetun wget -qO- --timeout=5 http://127.0.0.1:8090/api/v2/app/version 2>/dev/null || echo "failed")
    
    if [[ "$qb_response" == "failed" ]]; then
        log_error "qBittorrent not accessible"
        return 1
    fi
    
    log_info "qBittorrent version: $qb_response"
    return 0
}

check_service_connectivity() {
    log_debug "Testing inter-service connectivity..."
    local services=("prowlarr:9696" "sonarr:8989" "radarr:7878" "bazarr:6767" "jellyfin:8096")
    local failed_services=()
    
    for service in "${services[@]}"; do
        local service_name="${service%:*}"
        local service_port="${service#*:}"
        
        if ! podman-compose exec -T "$service_name" timeout 5 curl -s "http://localhost:$service_port" &>/dev/null; then
            failed_services+=("$service_name")
        fi
    done
    
    if [[ ${#failed_services[@]} -gt 0 ]]; then
        log_warn "Services not responding: ${failed_services[*]}"
        return 1
    fi
    
    log_info "Service connectivity: ✓"
    return 0
}

# =============================================================================
#                            DIAGNOSTIC FUNCTIONS
# =============================================================================

collect_system_info() {
    log_section "System Information"
    
    {
        echo "Date: $(date)"
        echo "Hostname: $(hostname)"
        echo "OS: $(uname -a)"
        echo "Podman version: $(podman --version 2>/dev/null || echo 'Not found')"
        echo "Podman Compose version: $(podman-compose --version 2>/dev/null || echo 'Not found')"
        echo "Available disk space:"
        df -h
        echo ""
        echo "Memory usage:"
        free -h
        echo ""
        echo "CPU info:"
        lscpu | head -20
    } | tee "${LOG_DIR}/system-info.log"
}

collect_container_stats() {
    log_section "Container Statistics"
    
    {
        echo "Container status:"
        podman-compose ps
        echo ""
        echo "Container resource usage:"
        podman stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}"
        echo ""
        echo "Container images:"
        podman-compose images
    } | tee "${LOG_DIR}/container-stats.log"
}

collect_network_info() {
    log_section "Network Information"
    
    {
        echo "Network connectivity tests:"
        echo "Google DNS: $(ping -c 1 8.8.8.8 &>/dev/null && echo 'OK' || echo 'FAILED')"
        echo "PIA servers: $(ping -c 1 serverlist.piaservers.net &>/dev/null && echo 'OK' || echo 'FAILED')"
        echo ""
        echo "Podman networks:"
        podman network ls
        echo ""
        echo "Active network connections:"
        netstat -tuln | head -20
    } | tee "${LOG_DIR}/network-info.log"
}

collect_service_logs() {
    log_section "Service Logs Collection"
    local services=("gluetun" "pia-wggen" "pia-pf" "qbittorrent" "prowlarr" "sonarr" "radarr" "bazarr" "jellyfin")
    
    for service in "${services[@]}"; do
        log_debug "Collecting logs for $service..."
        podman-compose logs --tail=100 "$service" > "${LOG_DIR}/${service}-logs.log" 2>&1 || true
    done
    
    log_info "Service logs collected in ${LOG_DIR}/"
}

run_connectivity_tests() {
    log_section "Connectivity Tests"
    
    {
        echo "Testing external connectivity:"
        echo "- Google: $(curl -s --max-time 5 https://www.google.com &>/dev/null && echo 'OK' || echo 'FAILED')"
        echo "- PIA API: $(curl -s --max-time 5 https://www.privateinternetaccess.com/api/client/v2/token &>/dev/null && echo 'OK' || echo 'FAILED')"
        echo "- Port checker: $(curl -s --max-time 5 https://portchecker.co &>/dev/null && echo 'OK' || echo 'FAILED')"
        echo ""
        echo "Testing internal service connectivity:"
        
        if podman-compose ps | grep -q "gluetun"; then
            echo "- VPN container accessible: $(podman-compose exec -T gluetun echo 'OK' 2>/dev/null || echo 'FAILED')"
            echo "- qBittorrent via VPN: $(podman-compose exec -T gluetun wget -qO- --timeout=5 http://127.0.0.1:8090 &>/dev/null && echo 'OK' || echo 'FAILED')"
        fi
    } | tee "${LOG_DIR}/connectivity-tests.log"
}

# =============================================================================
#                            CLEANUP FUNCTIONS
# =============================================================================

cleanup_old_logs() {
    log_debug "Cleaning up old log files..."
    
    # Remove logs older than 7 days
    find "${LOG_DIR}" -type f -name "*.log" -mtime +7 -delete 2>/dev/null || true
    
    # Clean up Podman logs
    podman system prune -f --filter "until=168h" &>/dev/null || true
    
    # Clean up gluetun temporary files
    podman-compose exec -T gluetun find /tmp -name "*.tmp" -mtime +1 -delete 2>/dev/null || true
    
    log_info "Old logs and temporary files cleaned up"
}

cleanup_podman_resources() {
    log_debug "Cleaning up unused Podman resources..."
    
    # Remove unused containers, networks, images
    podman system prune -af --filter "until=24h" &>/dev/null || true
    
    # Remove unused volumes (be careful with this)
    podman volume prune -f &>/dev/null || true
    
    log_info "Podman resources cleaned up"
}

# =============================================================================
#                            DEBUG MANAGEMENT FUNCTIONS
# =============================================================================

enable_debug_mode() {
    log_section "Enabling Debug Mode"
    
    if [[ ! -f "$ENV_FILE" ]]; then
        log_error "Environment file not found: $ENV_FILE"
        return 1
    fi
    
    # Backup current .env file
    cp "$ENV_FILE" "${ENV_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
    
    # Enable debug mode
    if grep -q "^DEBUG=" "$ENV_FILE"; then
        sed -i 's/^DEBUG=.*/DEBUG=true/' "$ENV_FILE"
    else
        echo "DEBUG=true" >> "$ENV_FILE"
    fi
    
    log_info "Debug mode enabled. Restart services to apply changes:"
    log_info "podman-compose restart"
    
    # Show what will change
    log_debug "Services that will show enhanced logging:"
    echo "  - pia_pf_runner.sh (PIA port forwarding)"
    echo "  - update-qb.sh (qBittorrent port updates)"
    echo "  - Container startup processes"
}

disable_debug_mode() {
    log_section "Disabling Debug Mode"
    
    if [[ ! -f "$ENV_FILE" ]]; then
        log_error "Environment file not found: $ENV_FILE"
        return 1
    fi
    
    # Backup current .env file
    cp "$ENV_FILE" "${ENV_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
    
    # Disable debug mode
    if grep -q "^DEBUG=" "$ENV_FILE"; then
        sed -i 's/^DEBUG=.*/DEBUG=false/' "$ENV_FILE"
    else
        echo "DEBUG=false" >> "$ENV_FILE"
    fi
    
    log_info "Debug mode disabled. Restart services to apply changes:"
    log_info "podman-compose restart"
}

# =============================================================================
#                            TROUBLESHOOTING FUNCTIONS
# =============================================================================

troubleshoot_vpn_issues() {
    log_section "VPN Troubleshooting"
    
    {
        echo "VPN Configuration Status:"
        echo "- WireGuard config exists: $([[ -f "gluetun/wireguard/wg0.conf" ]] && echo 'YES' || echo 'NO')"
        echo "- Volume mounted config: $(podman-compose exec -T gluetun ls -la /gluetun/wireguard/ 2>/dev/null | grep wg0.conf || echo 'NOT FOUND')"
        echo ""
        
        echo "PIA-WGGen Status:"
        podman-compose logs --tail=20 pia-wggen 2>/dev/null || echo "pia-wggen logs not available"
        echo ""
        
        echo "Gluetun VPN Status:"
        podman-compose logs --tail=20 gluetun | grep -E "(VPN|connection|error)" || echo "No VPN status messages found"
        echo ""
        
        echo "Suggested Actions:"
        echo "1. Regenerate WireGuard config: podman-compose run --rm pia-wggen"
        echo "2. Restart VPN services: podman-compose restart gluetun pia-pf"
        echo "3. Check PIA credentials in .env file"
        echo "4. Verify PIA subscription is active"
    } | tee "${LOG_DIR}/vpn-troubleshooting.log"
}

troubleshoot_port_forwarding() {
    log_section "Port Forwarding Troubleshooting"
    
    {
        echo "Port Forwarding Status:"
        echo "- PIA subscription supports PF: Check your PIA account"
        echo "- Port forwarding enabled: $(grep PIA_PF .env 2>/dev/null || echo 'NOT SET')"
        echo ""
        
        echo "PIA Port Forwarding Logs:"
        podman-compose logs --tail=30 pia-pf 2>/dev/null | grep -E "(port|forward|error)" || echo "No port forwarding logs found"
        echo ""
        
        echo "Current forwarded port:"
        podman-compose exec -T gluetun cat /tmp/gluetun/forwarded_port 2>/dev/null || echo "No forwarded port file found"
        echo ""
        
        echo "Suggested Actions:"
        echo "1. Verify PIA_PF=true in .env file"
        echo "2. Check PIA subscription includes port forwarding"
        echo "3. Restart port forwarding: podman-compose restart pia-pf"
        echo "4. Try different PIA server region"
    } | tee "${LOG_DIR}/port-forwarding-troubleshooting.log"
}

troubleshoot_download_issues() {
    log_section "Download Issues Troubleshooting"
    
    {
        echo "qBittorrent Status:"
        echo "- Service accessible: $(check_qbittorrent_connectivity &>/dev/null && echo 'YES' || echo 'NO')"
        echo "- Current listening port: $(podman-compose exec -T gluetun wget -qO- http://127.0.0.1:8090/api/v2/app/preferences 2>/dev/null | grep -o '"listen_port":[0-9]*' | cut -d: -f2 || echo 'UNKNOWN')"
        echo ""
        
        echo "Storage Status:"
        echo "- Downloads directory exists: $([[ -d "/media/Storage/downloads" ]] && echo 'YES' || echo 'NO')"
        echo "- Available space: $(df -h /media/Storage 2>/dev/null | tail -1 | awk '{print $4}' || echo 'UNKNOWN')"
        echo ""
        
        echo "Recent qBittorrent logs:"
        podman-compose logs --tail=20 qbittorrent 2>/dev/null | grep -E "(error|warn|torrent)" || echo "No relevant logs found"
        echo ""
        
        echo "Suggested Actions:"
        echo "1. Check available disk space"
        echo "2. Verify port forwarding is working"
        echo "3. Test manual torrent download"
        echo "4. Check indexer connectivity in Prowlarr"
    } | tee "${LOG_DIR}/download-troubleshooting.log"
}

# =============================================================================
#                            MAIN EXECUTION FUNCTIONS
# =============================================================================

run_health_check() {
    log_section "Media Stack Health Check"
    
    local checks=(
        "check_podman_compose"
        "check_environment_file"
        "check_services_status"
        "check_vpn_connectivity"
        "check_port_forwarding"
        "check_qbittorrent_connectivity"
        "check_service_connectivity"
    )
    
    local failed_checks=0
    
    for check in "${checks[@]}"; do
        if ! $check; then
            ((failed_checks++))
        fi
    done
    
    echo ""
    if [[ $failed_checks -eq 0 ]]; then
        log_info "✅ All health checks passed!"
    else
        log_warn "⚠️  $failed_checks health check(s) failed"
        log_info "Run './maintenance.sh diagnostic' for detailed troubleshooting"
    fi
    
    return $failed_checks
}

run_full_diagnostic() {
    log_section "Full System Diagnostic"
    
    collect_system_info
    collect_container_stats
    collect_network_info
    collect_service_logs
    run_connectivity_tests
    troubleshoot_vpn_issues
    troubleshoot_port_forwarding
    troubleshoot_download_issues
    
    log_info "📋 Full diagnostic completed. Results saved in ${LOG_DIR}/"
    log_info "📧 Share these logs when seeking support"
}

run_cleanup() {
    log_section "System Cleanup"
    
    cleanup_old_logs
    cleanup_podman_resources
    
    log_info "🧹 Cleanup completed"
}

show_logs() {
    local service="${1:-all}"
    local lines="${2:-50}"
    
    log_section "Service Logs"
    
    if [[ "$service" == "all" ]]; then
        log_info "Showing recent logs for all services (last $lines lines each):"
        podman-compose logs --tail="$lines"
    else
        log_info "Showing recent logs for $service (last $lines lines):"
        podman-compose logs --tail="$lines" "$service"
    fi
}

show_help() {
    cat << EOF
Media Stack Maintenance Script

USAGE:
    ./maintenance.sh [COMMAND] [OPTIONS]

COMMANDS:
    health              Run comprehensive health checks
    logs [SERVICE]      Show logs for service (default: all services)
    diagnostic          Run full system diagnostic and collect logs
    cleanup             Clean up old logs and unused Podman resources
    debug-enable        Enable debug mode for enhanced logging
    debug-disable       Disable debug mode
    troubleshoot-vpn    Run VPN-specific troubleshooting
    troubleshoot-pf     Run port forwarding troubleshooting
    troubleshoot-dl     Run download issues troubleshooting
    help                Show this help message

EXAMPLES:
    ./maintenance.sh health                    # Run health checks
    ./maintenance.sh logs gluetun             # Show gluetun logs
    ./maintenance.sh logs all 100             # Show last 100 lines for all services
    ./maintenance.sh diagnostic               # Full diagnostic with log collection
    ./maintenance.sh cleanup                  # Clean up old files
    ./maintenance.sh debug-enable             # Enable debug mode
    ./maintenance.sh troubleshoot-vpn         # VPN troubleshooting

HEALTH CHECKS:
    ✓ Podman Compose availability
    ✓ Environment file configuration
    ✓ Services status and health
    ✓ VPN connectivity and IP verification
    ✓ Port forwarding functionality
    ✓ qBittorrent accessibility
    ✓ Inter-service connectivity

LOG LOCATIONS:
    System info:        ${LOG_DIR}/system-info.log
    Container stats:    ${LOG_DIR}/container-stats.log
    Network info:       ${LOG_DIR}/network-info.log
    Service logs:       ${LOG_DIR}/[service]-logs.log
    Troubleshooting:    ${LOG_DIR}/[issue]-troubleshooting.log

For more help, see README.md troubleshooting section.
EOF
}

# =============================================================================
#                                MAIN SCRIPT LOGIC
# =============================================================================

main() {
    # Create debug log file
    echo "$(date '+%Y-%m-%d %H:%M:%S') - Maintenance script started" > "$DEBUG_LOG_FILE"
    
    case "${1:-help}" in
        "health")
            run_health_check
            ;;
        "logs")
            show_logs "${2:-all}" "${3:-50}"
            ;;
        "diagnostic")
            run_full_diagnostic
            ;;
        "cleanup")
            run_cleanup
            ;;
        "debug-enable")
            enable_debug_mode
            ;;
        "debug-disable")
            disable_debug_mode
            ;;
        "troubleshoot-vpn")
            troubleshoot_vpn_issues
            ;;
        "troubleshoot-pf")
            troubleshoot_port_forwarding
            ;;
        "troubleshoot-dl")
            troubleshoot_download_issues
            ;;
        "help"|"-h"|"--help")
            show_help
            ;;
        *)
            log_error "Unknown command: $1"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

# Execute main function with all arguments
main "$@"