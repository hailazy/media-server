#!/bin/bash
# Install systemd user timer for Calibre Library cloud backup (one-way local → OneDrive).
# Idempotent: safe to re-run. Used by:
#   - Manual setup on new machine
#   - workstation-setup recover.sh phase 6 (post-hook)
#
# Steps:
#   1. Ensure rclone installed + onedrive-dev: remote configured
#   2. Write ~/.config/systemd/user/calibre-sync.{service,timer}
#   3. Enable + start timer (daily 22:30)
#
# Cloud destination: onedrive-dev:Calibre Library/ (Dev account root)
# Local source: /home/haint/Data/Calibre Library/
# Sync direction: one-way (local → cloud). CWA is single writer.

set -e

LIBRARY_PATH="${CALIBRE_LIBRARY_PATH:-/home/haint/Data/Calibre Library}"
CLOUD_REMOTE="onedrive-dev:Calibre Library/"

SYSTEMD_USER_DIR="${HOME}/.config/systemd/user"
SERVICE_FILE="${SYSTEMD_USER_DIR}/calibre-sync.service"
TIMER_FILE="${SYSTEMD_USER_DIR}/calibre-sync.timer"

log() { echo -e "\033[0;34m[calibre-sync-setup]\033[0m $*"; }
ok()  { echo -e "\033[0;32m[calibre-sync-setup]\033[0m $*"; }
err() { echo -e "\033[0;31m[calibre-sync-setup]\033[0m $*" >&2; }

# 1. Dependencies
if ! command -v rclone >/dev/null 2>&1; then
    err "rclone not installed. Install: sudo dnf install -y rclone"
    exit 1
fi

if ! rclone listremotes | grep -qx "onedrive-dev:"; then
    err "rclone remote 'onedrive-dev:' not configured."
    err "Set up via workstation-setup recovery flow or 'rclone config'."
    exit 1
fi

if [[ ! -d "$LIBRARY_PATH" ]]; then
    log "Calibre Library not present at: $LIBRARY_PATH"
    log "Timer will still install — first sync will fail until library exists."
    log "Restore from cloud: rclone copy \"$CLOUD_REMOTE\" \"$LIBRARY_PATH\""
fi

# 2. Write systemd unit files
mkdir -p "$SYSTEMD_USER_DIR"

cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Sync local Calibre Library to OneDrive cloud (one-way backup)
Documentation=https://github.com/haingt-dev/home-server
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/bin/rclone sync "$LIBRARY_PATH/" "$CLOUD_REMOTE" --transfers 4 --checkers 8 --fast-list --log-level INFO
TimeoutStartSec=3600
Nice=10
IOSchedulingClass=idle
EOF
ok "Wrote $SERVICE_FILE"

cat > "$TIMER_FILE" <<EOF
[Unit]
Description=Daily Calibre Library backup sync (22:30)
Documentation=https://github.com/haingt-dev/home-server

[Timer]
OnCalendar=*-*-* 22:30:00
Persistent=true
RandomizedDelaySec=5min

[Install]
WantedBy=timers.target
EOF
ok "Wrote $TIMER_FILE"

# 3. Reload + enable + start
systemctl --user daemon-reload
systemctl --user enable --now calibre-sync.timer
ok "Timer enabled — daily 22:30 sync (±5min jitter)"

NEXT=$(systemctl --user list-timers calibre-sync.timer --no-pager | awk 'NR==2 {print $1, $2, $3}')
log "Next run: $NEXT"
log "Manual sync: systemctl --user start calibre-sync.service"
log "Logs:        journalctl --user -u calibre-sync.service -n 50"

ok "Done."
