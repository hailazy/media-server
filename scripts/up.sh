#!/bin/bash
# Home Server unified startup script
# Usage: ./scripts/up.sh {media|forge|sillytavern|dashboard|all} [extra args]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

# shellcheck source=_lib.sh
source "${SCRIPT_DIR}/_lib.sh"

usage() {
    cat <<EOF
Usage: $0 {media|forge|sillytavern|dashboard|all} [extra args]

Sections:
  media         Jellyfin + arr stack + qBittorrent + Gluetun VPN
  forge         Stable Diffusion WebUI Forge (image generation)
  sillytavern   SillyTavern chat UI
  dashboard     Homarr dashboard
  all           Start all bootstrapped sections

Examples:
  $0 media              # start media stack
  $0 forge              # start forge only
  $0 all                # start everything available
  $0 media --build      # rebuild images first
EOF
}

SECTION="${1:-}"
if [[ -z "$SECTION" || "$SECTION" =~ ^(-h|--help)$ ]]; then
    usage
    exit 0
fi
shift

start_section() {
    local section="$1"; shift
    local compose_file="${ROOT_DIR}/${section}/compose.yml"
    local env_file="${ROOT_DIR}/${section}/.env"

    if [[ ! -f "$compose_file" ]]; then
        log_warning "No compose.yml at ${section}/ — section not bootstrapped, skipping"
        return 0
    fi

    log_info "→ Starting section: $section"

    # GPU pre-flight for GPU-using sections
    if [[ "$section" =~ ^(media|forge)$ ]]; then
        check_nvidia_gpu_availability 60
        check_nvidia_cdi_configuration
    fi

    # Shared network needed for forge/sillytavern/dashboard
    if [[ "$section" =~ ^(forge|sillytavern|dashboard)$ ]]; then
        ensure_home_network
    fi

    # VRAM guard hook (Worker B Phase 2 implements vram-guard.sh)
    if [[ -x "${SCRIPT_DIR}/vram-guard.sh" ]]; then
        if ! "${SCRIPT_DIR}/vram-guard.sh" check "$section"; then
            log_error "VRAM guard rejected start of section: $section"
            return 1
        fi
    fi

    local env_arg=""
    [[ -f "$env_file" ]] && env_arg="--env-file ${env_file}"

    log_info "Executing: $COMPOSE_CMD ${env_arg} -f ${compose_file} up -d $*"
    if $COMPOSE_CMD $env_arg -f "$compose_file" up -d "$@"; then
        log_success "Section ${section} started"
    else
        log_error "Section ${section} failed to start"
        return 1
    fi
}

main() {
    check_podman_setup
    check_podman_compose

    case "$SECTION" in
        media|forge|sillytavern|dashboard)
            check_section_env "$SECTION"
            start_section "$SECTION" "$@"
            ;;
        all)
            # Order: forge first (warm GPU), media (heavy), then ST + dashboard
            local order=(forge media sillytavern dashboard)
            local failed=0
            for s in "${order[@]}"; do
                start_section "$s" "$@" || failed=$((failed + 1))
            done
            if (( failed == 0 )); then
                log_success "All sections started"
            else
                log_warning "$failed section(s) failed or skipped"
            fi
            ;;
        *)
            log_error "Unknown section: $SECTION"
            usage
            exit 1
            ;;
    esac
}

main "$@"
