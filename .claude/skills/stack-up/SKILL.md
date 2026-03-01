---
name: stack-up
description: Start the Podman media stack with pre-flight checks and health verification
disable-model-invocation: true
argument-hint: "[service name or flags]"
---

Start the Podman media stack with pre-flight checks.

1. **Pre-flight checks** (report issues before starting):
   - `which podman` and `which podman-compose`
   - Compose file exists: `core/podman-compose.yml`
   - Env file exists: `core/.env` (check existence only — NEVER read contents, it has secrets)
   - NVIDIA GPU: `ls /dev/nvidia*`
   - Report any issues and ask to confirm before proceeding

2. **Start the stack:**
   ```
   ./scripts/podman-up.sh $ARGUMENTS
   ```

3. **Post-start health** (wait ~15s for containers to init):
   ```
   podman-compose -f core/podman-compose.yml ps
   ```
   Verify all containers show "Up" / "running".

4. **Report** with service URLs:
   - Prowlarr: http://localhost:9696
   - Sonarr: http://localhost:8989
   - Radarr: http://localhost:7878
   - Bazarr: http://localhost:6767
   - qBittorrent: http://localhost:8080
   - Jellyfin: http://localhost:8096
   - FlareSolverr: http://localhost:8191
