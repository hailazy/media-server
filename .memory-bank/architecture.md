# Architecture

System overview
- Orchestrated with Podman Compose using a single compose file: [core/podman-compose.yml](core/podman-compose.yml:1)
- Operational scripts for lifecycle:
  - Start: [scripts/podman-up.sh](scripts/podman-up.sh:1)
  - Stop: [scripts/podman-down.sh](scripts/podman-down.sh:1)
  - Logs: [scripts/podman-logs.sh](scripts/podman-logs.sh:1)
  - Systemd wrapper: [scripts/podman-systemd-wrapper.sh](scripts/podman-systemd-wrapper.sh:1)
- Health and diagnostics:
  - Health/maintenance: [maintenance/maintenance.sh](maintenance/maintenance.sh:1)
  - Quick checks: [maintenance/quick-debug.sh](maintenance/quick-debug.sh:1)

High-level architecture
```
┌─────────────────────────────────────────────────────────────────┐
│                         Media Stack (Podman)                    │
│                                                                 │
│   ┌────────────┐     ┌───────────┐     ┌───────────┐            │
│   │  Prowlarr  │◄────│  Sonarr   │     │  Radarr   │            │
│   │   9696     │     │   8989    │     │   7878    │            │
│   └────────────┘     └───────────┘     └───────────┘            │
│          ▲                        ▲                  ▲          │
│          │                        │                  │          │
│          │                        │                  │          │
│          │                        │                  │          │
│   ┌────────────┐      ┌──────────────────────────────────────┐  │
│   │ FlareSolverr│      │            Jellyfin 8096            │  │
│   │    8191     │      │  (GPU optional; transcoding cache)  │  │
│   └────────────┘      └──────────────────────────────────────┘  │
│                                      ▲                           │
│                                      │                           │
│                         ┌──────────────────────────┐             │
│                         │      qBittorrent 8080    │             │
│                         │  (network_mode:gluetun)  │             │
│                         └─────────────▲────────────┘             │
│                                       │                          │
│                         ┌─────────────┴─────────────┐            │
│                         │     Gluetun (AirVPN)      │            │
│                         │  WireGuard + Port Fwd     │            │
│                         └───────────────────────────┘            │
└─────────────────────────────────────────────────────────────────┘
```

Key technical decisions
- VPN-first networking
  - qBittorrent runs with network_mode "container:gluetun" to enforce VPN routing at the container boundary.
  - AirVPN WireGuard credentials are provided via environment variables sourced from core/.env.
- Port forwarding
  - Enabled through Gluetun and exposed to qBittorrent automatically; verification steps are documented in [docs/QUICK-REF.md](docs/QUICK-REF.md:1) and [docs/PODMAN.md](docs/PODMAN.md:1).
- Rootless-first
  - Defaults target rootless Podman; optional rootful tuning is documented in [docs/PODMAN.md](docs/PODMAN.md:1).
- GPU support with boot reliability
  - NVIDIA CDI preferred with a boot-time race-condition fallback implemented in [scripts/podman-up.sh](scripts/podman-up.sh:1) and documented in [docs/GPU-TIMING-FIX.md](docs/GPU-TIMING-FIX.md:1).
- Single source of truth
  - One compose file [core/podman-compose.yml](core/podman-compose.yml:1) drives all service definitions, volumes, and environment wiring.

Source/code and configuration paths
- Compose: [core/podman-compose.yml](core/podman-compose.yml:1)
- Env templates: [core/.env.example](core/.env.example:1), optional [core/.env.performance](core/.env.performance:1)
- Scripts: [scripts/podman-up.sh](scripts/podman-up.sh:1), [scripts/podman-down.sh](scripts/podman-down.sh:1), [scripts/podman-logs.sh](scripts/podman-logs.sh:1), [scripts/podman-systemd-wrapper.sh](scripts/podman-systemd-wrapper.sh:1)
- Maintenance: [maintenance/maintenance.sh](maintenance/maintenance.sh:1), [maintenance/quick-debug.sh](maintenance/quick-debug.sh:1)
- AirVPN servers data (if used): [services/gluetun/servers.json](services/gluetun/servers.json:1)
- Documentation entry points: [docs/README.md](docs/README.md:1), [docs/QUICK-REF.md](docs/QUICK-REF.md:1), [docs/PODMAN.md](docs/PODMAN.md:1)

Component relationships
- Prowlarr → Sonarr/Radarr: Indexers feed downstream apps
- Sonarr/Radarr → qBittorrent: Download client over http://gluetun:8080
- Bazarr → Sonarr/Radarr: Subtitle fetching using *arr API endpoints
- Jellyfin → Media directories: Serves /movies and /tv-shows from host
- qBittorrent → Gluetun: All qBittorrent traffic egress via VPN container
- Gluetun ↔ AirVPN: WireGuard session, optional port forwarding

Critical implementation paths
- First boot path
  1) Copy envs: core/.env.example → core/.env
  2) Start: [scripts/podman-up.sh](scripts/podman-up.sh:1)
  3) Health: [maintenance/maintenance.sh](maintenance/maintenance.sh:1) health
- Troubleshooting path
  1) Quick triage: [maintenance/quick-debug.sh](maintenance/quick-debug.sh:1)
  2) Logs: [scripts/podman-logs.sh](scripts/podman-logs.sh:1)
  3) VPN verification: podman-compose -f core/podman-compose.yml exec gluetun wget -qO- https://ipinfo.io
- GPU boot fallback path
  - Detection and fallback compose selection implemented in [scripts/podman-up.sh](scripts/podman-up.sh:1); behavior and rationale documented in [docs/GPU-TIMING-FIX.md](docs/GPU-TIMING-FIX.md:1).

Security model
- VPN isolation: qBittorrent cannot reach the WAN without Gluetun
- Least privilege: Rootless Podman by default, optional rootful for performance
- SELinux: Compose and docs include guidance for labeling and policy considerations (see [docs/PODMAN.md](docs/PODMAN.md:1))