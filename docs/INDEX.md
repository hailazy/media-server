# Home Server — Documentation Index

Self-hosted personal services orchestrated as **modular podman-compose sections**, sharing scripts and a KDE tray indicator. Each section is its own podman-compose stack with its own `.env` and `data/` directory.

## Sections (canonical READMEs live with each section)

| Section | Purpose | Endpoint | README |
|---------|---------|----------|--------|
| `media/` | Jellyfin + Sonarr/Radarr/Bazarr/Prowlarr + qBittorrent + Gluetun (AirVPN) + FlareSolverr | http://localhost:8096 (Jellyfin) | (no README — see `docs/` below) |
| `forge/` | Stable Diffusion WebUI Forge — shared image gen | http://localhost:7860 | [`forge/README.md`](../forge/README.md) |
| `sillytavern/` | LLM chat UI with character cards, image-gen integration | http://localhost:8000 | [`sillytavern/README.md`](../sillytavern/README.md) |
| `dashboard/` | Homarr — single pane of glass | http://localhost:7575 | [`dashboard/README.md`](../dashboard/README.md) |

Per-section READMEs cover ops, gotchas, and integration. The docs in this folder cover **cross-cutting** concerns + media-section deep-dives.

## Cross-cutting docs

1. **[QUICK-REF.md](QUICK-REF.md)** — daily-driver commands, tray, VRAM budget, common issues. **Read first.**
2. **[README.md](README.md)** — home-server overview, architecture, requirements, install.
3. **[PODMAN.md](PODMAN.md)** — Podman fundamentals: rootless vs rootful, SELinux, GPU CDI, systemd integration. Read after first run if you need platform depth.
4. **[AIRVPN-VALIDATION-CHECKLIST.md](AIRVPN-VALIDATION-CHECKLIST.md)** — AirVPN + Gluetun setup, the 4 chain-bug gotchas, port forwarding wiring.

## Media section deep-dives ([docs/media/](media/))

Hardware/performance docs specific to the media stack:

- **[media/JELLYFIN-PERFORMANCE-OPTIMIZATION.md](media/JELLYFIN-PERFORMANCE-OPTIMIZATION.md)** — NVENC/NVDEC tuning, codec strategy, anti-patterns (rewritten 2026-05-03).
- **[media/QBITTORRENT-PERFORMANCE-OPTIMIZATION.md](media/QBITTORRENT-PERFORMANCE-OPTIMIZATION.md)** — qBT through Gluetun, AirVPN PF wiring, API control (rewritten 2026-05-03).
- **[media/GPU-TIMING-FIX.md](media/GPU-TIMING-FIX.md)** — CDI auto-regen technique. Pre-migration; technique still applied via `scripts/_lib.sh`.
- **[media/BOOT-STARTUP-INVESTIGATION.md](media/BOOT-STARTUP-INVESTIGATION.md)** — Historical case study from Oct 2025.

## Shared infrastructure

- **`scripts/`** — section ops + tray:
  - `up.sh <section>` / `down.sh <section>` / `logs.sh <section>` — section lifecycle
  - `category.sh {ai|media|all} {toggle|up|down|status}` — multi-section ops (used by tray)
  - `tray.py` — KDE Plasma tray indicator (autostart via `~/.config/autostart/home-server-tray.desktop`)
  - `vram-guard.sh` — VRAM budgeting between Forge and Jellyfin (16GB ceiling on RTX 4070 Ti SUPER)
  - `dashboard-backup.sh` / `dashboard-restore.sh` — Homarr SQLite snapshot
  - `_lib.sh` — shared logging, GPU CDI auto-regen, network helpers
- **`imagegen/`** — shared **cloud** image-gen CLI (GPT Image 2) with content-hash cache + cost ledger, consumed by repo skills (IC concept-gen today). The cloud counterpart to `forge/` (local). Contract + extension guide: [`imagegen/README.md`](../imagegen/README.md).
- **`AGENTS.md`** + **`.claude/CLAUDE.md`** — AI-agent operating instructions for this repo.

## Role-based quick paths

**New install (10-15 min)**
1. `cp <section>/.env.example <section>/.env` for each section you want
2. `./scripts/up.sh <section>` (or `all`)
3. `./scripts/up.sh dashboard` → http://localhost:7575 → onboarding
4. KDE tray autostart: `cp scripts/launcher.sh ~/.local/bin/` (already configured if migrated)

**Daily ops**
- Tray icon shows section state (🟢 all up · 🟡 partial · ⚫ down). Right-click → start/stop categories.
- Logs: `./scripts/logs.sh <section> -f`

**Troubleshooting**
1. Quick triage: `./scripts/logs.sh <section>` last 50 lines
2. VPN check (media): `podman exec gluetun wget -qO- https://ipinfo.io`
3. Targeted: `media/maintenance/quick-debug.sh` for media-stack-specific
4. Path issues from re-creating `.env`: see `AIRVPN-VALIDATION-CHECKLIST.md`

**Advanced tuning** (see media deep-dives)

## Conventions

- All commands run from repo root unless noted.
- `<section>/.env` is gitignored; `<section>/.env.example` is the template.
- Container state lives in `<section>/data/` (also gitignored).
- AI sections (forge, sillytavern, dashboard) share `home-net` Podman network for cross-container DNS (`http://home-forge:7860`, etc.).
- Media stack runs on its own network (default project network); dashboard reaches it via `host.containers.internal`.
