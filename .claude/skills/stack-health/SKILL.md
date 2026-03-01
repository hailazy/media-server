---
name: stack-health
description: Run full diagnostics on the Podman media stack (GPU, services, volumes, network)
disable-model-invocation: true
argument-hint: "[gpu|vpn|services]"
---

Run full diagnostics on the Podman media stack.

If `$ARGUMENTS` provided (e.g., `gpu`, `vpn`, `services`), run only that check.

1. **System:** `podman --version`, `podman-compose --version`, rootless mode check

2. **NVIDIA GPU:**
   - `ls -la /dev/nvidia*`
   - `nvidia-smi --query-gpu=name,driver_version,memory.total,memory.used,temperature.gpu --format=csv,noheader`
   - CDI config: `ls ~/.config/containers/cdi/nvidia.yaml`

3. **Containers:**
   ```
   podman-compose -f core/podman-compose.yml ps
   ```
   For each: name, status, uptime, ports, health check result.

4. **Volumes:** `podman volume ls` — report sizes

5. **VPN:** If gluetun running: `podman exec gluetun wget -qO- ifconfig.me`

6. **Disk space:** `df -h /home` — flag if < 10% free

7. **Quick-debug:** If `maintenance/quick-debug.sh` exists, run `./maintenance/quick-debug.sh all`

8. **Summary dashboard:**
   | Service | Status | Health | Uptime | Port |
   Show warnings prominently.
