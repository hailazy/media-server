#!/bin/bash
# Podman Media Stack Logs Script
# ===============================
# View logs for media stack services using Podman with various options.

set -e  # Exit on any error

# Configuration
COMPOSE_FILE="core/podman-compose.yml"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
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

# Show available services
show_services() {
    log_info "Available services:"
    echo -e "  ${CYAN}pia-wggen${NC}    - PIA WireGuard configuration generator"
    echo -e "  ${CYAN}flaresolverr${NC} - CloudFlare challenge solver"
    echo -e "  ${CYAN}prowlarr${NC}     - Indexer management"
    echo -e "  ${CYAN}sonarr${NC}       - TV series management"
    echo -e "  ${CYAN}radarr${NC}       - Movie management"
    echo -e "  ${CYAN}bazarr${NC}       - Subtitle management"
    echo -e "  ${CYAN}gluetun${NC}      - VPN container"
    echo -e "  ${CYAN}pia-pf${NC}       - PIA port forwarding"
    echo -e "  ${CYAN}qbittorrent${NC}  - Torrent client"
    echo -e "  ${CYAN}jellyfin${NC}     - Media server"
}

# Show service status
show_status() {
    log_info "Current service status:"
    $COMPOSE_CMD -f $COMPOSE_FILE ps 2>/dev/null || log_warning "No services found"
}

# Main execution
main() {
    # Pre-flight checks
    check_podman_compose
    
    # Check if compose file exists
    if [[ ! -f "$COMPOSE_FILE" ]]; then
        log_error "Compose file $COMPOSE_FILE not found!"
        exit 1
    fi
    
    # Parse command line arguments
    SERVICES=""
    FOLLOW=""
    TAIL_LINES=""
    TIMESTAMPS=""
    SINCE=""
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --follow|-f)
                FOLLOW="--follow"
                shift
                ;;
            --tail|-n)
                if [[ -n "$2" && "$2" =~ ^[0-9]+$ ]]; then
                    TAIL_LINES="--tail $2"
                    shift 2
                elif [[ "$2" == "all" ]]; then
                    TAIL_LINES="--tail all"
                    shift 2
                else
                    TAIL_LINES="--tail 100"
                    shift
                fi
                ;;
            --timestamps|-t)
                TIMESTAMPS="--timestamps"
                shift
                ;;
            --since)
                if [[ -n "$2" ]]; then
                    SINCE="--since $2"
                    shift 2
                else
                    log_error "--since requires a value (e.g., '1h', '30m', '2024-01-01')"
                    exit 1
                fi
                ;;
            --status)
                show_status
                exit 0
                ;;
            --services)
                show_services
                exit 0
                ;;
            --help|-h)
                echo "Usage: $0 [OPTIONS] [SERVICES...]"
                echo ""
                echo "Options:"
                echo "  --follow, -f         Follow log output (live streaming)"
                echo "  --tail, -n NUMBER    Number of lines to show from end (default: 100)"
                echo "                       Use 'all' to show all lines"
                echo "  --timestamps, -t     Show timestamps"
                echo "  --since TIME         Show logs since timestamp (e.g., '1h', '30m', '2024-01-01')"
                echo "  --status             Show service status and exit"
                echo "  --services           List available services and exit"
                echo "  --help, -h           Show this help message"
                echo ""
                echo "Services:"
                echo "  If no services specified, logs for all services will be shown"
                echo ""
                show_services
                echo ""
                echo "Examples:"
                echo "  $0                           # Show recent logs for all services"
                echo "  $0 -f gluetun pia-pf        # Follow logs for VPN services"
                echo "  $0 --tail 50 jellyfin       # Show last 50 lines for Jellyfin"
                echo "  $0 -t --since 1h            # Show logs with timestamps from last hour"
                echo "  $0 --follow --tail all      # Follow all logs from beginning"
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
    
    # Set default tail if not specified
    if [[ -z "$TAIL_LINES" && -z "$FOLLOW" ]]; then
        TAIL_LINES="--tail 100"
    fi
    
    # Build the command
    CMD="$COMPOSE_CMD -f $COMPOSE_FILE logs $FOLLOW $TAIL_LINES $TIMESTAMPS $SINCE $SERVICES"
    
    # Show what we're doing
    if [[ -n "$SERVICES" ]]; then
        log_info "Viewing logs for services:$SERVICES"
    else
        log_info "Viewing logs for all services"
    fi
    
    if [[ -n "$FOLLOW" ]]; then
        log_info "Following logs (press Ctrl+C to stop)"
    fi
    
    echo ""
    
    # Execute the command
    if ! $CMD; then
        log_error "Failed to retrieve logs!"
        echo ""
        log_info "Troubleshooting tips:"
        echo "  - Check if services are running: $0 --status"
        echo "  - View available services: $0 --services"
        echo "  - Start services: ./start.sh"
        exit 1
    fi
}

# Handle Ctrl+C gracefully when following logs
trap 'log_info "Log following stopped."; exit 0' SIGINT SIGTERM

# Run main function
main "$@"