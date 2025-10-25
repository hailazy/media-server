#!/bin/bash
# Systemd wrapper for Podman Media Stack
# Ensures proper environment for rootless podman

# Debug: Log environment details
echo "[WRAPPER] Starting wrapper script with user: $(whoami)" >&2
echo "[WRAPPER] PATH: $PATH" >&2
echo "[WRAPPER] XDG_RUNTIME_DIR: $XDG_RUNTIME_DIR" >&2

# Set essential environment variables for rootless podman
export XDG_RUNTIME_DIR="/run/user/$(id -u)"
export DBUS_SESSION_BUS_ADDRESS="unix:path=${XDG_RUNTIME_DIR}/bus"

# Ensure PATH includes podman binaries
export PATH="/usr/local/bin:/usr/bin:/bin"

echo "[WRAPPER] After setting env - PATH: $PATH" >&2
echo "[WRAPPER] XDG_RUNTIME_DIR: $XDG_RUNTIME_DIR" >&2

# Test if podman is accessible
if command -v podman >/dev/null 2>&1; then
    echo "[WRAPPER] podman found at: $(command -v podman)" >&2
else
    echo "[WRAPPER] ERROR: podman not found in PATH" >&2
fi

if command -v podman-compose >/dev/null 2>&1; then
    echo "[WRAPPER] podman-compose found at: $(command -v podman-compose)" >&2
else
    echo "[WRAPPER] ERROR: podman-compose not found in PATH" >&2
fi

# Set working directory to project root
cd /home/haint/media-stack

# Source environment file if it exists
if [[ -f .env ]]; then
    set -a
    source .env
    set +a
fi

# Execute the actual startup script
echo "[WRAPPER] Executing scripts/podman-up.sh" >&2
exec ./scripts/podman-up.sh "$@"