# Context

Current work focus
- Documentation cleanup and normalization (remove “Roocline”, fix paths/commands) across:
  - [docs/QUICK-REF.md](docs/QUICK-REF.md:1)
  - [docs/README.md](docs/README.md:1)
  - [docs/PODMAN.md](docs/PODMAN.md:1)
  - [docs/GPU-TIMING-FIX.md](docs/GPU-TIMING-FIX.md:1)
  - [docs/QBITTORRENT-PERFORMANCE-OPTIMIZATION.md](docs/QBITTORRENT-PERFORMANCE-OPTIMIZATION.md:1)
  - [docs/JELLYFIN-PERFORMANCE-OPTIMIZATION.md](docs/JELLYFIN-PERFORMANCE-OPTIMIZATION.md:1)
  - [docs/BOOT-STARTUP-INVESTIGATION.md](docs/BOOT-STARTUP-INVESTIGATION.md:1)
- Documentation reorganization: Start Here index, reading-order banners, command/link normalization.
- Memory Bank initialization under [`.kilocode/rules/memory-bank/`](.kilocode/rules/memory-bank): created [product.md](.kilocode/rules/memory-bank/product.md:1). Next: add [architecture.md](.kilocode/rules/memory-bank/architecture.md:1), [tech.md](.kilocode/rules/memory-bank/tech.md:1), and [tasks.md](.kilocode/rules/memory-bank/tasks.md:1).

Recent changes
- Removed all “Roocline” references from documentation.
- Standardized compose usage to [core/podman-compose.yml](core/podman-compose.yml:1).
- Replaced references to non-existent root scripts with:
  - [scripts/podman-up.sh](scripts/podman-up.sh:1)
  - [scripts/podman-down.sh](scripts/podman-down.sh:1)
  - [scripts/podman-logs.sh](scripts/podman-logs.sh:1)
  - [maintenance/quick-debug.sh](maintenance/quick-debug.sh:1)
  - [maintenance/maintenance.sh](maintenance/maintenance.sh:1)
- Corrected links and systemd references in:
  - [docs/GPU-TIMING-FIX.md](docs/GPU-TIMING-FIX.md:1)
  - [docs/BOOT-STARTUP-INVESTIGATION.md](docs/BOOT-STARTUP-INVESTIGATION.md:1)
- Fixed broken relative links in:
  - [docs/QBITTORRENT-PERFORMANCE-OPTIMIZATION.md](docs/QBITTORRENT-PERFORMANCE-OPTIMIZATION.md:1)
  - [docs/JELLYFIN-PERFORMANCE-OPTIMIZATION.md](docs/JELLYFIN-PERFORMANCE-OPTIMIZATION.md:1)
- Added “Start here” and reading-order banners to eight docs; normalized internal repo links to root-relative with :1 anchors; standardized “podman-compose -f core/podman-compose.yml …” usage; removed stray artifact from [docs/README.md](docs/README.md:1).

Canonical paths and assumptions
- Compose file: [core/podman-compose.yml](core/podman-compose.yml:1)
- Environment files: [core/.env.example](core/.env.example:1), [core/.env.performance](core/.env.performance:1) (optional), core/.env (user-provided)
- Operations scripts: [scripts/podman-up.sh](scripts/podman-up.sh:1), [scripts/podman-down.sh](scripts/podman-down.sh:1), [scripts/podman-logs.sh](scripts/podman-logs.sh:1), [scripts/podman-systemd-wrapper.sh](scripts/podman-systemd-wrapper.sh:1)
- Maintenance utilities: [maintenance/maintenance.sh](maintenance/maintenance.sh:1), [maintenance/quick-debug.sh](maintenance/quick-debug.sh:1)
- Systemd unit (user-level): ~/.config/systemd/user/media-stack.service
- Storage directories: /media/Storage/{downloads,movies,tv-shows}

Next steps
- Create and populate: [architecture.md](.kilocode/rules/memory-bank/architecture.md:1), [tech.md](.kilocode/rules/memory-bank/tech.md:1), [tasks.md](.kilocode/rules/memory-bank/tasks.md:1).
- Validate remaining internal references across all docs and consolidate command usage patterns.
- Optional: update helper echoes in [scripts/podman-logs.sh](scripts/podman-logs.sh:1) and [maintenance/quick-debug.sh](maintenance/quick-debug.sh:1) to remove legacy root-level script mentions.
- Spot-check link integrity periodically; keep index in sync with doc set.