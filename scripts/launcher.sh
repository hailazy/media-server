#!/bin/bash
# Launcher: ensure home-server core sections up, open Homarr in browser.
# Forge + SillyTavern + Dashboard auto-start. Media stack NOT auto-started (needs .env + AirVPN).

set -e

HOME_SERVER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DASHBOARD_URL="http://localhost:7575"
FORGE_URL="http://localhost:7860/sdapi/v1/sd-models"
ST_URL="http://localhost:8000"

is_up() { curl -sf "$1" >/dev/null 2>&1; }

start_section() {
    local section="$1"
    (cd "$HOME_SERVER_DIR" && ./scripts/up.sh "$section") >/dev/null 2>&1 || true
}

started_any=false

if ! is_up "$DASHBOARD_URL";    then start_section dashboard;   started_any=true; fi
if ! is_up "$FORGE_URL";        then start_section forge;       started_any=true; fi
if ! is_up "$ST_URL";           then start_section sillytavern; started_any=true; fi

if $started_any; then
    notify-send -a "Home Server" "Starting services..." \
        "Dashboard ready first; Forge cold-start ~3min on first run" 2>/dev/null || true
fi

# Wait up to 30s for dashboard (browser entry point) — Forge/ST keep booting in background
for _ in $(seq 1 30); do
    is_up "$DASHBOARD_URL" && break
    sleep 1
done

xdg-open "$DASHBOARD_URL" >/dev/null 2>&1 &
