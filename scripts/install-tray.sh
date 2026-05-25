#!/bin/bash
# Install KDE Plasma system tray indicator for home-server.
# Idempotent: safe to re-run. Used by:
#   - Manual setup on new machine
#   - workstation-setup recover.sh phase 6 (post-hook)
#
# Steps:
#   1. Ensure python3-pyqt6 installed (via dnf)
#   2. Write ~/.config/autostart/home-server-tray.desktop
#   3. Launch tray if not running (so user doesn't have to log out / in)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
TRAY_PY="${SCRIPT_DIR}/tray.py"

AUTOSTART_DIR="${HOME}/.config/autostart"
AUTOSTART_FILE="${AUTOSTART_DIR}/home-server-tray.desktop"

log() { echo -e "\033[0;34m[install-tray]\033[0m $*"; }
ok()  { echo -e "\033[0;32m[install-tray]\033[0m $*"; }
err() { echo -e "\033[0;31m[install-tray]\033[0m $*" >&2; }

[[ ! -f "$TRAY_PY" ]] && { err "tray.py not found at $TRAY_PY"; exit 1; }

# 1. Ensure PyQt6 available (Fedora/Nobara: python3-pyqt6)
if ! python3 -c 'import PyQt6.QtWidgets' 2>/dev/null; then
    log "PyQt6 missing — installing python3-pyqt6 via dnf"
    if ! sudo dnf install -y python3-pyqt6; then
        err "Failed to install python3-pyqt6"
        err "Run manually: sudo dnf install -y python3-pyqt6"
        exit 1
    fi
    ok "python3-pyqt6 installed"
else
    log "PyQt6 already installed"
fi

# 2. Write autostart desktop entry
mkdir -p "$AUTOSTART_DIR"
cat > "$AUTOSTART_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=Home Server Tray
Comment=System tray indicator for home-server services
Exec=/usr/bin/python3 ${TRAY_PY}
Icon=network-server
Terminal=false
X-GNOME-Autostart-enabled=true
X-KDE-autostart-after=panel
StartupNotify=false
EOF
ok "Wrote autostart entry: $AUTOSTART_FILE"

# 3. Launch now if not already running (avoid duplicate)
if pgrep -af "python3 .*${TRAY_PY}" >/dev/null 2>&1; then
    log "Tray already running"
else
    log "Launching tray now (background)"
    nohup /usr/bin/python3 "$TRAY_PY" >/tmp/home-server-tray.log 2>&1 &
    disown
    ok "Tray started — should appear in system tray within a few seconds"
fi

ok "Done. Tray will autostart on next login."
