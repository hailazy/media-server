#!/bin/bash
# Restore Homarr config from a tar.gz backup.
# Usage: ./scripts/dashboard-restore.sh <backup-file>

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOME_SERVER_DIR="$(dirname "$SCRIPT_DIR")"
DASHBOARD_DIR="${HOME_SERVER_DIR}/dashboard"

BACKUP="${1:-}"
if [[ -z "$BACKUP" || ! -f "$BACKUP" ]]; then
    echo "Usage: $0 <backup.tar.gz>"
    [[ -d "${DASHBOARD_DIR}/backups" ]] && {
        echo ""
        echo "Available backups:"
        ls -lh "${DASHBOARD_DIR}/backups/"*.tar.gz 2>/dev/null | awk '{print "  " $NF " (" $5 ")"}'
    }
    exit 1
fi

# Stop dashboard before restoring
echo "[INFO] Stopping dashboard..."
(cd "$HOME_SERVER_DIR" && ./scripts/down.sh dashboard >/dev/null 2>&1)

# Wipe current data
echo "[INFO] Wiping current data dir..."
podman unshare rm -rf "${DASHBOARD_DIR}/data"

# Extract backup
echo "[INFO] Extracting $BACKUP..."
podman unshare tar -xzf "$BACKUP" -C "$DASHBOARD_DIR"

# Restart
echo "[INFO] Starting dashboard..."
(cd "$HOME_SERVER_DIR" && ./scripts/up.sh dashboard >/dev/null 2>&1)

echo "[OK] Restored. Login at http://localhost:7575 with credentials from when backup was taken."
