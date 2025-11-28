# Documentation Index (Start Here)

Purpose
- Provide a clear, prioritized reading order and role-based navigation so you always know what to read first and what is optional.

Priority reading order
1) Essential Quick Reference
   - Read: [docs/QUICK-REF.md](docs/QUICK-REF.md:1)
   - Why: Fastest path to core commands, health checks, and verification
   - When: First run and daily operations

2) Overview and Setup
   - Read: [docs/README.md](docs/README.md:1)
   - Why: Full system overview, structure, installation, configuration
   - When: Initial setup or onboarding

3) Podman Guide (details and trade-offs)
   - Read: [docs/PODMAN.md](docs/PODMAN.md:1)
   - Why: Rootless vs rootful, SELinux, GPU, systemd integration
   - When: After first run or when you need deeper platform details

4) GPU Boot Reliability (only if you use NVIDIA GPU)
   - Read: [docs/GPU-TIMING-FIX.md](docs/GPU-TIMING-FIX.md:1)
   - Why: Fixes rare boot-time race causing Jellyfin GPU to miss on first attempt
   - When: If you have NVIDIA and want first-try reliability on boot

5) qBittorrent Performance Tuning (optional)
   - Read: [docs/QBITTORRENT-PERFORMANCE-OPTIMIZATION.md](docs/QBITTORRENT-PERFORMANCE-OPTIMIZATION.md:1)
   - Why: Maximize throughput and stability for large libraries
   - When: After baseline is stable and you want more performance

6) Jellyfin Performance Tuning (optional)
   - Read: [docs/JELLYFIN-PERFORMANCE-OPTIMIZATION.md](docs/JELLYFIN-PERFORMANCE-OPTIMIZATION.md:1)
   - Why: Improve transcoding capacity and reduce latency
   - When: When you need more concurrent streams or snappier UI

7) Boot Startup Case Study (optional)
   - Read: [docs/BOOT-STARTUP-INVESTIGATION.md](docs/BOOT-STARTUP-INVESTIGATION.md:1)
   - Why: Real-world investigation and resolution steps for startup concerns
   - When: Only for historical context or similar symptoms

8) AirVPN Validation Checklist (optional)
   - Read: [docs/AIRVPN-VALIDATION-CHECKLIST.md](docs/AIRVPN-VALIDATION-CHECKLIST.md:1)
   - Why: Deep validation and configuration verification
   - When: When verifying VPN configuration end-to-end

Role-based quick paths
- New install (10–15 minutes)
  1. Copy envs: [core/.env.example](core/.env.example:1) → core/.env
  2. Start: [scripts/podman-up.sh](scripts/podman-up.sh:1)
  3. Health: [maintenance/maintenance.sh](maintenance/maintenance.sh:1) health
  4. Verify VPN: podman-compose -f [core/podman-compose.yml](core/podman-compose.yml:1) exec gluetun wget -qO- https://ipinfo.io
  5. Reference: [docs/QUICK-REF.md](docs/QUICK-REF.md:1)

- Daily operations (2 minutes)
  - Health: [maintenance/maintenance.sh](maintenance/maintenance.sh:1) health
  - Logs: [scripts/podman-logs.sh](scripts/podman-logs.sh:1)
  - VPN check: podman-compose -f [core/podman-compose.yml](core/podman-compose.yml:1) exec gluetun wget -qO- https://ipinfo.io

- Troubleshooting (triage first)
  1. Quick triage: [maintenance/quick-debug.sh](maintenance/quick-debug.sh:1)
  2. Service logs: [scripts/podman-logs.sh](scripts/podman-logs.sh:1)
  3. Targeted checks: [docs/QUICK-REF.md](docs/QUICK-REF.md:1) Troubleshooting section
  4. GPU boot behavior (if NVIDIA): [docs/GPU-TIMING-FIX.md](docs/GPU-TIMING-FIX.md:1)

- Advanced tuning (optional)
  - qBittorrent: [docs/QBITTORRENT-PERFORMANCE-OPTIMIZATION.md](docs/QBITTORRENT-PERFORMANCE-OPTIMIZATION.md:1)
  - Jellyfin: [docs/JELLYFIN-PERFORMANCE-OPTIMIZATION.md](docs/JELLYFIN-PERFORMANCE-OPTIMIZATION.md:1)
  - Podman trade-offs, SELinux, systemd: [docs/PODMAN.md](docs/PODMAN.md:1)

Minimal command cheat sheet
- Start: [scripts/podman-up.sh](scripts/podman-up.sh:1)
- Stop: [scripts/podman-down.sh](scripts/podman-down.sh:1)
- Logs: [scripts/podman-logs.sh](scripts/podman-logs.sh:1)
- Health: [maintenance/maintenance.sh](maintenance/maintenance.sh:1) health
- Compose status: podman-compose -f [core/podman-compose.yml](core/podman-compose.yml:1) ps
- VPN IP: podman-compose -f [core/podman-compose.yml](core/podman-compose.yml:1) exec gluetun wget -qO- https://ipinfo.io

Notes
- Start with 1 → 2 → 3 for a strong baseline. Items 4–8 are situational or advanced.
- All commands assume execution from repository root unless noted otherwise.