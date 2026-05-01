#!/bin/bash
# VRAM constraint guard — called by up.sh before starting a section.
#
# Calling convention: vram-guard.sh check <section>
#   exit 0 → allow start; non-zero → refuse.
#
# Rules (RTX 4070 Ti Super, 16 GB VRAM):
#   forge   ~12000 MB peak load
#     - HARD REFUSE if free <  2000 MB  (would push >15 GB used → OOM risk)
#     - SOFT  WARN  if free <  4000 MB  (would push >13 GB used)
#     - else allow
#   media   light (Jellyfin NVENC ~2 GB)
#     - HARD REFUSE if free <  1000 MB
#     - else allow
#   sillytavern, dashboard → non-GPU, exit 0 immediately
#
# Overrides: VRAM_GUARD_FORCE=1 env var, or --force flag → skip check.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_lib.sh
source "${SCRIPT_DIR}/_lib.sh"

usage() {
    echo "Usage: $0 check <section> [--force]"
    echo "  section: media | forge | sillytavern | dashboard"
}

CMD="${1:-}"
SECTION="${2:-}"
FORCE="${VRAM_GUARD_FORCE:-0}"

for arg in "$@"; do
    [[ "$arg" == "--force" ]] && FORCE=1
done

if [[ "$CMD" != "check" || -z "$SECTION" ]]; then
    usage
    exit 2
fi

if [[ "$FORCE" == "1" ]]; then
    log_warning "VRAM guard bypassed (force) for section: ${SECTION}"
    exit 0
fi

# Non-GPU sections: pass through
case "$SECTION" in
    sillytavern|dashboard)
        exit 0
        ;;
    media|forge)
        ;;
    *)
        log_warning "VRAM guard: unknown section '${SECTION}', allowing"
        exit 0
        ;;
esac

# Read VRAM (MB). nvidia-smi missing → warn-only, allow.
if ! command -v nvidia-smi >/dev/null 2>&1; then
    log_warning "nvidia-smi not found — skipping VRAM check"
    exit 0
fi

read -r used free < <(nvidia-smi --id=0 --query-gpu=memory.used,memory.free --format=csv,noheader,nounits | tr -d ',' | awk '{print $1, $2}')

if [[ -z "$free" ]]; then
    log_warning "Failed to read VRAM — allowing"
    exit 0
fi

log_info "VRAM (GPU 0): used=${used} MB, free=${free} MB"

case "$SECTION" in
    forge)
        if (( free < 2000 )); then
            log_error "VRAM HARD REFUSE for forge — free ${free} MB < 2000 MB threshold"
            log_error "Stop other GPU workloads or run with VRAM_GUARD_FORCE=1 to override"
            exit 1
        elif (( free < 4000 )); then
            log_warning "VRAM SOFT WARN for forge — free ${free} MB < 4000 MB; starting anyway"
            exit 0
        else
            log_success "VRAM ok for forge (free ${free} MB)"
            exit 0
        fi
        ;;
    media)
        if (( free < 1000 )); then
            log_error "VRAM HARD REFUSE for media — free ${free} MB < 1000 MB; Jellyfin NVENC would OOM"
            exit 1
        else
            log_success "VRAM ok for media (free ${free} MB)"
            exit 0
        fi
        ;;
esac
