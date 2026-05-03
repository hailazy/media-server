#!/usr/bin/env bash
# scripts/update.sh — pull latest images for all sections, optionally recycle running ones.
#
# Usage: ./scripts/update.sh
#
# Pulls latest images for media, forge, sillytavern, dashboard. If sections are
# currently running, prompts whether to recycle them (down + up) to apply the
# new images. Pull is per-image atomic and resumable; safe to interrupt.
#
# Pairs with the tray indicator: right-click → Update Services.

set -uo pipefail   # no -e: pull failures should be reported per-section, not abort the loop

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

# shellcheck source=_lib.sh
source "$SCRIPT_DIR/_lib.sh"

SECTIONS=(media forge sillytavern dashboard)

# Maps section → primary container name (mirrors tray.py state-detection logic)
section_container() {
    case "$1" in
        media)        echo "jellyfin" ;;
        forge)        echo "home-forge" ;;
        sillytavern)  echo "home-sillytavern" ;;
        dashboard)    echo "home-dashboard" ;;
    esac
}

is_running() {
    local container
    container=$(section_container "$1")
    [[ -n "$container" ]] || return 1
    podman ps --filter "name=$container" --format '{{.Names}}' | grep -qx "$container"
}

main() {
    check_podman_setup
    check_podman_compose

    log_info "Pulling latest images for all sections..."

    local pull_failed=0
    for s in "${SECTIONS[@]}"; do
        local compose_file="$ROOT_DIR/$s/compose.yml"
        local env_file="$ROOT_DIR/$s/.env"

        if [[ ! -f "$compose_file" ]]; then
            log_warning "$s: no compose.yml — section not bootstrapped, skipping"
            continue
        fi

        # .env is optional: forge/sillytavern run on compose defaults, only media + dashboard need vars.
        local env_arg=()
        [[ -f "$env_file" ]] && env_arg=(--env-file "$env_file")

        echo
        log_info "── $s ──"
        if $COMPOSE_CMD "${env_arg[@]}" -f "$compose_file" pull; then
            log_success "$s pulled"
        else
            log_warning "$s pull failed (continuing)"
            pull_failed=$((pull_failed + 1))
        fi
    done

    echo
    if (( pull_failed > 0 )); then
        log_warning "$pull_failed section(s) had pull failures — review log above"
    else
        log_success "All sections pulled"
    fi

    local running=()
    for s in "${SECTIONS[@]}"; do
        is_running "$s" && running+=("$s")
    done

    if (( ${#running[@]} == 0 )); then
        echo
        log_info "No sections running — new images apply next time you start each section."
    else
        echo
        log_info "Running sections (need recycle to apply new images): ${running[*]}"
        local ans
        read -rp "Recycle these now? [y/N] " ans
        case "${ans,,}" in
            y|yes)
                echo
                for s in "${running[@]}"; do
                    "$SCRIPT_DIR/down.sh" "$s" || log_warning "$s down failed"
                done
                echo
                for s in "${running[@]}"; do
                    "$SCRIPT_DIR/up.sh" "$s" || log_warning "$s up failed"
                done
                echo
                log_success "Recycle complete"
                ;;
            *)
                log_info "Skipped recycle. Run './scripts/down.sh all && ./scripts/up.sh all' later to apply."
                ;;
        esac
    fi

    echo
    read -rp "Press Enter to close..." _
}

main "$@"
