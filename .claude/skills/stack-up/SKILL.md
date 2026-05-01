---
name: stack-up
description: "Start a home-server section (media|forge|sillytavern|dashboard|all)"
disable-model-invocation: false
argument-hint: "<section> [extra args]"
allowed-tools: Bash
---

Start a home-server section with pre-flight checks.

`$ARGUMENTS` first token is the section: `media`, `forge`, `sillytavern`, `dashboard`, or `all`. Remaining tokens forward to podman-compose.

1. **Pre-flight checks** (report issues before starting):
   - `which podman` and `which podman-compose`
   - Compose file exists: `<section>/compose.yml`
   - Env file exists: `<section>/.env` (check existence only — NEVER read contents)
   - For media/forge: NVIDIA GPU `ls /dev/nvidia*`
   - Report any issues and ask to confirm before proceeding

2. **Start the section:**
   ```
   ./scripts/up.sh $ARGUMENTS
   ```

3. **Post-start health** (wait ~15s):
   ```
   podman-compose -f <section>/compose.yml ps
   ```
   Verify all containers show "Up" / "running".

4. **Report** with service URLs (relevant to section):
   - media: Prowlarr 9696, Sonarr 8989, Radarr 7878, Bazarr 6767, qBittorrent 8080, Jellyfin 8096, FlareSolverr 8191
   - forge: WebUI/API http://localhost:7860
   - sillytavern: http://localhost:8000 (default)
   - dashboard: Homarr port (TBD when bootstrapped)
