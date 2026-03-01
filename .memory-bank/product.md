# Product: Media Stack with VPN

Why this exists
- Provide a private, automated home media pipeline that searches, downloads, organizes, and streams content through a VPN, with predictable setup and operations on modern Linux systems.

Problems it solves
- Privacy and IP exposure: All torrent traffic flows through a VPN gateway.
- Manual glue: Automates the end-to-end flow across multiple apps.
- Unclear networking: Standardizes Podman networking and port forwarding through a single VPN container.
- Troubleshooting fatigue: Ships with unified health checks and logs workflow.

How it works (high level)
1) VPN entrypoint: Gluetun establishes an AirVPN WireGuard connection using static config values from AirVPN Config Generator, acting as the gateway.
2) Downloading: qBittorrent runs in network_mode "container:gluetun" so all its traffic is forced through VPN.
3) Indexers and automation: Prowlarr manages indexers and feeds Sonarr/Radarr; Bazarr handles subtitles.
4) Library and playback: Jellyfin serves media, with optional GPU acceleration.
5) Operations: Start/stop/logs via scripts and a single compose file.

Core deliverables
- Single compose file: [core/podman-compose.yml](core/podman-compose.yml:1)
- Operations scripts: [scripts/podman-up.sh](scripts/podman-up.sh:1), [scripts/podman-down.sh](scripts/podman-down.sh:1), [scripts/podman-logs.sh](scripts/podman-logs.sh:1)
- Health and debugging: [maintenance/maintenance.sh](maintenance/maintenance.sh:1), [maintenance/quick-debug.sh](maintenance/quick-debug.sh:1)
- Documentation: [docs/README.md](docs/README.md:1), [docs/QUICK-REF.md](docs/QUICK-REF.md:1), [docs/PODMAN.md](docs/PODMAN.md:1)

User experience goals
- Fast first run: copy [core/.env.example](core/.env.example:1) to core/.env and populate 4–5 AirVPN variables, then bring up the stack.
- Clear daily operations: one health command, one logs command, one stop/start path.
- Predictable recovery: deterministic restart and diagnostic capture when something goes wrong.
- Secure by default: qbittorrent cannot leak traffic outside VPN; straightforward verification steps are documented.
- Rootless-first with optional rootful optimizations: secure defaults, with documented trade-offs if maximum performance is required.
- GPU-friendly: optional NVIDIA CDI support with a boot-time fallback for first-try reliability.

Primary user flows
- First boot
  - Configure AirVPN: copy [core/.env.example](core/.env.example:1) → core/.env
  - Start stack: [scripts/podman-up.sh](scripts/podman-up.sh:1)
  - Verify health: [maintenance/maintenance.sh](maintenance/maintenance.sh:1) health
- Normal ops
  - Logs and checks: [scripts/podman-logs.sh](scripts/podman-logs.sh:1), [maintenance/quick-debug.sh](maintenance/quick-debug.sh:1)
  - Weekly updates: pull images and redeploy via compose or scripts
- Troubleshooting
  - Health script → targeted debug → service restart as needed

Scope
- In scope: Podman-based orchestration, AirVPN + WireGuard via Gluetun, *arr suite, qBittorrent, Jellyfin, GPU acceleration (optional), health/diagnostics, and documentation.
- Out of scope: Docker-specific deployment, cloud hosting, multi-user auth management, seedbox integrations beyond AirVPN.

Non-goals
- No automatic WAN exposure for Jellyfin; leave remote access manual.
- No Dockerfiles for custom builds; rely on upstream images.
- No non-AirVPN providers in this baseline (extendable later).

Success criteria
- Stack starts cleanly rootless on current Fedora/Ubuntu with Podman ≥4.0 using [core/podman-compose.yml](core/podman-compose.yml:1).
- qBittorrent always routes through Gluetun; external IP check differs from host.
- Health workflow detects and guides remediation for 90% of common issues.
- GPU systems start reliably on first boot with the documented fallback behavior.
- All docs have valid internal references and consistent command paths (scripts/ and core/).

Key assumptions
- Linux host with Podman + podman-compose available.
- AirVPN account with WireGuard config generated (PrivateKey, Address values).
- Storage directories exist: /media/Storage/{downloads,movies,tv-shows} bound into containers.

Reference docs
- Start here index: [docs/INDEX.md](docs/INDEX.md:1)
- Overview and quick start: [docs/README.md](docs/README.md:1)
- Commands and checks: [docs/QUICK-REF.md](docs/QUICK-REF.md:1)
- Podman details and trade-offs: [docs/PODMAN.md](docs/PODMAN.md:1)