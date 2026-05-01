---
name: stack-health
description: "Full diagnostics on home-server stack (media + forge + sillytavern + dashboard)"
disable-model-invocation: false
argument-hint: "[gpu|vpn|services|<section>]"
allowed-tools: Bash
---

Run full diagnostics on the home-server stack.

If `$ARGUMENTS` provided (e.g., `gpu`, `vpn`, `services`, or a section name like `forge`), run only that check.

1. **System:** `podman --version`, `podman-compose --version`, rootless mode check

2. **NVIDIA GPU:**
   - `ls -la /dev/nvidia*`
   - `nvidia-smi --query-gpu=name,driver_version,memory.total,memory.used,temperature.gpu --format=csv,noheader`
   - CDI config: `ls ~/.config/containers/cdi/nvidia.yaml`

3. **Containers per section:**
   ```
   for s in media forge sillytavern dashboard; do
     [ -f "$s/compose.yml" ] && podman-compose -f "$s/compose.yml" ps
   done
   ```
   For each: name, status, uptime, ports, health check result.

4. **Volumes:** `podman volume ls` — report sizes

5. **VPN:** If gluetun running (media section): `podman exec gluetun wget -qO- ifconfig.me`

6. **VRAM budget:** `nvidia-smi --query-gpu=memory.used,memory.free --format=csv,noheader` — flag if free < 4GB while Forge expected to run

7. **Disk space:** `df -h /home` — flag if < 10% free

8. **Quick-debug:** If `media/maintenance/quick-debug.sh` exists, run `./media/maintenance/quick-debug.sh all`

9. **Summary dashboard:**
   | Section | Service | Status | Health | Uptime | Port |
   Show warnings prominently.
