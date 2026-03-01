# Tech

Technologies used
- Containers and orchestration
  - Podman (rootless-first), podman-compose
  - Systemd user services for autostart
  - LinuxServer.io images for *arr suite and Jellyfin
- VPN and networking
  - Gluetun as VPN gateway with AirVPN + WireGuard
  - Container network isolation using network_mode "container:gluetun"
  - AirVPN static port-forwarding integration
- GPU acceleration
  - NVIDIA CDI (Container Device Interface) for Jellyfin
  - VAAPI fallback via /dev/dri for Intel/AMD
- Shell and tooling
  - Bash scripts for lifecycle ops and maintenance
  - SELinux compatible bind-mounts and labels

Development setup
- Core compose and environment files
  - Compose: [core/podman-compose.yml](core/podman-compose.yml:1)
  - Env template: [core/.env.example](core/.env.example:1)
  - Optional performance overlay: [core/.env.performance](core/.env.performance:1)
- Lifecycle scripts
  - Start: [scripts/podman-up.sh](scripts/podman-up.sh:1)
  - Stop: [scripts/podman-down.sh](scripts/podman-down.sh:1)
  - Logs: [scripts/podman-logs.sh](scripts/podman-logs.sh:1)
  - Systemd wrapper: [scripts/podman-systemd-wrapper.sh](scripts/podman-systemd-wrapper.sh:1)
- Maintenance and diagnostics
  - Health and diagnostics: [maintenance/maintenance.sh](maintenance/maintenance.sh:1)
  - Quick triage: [maintenance/quick-debug.sh](maintenance/quick-debug.sh:1)
- Documentation entry points
  - First stop: [docs/INDEX.md](docs/INDEX.md:1)
  - Overview: [docs/README.md](docs/README.md:1)
  - Quick reference: [docs/QUICK-REF.md](docs/QUICK-REF.md:1)
  - Podman guide: [docs/PODMAN.md](docs/PODMAN.md:1)
  - GPU startup fix: [docs/GPU-TIMING-FIX.md](docs/GPU-TIMING-FIX.md:1)

Technical constraints
- Rootless-first model
  - No privileged daemon; port bindings <1024 require mapping to high ports
  - Certain sysctls unavailable; documented alternatives in [docs/PODMAN.md](docs/PODMAN.md:1)
- SELinux
  - Use :Z/:z labeling on bind-mounts; see examples in [core/podman-compose.yml](core/podman-compose.yml:1)
- VPN isolation
  - qBittorrent must run with network_mode "container:gluetun"; do not expose qbittorrent ports directly on host
- GPU availability at boot
  - Race condition mitigation implemented in [scripts/podman-up.sh](scripts/podman-up.sh:1) and described in [docs/GPU-TIMING-FIX.md](docs/GPU-TIMING-FIX.md:1)

Dependencies
- Host
  - Podman ≥ 4.x and podman-compose installed
  - Optional: NVIDIA drivers + nvidia-container-toolkit for CDI
  - Storage directories: /media/Storage/{downloads,movies,tv-shows}
- AirVPN account
  - WireGuard credentials from AirVPN Config Generator (PrivateKey, Address)
  - Optional port forwarding enabled in AirVPN client area

Tool usage patterns
- Operations
  - Start/Stop via scripts for consistency:
    - Start: [scripts/podman-up.sh](scripts/podman-up.sh:1)
    - Stop: [scripts/podman-down.sh](scripts/podman-down.sh:1)
    - Logs: [scripts/podman-logs.sh](scripts/podman-logs.sh:1)
- Health and verification
  - First check: [maintenance/maintenance.sh](maintenance/maintenance.sh:1) health
  - VPN IP check: podman-compose -f [core/podman-compose.yml](core/podman-compose.yml:1) exec gluetun wget -qO- https://ipinfo.io
- Configuration workflow
  - Copy [core/.env.example](core/.env.example:1) → core/.env; set AirVPN WireGuard and qBittorrent credentials
  - Optional performance tuning with [core/.env.performance](core/.env.performance:1)
- GPU boot reliability
  - Automatic fallback to no-GPU compose variant if devices are unavailable; details in [docs/GPU-TIMING-FIX.md](docs/GPU-TIMING-FIX.md:1)

Testing and validation
- Compose validation
  - podman-compose -f [core/podman-compose.yml](core/podman-compose.yml:1) config
- Service health
  - [maintenance/maintenance.sh](maintenance/maintenance.sh:1) health then targeted checks (VPN, PF, services)
- VPN routing correctness
  - Ensure gluetun-reported IP differs from host and qbittorrent inherits same egress via network_mode

Notes for contributors
- Follow rootless-compatible patterns unless a documented rootful optimization is required and justified in [docs/PODMAN.md](docs/PODMAN.md:1)
- Keep single source of truth in [core/podman-compose.yml](core/podman-compose.yml:1); prefer env indirection over hard-coded values
- When updating docs, ensure all internal references use correct paths and clickable references to reduce drift