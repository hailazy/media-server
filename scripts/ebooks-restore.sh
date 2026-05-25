#!/bin/bash
# Restore CWA config from a tar.gz backup.
# Replaces ebooks/data/config/ with the snapshot's contents.
# Leaves ebooks/data/ingest/ untouched (transient).
# Usage: ./scripts/ebooks-restore.sh <backup-file>

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOME_SERVER_DIR="$(dirname "$SCRIPT_DIR")"
EBOOKS_DIR="${HOME_SERVER_DIR}/ebooks"

BACKUP="${1:-}"
if [[ -z "$BACKUP" || ! -f "$BACKUP" ]]; then
    echo "Usage: $0 <backup.tar.gz>"
    [[ -d "${EBOOKS_DIR}/backups" ]] && {
        echo ""
        echo "Available backups:"
        ls -lh "${EBOOKS_DIR}/backups/"*.tar.gz 2>/dev/null | awk '{print "  " $NF " (" $5 ")"}'
    }
    exit 1
fi

# Stop ebooks before restoring
echo "[INFO] Stopping ebooks..."
(cd "$HOME_SERVER_DIR" && ./scripts/down.sh ebooks >/dev/null 2>&1)

# Wipe current config (preserve ingest/)
echo "[INFO] Wiping current data/config/..."
podman unshare rm -rf "${EBOOKS_DIR}/data/config"

# Extract backup (contains "data/config" relative to EBOOKS_DIR)
echo "[INFO] Extracting $BACKUP..."
podman unshare tar -xzf "$BACKUP" -C "$EBOOKS_DIR"

# Restart
echo "[INFO] Starting ebooks..."
(cd "$HOME_SERVER_DIR" && ./scripts/up.sh ebooks >/dev/null 2>&1)

echo "[OK] Restored. Login at http://localhost:8083 with credentials from when backup was taken."
