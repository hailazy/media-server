#!/bin/bash
# Home Server unified logs viewer
# Usage: ./scripts/logs.sh {media|forge|sillytavern|dashboard|ebooks} [-f] [-n N] [services...]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

# shellcheck source=_lib.sh
source "${SCRIPT_DIR}/_lib.sh"

usage() {
    cat <<EOF
Usage: $0 {media|forge|sillytavern|dashboard|ebooks} [OPTIONS] [SERVICES...]

Options:
  -f, --follow         Follow log output
  -n, --tail N         Lines from end (default 100, 'all' for everything)
  -t, --timestamps     Show timestamps
  --since TIME         Logs since timestamp (1h, 30m, 2026-04-01)
  --status             Show ps + exit
EOF
}

SECTION="${1:-}"
if [[ -z "$SECTION" || "$SECTION" =~ ^(-h|--help)$ ]]; then
    usage
    exit 0
fi
shift

case "$SECTION" in
    media|forge|sillytavern|dashboard|ebooks) ;;
    *) log_error "Unknown section: $SECTION"; usage; exit 1 ;;
esac

COMPOSE_FILE="${ROOT_DIR}/${SECTION}/compose.yml"
[[ ! -f "$COMPOSE_FILE" ]] && { log_error "No compose at $COMPOSE_FILE"; exit 1; }

check_podman_compose

FOLLOW=""
TAIL_LINES=""
TIMESTAMPS=""
SINCE=""
SERVICES=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -f|--follow) FOLLOW="--follow"; shift ;;
        -n|--tail)
            if [[ "$2" == "all" || "$2" =~ ^[0-9]+$ ]]; then
                TAIL_LINES="--tail $2"; shift 2
            else
                TAIL_LINES="--tail 100"; shift
            fi
            ;;
        -t|--timestamps) TIMESTAMPS="--timestamps"; shift ;;
        --since)
            [[ -z "$2" ]] && { log_error "--since requires value"; exit 1; }
            SINCE="--since $2"; shift 2
            ;;
        --status)
            $COMPOSE_CMD -f "$COMPOSE_FILE" ps
            exit 0
            ;;
        -*)
            log_error "Unknown option: $1"; exit 1 ;;
        *)
            SERVICES="$SERVICES $1"; shift ;;
    esac
done

[[ -z "$TAIL_LINES" && -z "$FOLLOW" ]] && TAIL_LINES="--tail 100"

trap 'log_info "Stopped."; exit 0' SIGINT SIGTERM

$COMPOSE_CMD -f "$COMPOSE_FILE" logs $FOLLOW $TAIL_LINES $TIMESTAMPS $SINCE $SERVICES
