#!/bin/bash
# Dump Homarr config (SQLite + Redis state) to a tar.gz snapshot.
# Usage: ./scripts/dashboard-backup.sh [output-name]
# Default output: dashboard/backups/dashboard-YYYY-MM-DD-HHMM.tar.gz

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOME_SERVER_DIR="$(dirname "$SCRIPT_DIR")"
DASHBOARD_DIR="${HOME_SERVER_DIR}/dashboard"
BACKUP_DIR="${DASHBOARD_DIR}/backups"

if [[ ! -d "${DASHBOARD_DIR}/data/db" ]]; then
    echo "[ERROR] No dashboard data found at ${DASHBOARD_DIR}/data/db"
    echo "Container may be using legacy named volume — run dashboard once with current compose first."
    exit 1
fi

mkdir -p "$BACKUP_DIR"
NAME="${1:-dashboard-$(date +%Y-%m-%d-%H%M)}"
OUTPUT="${BACKUP_DIR}/${NAME}.tar.gz"

# Stop container briefly for consistent snapshot (SQLite WAL + Redis dump)
WAS_RUNNING=false
if podman ps --filter name=home-dashboard --format "{{.Names}}" | grep -q .; then
    WAS_RUNNING=true
    echo "[INFO] Stopping dashboard for consistent snapshot..."
    (cd "$HOME_SERVER_DIR" && ./scripts/down.sh dashboard >/dev/null 2>&1)
fi

# Use podman unshare since data dirs may have container-mapped UIDs
podman unshare tar -czf "$OUTPUT" -C "$DASHBOARD_DIR" data
podman unshare chown "$(id -u):$(id -g)" "$OUTPUT"

if $WAS_RUNNING; then
    echo "[INFO] Restarting dashboard..."
    (cd "$HOME_SERVER_DIR" && ./scripts/up.sh dashboard >/dev/null 2>&1)
fi

SIZE=$(du -h "$OUTPUT" | cut -f1)
echo "[OK] Backup saved: $OUTPUT ($SIZE)"
echo "Restore: ./scripts/dashboard-restore.sh $OUTPUT"
