#!/bin/bash
# Dump CWA config (app.db, users, settings, SMTP, OPDS state) to a tar.gz snapshot.
# Skips data/ingest/ — that folder is transient (CWA deletes processed files).
# Usage: ./scripts/ebooks-backup.sh [output-name]
# Default output: ebooks/backups/ebooks-YYYY-MM-DD-HHMM.tar.gz

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOME_SERVER_DIR="$(dirname "$SCRIPT_DIR")"
EBOOKS_DIR="${HOME_SERVER_DIR}/ebooks"
BACKUP_DIR="${EBOOKS_DIR}/backups"

if [[ ! -d "${EBOOKS_DIR}/data/config" ]]; then
    echo "[ERROR] No CWA config found at ${EBOOKS_DIR}/data/config"
    echo "Run ./scripts/up.sh ebooks first so CWA initializes app.db."
    exit 1
fi

mkdir -p "$BACKUP_DIR"
NAME="${1:-ebooks-$(date +%Y-%m-%d-%H%M)}"
OUTPUT="${BACKUP_DIR}/${NAME}.tar.gz"

# Stop container briefly for consistent snapshot (SQLite WAL safety)
WAS_RUNNING=false
if podman ps --filter name=home-ebooks --format "{{.Names}}" | grep -q .; then
    WAS_RUNNING=true
    echo "[INFO] Stopping ebooks for consistent snapshot..."
    (cd "$HOME_SERVER_DIR" && ./scripts/down.sh ebooks >/dev/null 2>&1)
fi

# podman unshare for consistency with dashboard-backup pattern
# (PUID=0 means files are haint-owned, but unshare is harmless and future-proof).
podman unshare tar -czf "$OUTPUT" -C "$EBOOKS_DIR" data/config
# 0:0 inside unshare namespace maps to host UID 1000:1001 (haint). Using
# "$(id -u):$(id -g)" here would chown to subuid because the substitution
# happens pre-unshare but chown runs post-unshare with shifted IDs.
podman unshare chown 0:0 "$OUTPUT"

if $WAS_RUNNING; then
    echo "[INFO] Restarting ebooks..."
    (cd "$HOME_SERVER_DIR" && ./scripts/up.sh ebooks >/dev/null 2>&1)
fi

SIZE=$(du -h "$OUTPUT" | cut -f1)
echo "[OK] Backup saved: $OUTPUT ($SIZE)"
echo "Restore: ./scripts/ebooks-restore.sh $OUTPUT"
