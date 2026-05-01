#!/bin/bash
# Home Server unified shutdown script
# Usage: ./scripts/down.sh {media|forge|sillytavern|dashboard|all} [extra args]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

# shellcheck source=_lib.sh
source "${SCRIPT_DIR}/_lib.sh"

usage() {
    cat <<EOF
Usage: $0 {media|forge|sillytavern|dashboard|all} [extra args]

Common extra args:
  --volumes, -v          Remove named volumes
  --rmi {all|local}      Remove images
  --timeout, -t SECONDS  Container stop timeout
EOF
}

SECTION="${1:-}"
if [[ -z "$SECTION" || "$SECTION" =~ ^(-h|--help)$ ]]; then
    usage
    exit 0
fi
shift

stop_section() {
    local section="$1"; shift
    local compose_file="${ROOT_DIR}/${section}/compose.yml"

    [[ ! -f "$compose_file" ]] && return 0

    log_info "← Stopping section: $section"
    if $COMPOSE_CMD -f "$compose_file" down "$@"; then
        log_success "Section ${section} stopped"
    else
        log_error "Section ${section} stop failed"
    fi
}

main() {
    check_podman_compose

    case "$SECTION" in
        media|forge|sillytavern|dashboard)
            stop_section "$SECTION" "$@"
            ;;
        all)
            # Reverse of up order
            local order=(dashboard sillytavern media forge)
            for s in "${order[@]}"; do
                stop_section "$s" "$@"
            done
            ;;
        *)
            log_error "Unknown section: $SECTION"
            usage
            exit 1
            ;;
    esac
}

main "$@"
