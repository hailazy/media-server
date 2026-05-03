# Home Server Quick Reference

Daily-driver command card. Start here for any task.

> **Full overview:** [README.md](README.md) · **Doc map:** [INDEX.md](INDEX.md)

---

## Essential commands

```bash
# Section lifecycle (run from repo root)
./scripts/up.sh    {media|forge|sillytavern|dashboard|all}
./scripts/down.sh  <section>
./scripts/logs.sh  <section> -f [service...]    # follow logs

# Multi-section (used by tray)
./scripts/category.sh {ai|media|all} {toggle|up|down|status}

# Dashboard backup (Homarr SQLite is one-time setup; back it up)
./scripts/dashboard-backup.sh
./scripts/dashboard-restore.sh <backup.tar.gz>

# Media-stack tools
./media/maintenance/maintenance.sh health
./media/maintenance/quick-debug.sh

# First-time / post-wipe wiring (Prowlarr↔arrs, Sonarr/Radarr→qBT, Bazarr↔arrs, root folders)
./media/scripts/provision.sh
```

## Tray indicator (KDE Plasma)

`scripts/tray.py` autostarts on login. State at a glance:

| Icon | Meaning |
|------|---------|
| 🟢 | All sections up |
| 🟡 | Partial (some down) |
| ⚫ | All down |

Right-click → start/stop per category. Double-click → opens dashboard at `:7575` (auto-starts dashboard if down). Configured via `~/.config/autostart/home-server-tray.desktop` → `scripts/launcher.sh`.

---

## Service ports

| Service | Port | Section | Auth |
|---------|------|---------|------|
| Jellyfin | 8096 | media | Setup on first run |
| qBittorrent WebUI | 8080 | media (via gluetun) | Temp password from logs (see below) |
| Sonarr | 8989 | media | Web setup |
| Radarr | 7878 | media | Web setup |
| Bazarr | 6767 | media | Web setup |
| Prowlarr | 9696 | media | Web setup |
| FlareSolverr | 8191 | media | None |
| Forge WebUI | 7860 | forge | None (localhost-only) |
| SillyTavern | 8000 | sillytavern | ST built-in |
| Homarr | 7575 | dashboard | Web setup (admin/password) |

Add a reverse proxy with auth if you need LAN/remote access to anything other than dashboard.

---

## VRAM budget (RTX 4070 Ti SUPER 16GB)

Enforced by `scripts/vram-guard.sh` before GPU sections start.

| Combo | Peak VRAM | Status |
|-------|-----------|--------|
| Forge SDXL alone | ~12GB | Safe |
| Jellyfin NVENC alone | ~2GB | Safe |
| Forge + Jellyfin idle | ~12GB | Safe |
| Forge + Jellyfin transcoding | ~14GB | Tight, soft warn |
| Forge + Jellyfin 4K HEVC | ~15-16GB | Hard refuse |

Don't run Forge + heavy transcoding simultaneously. Tray makes it easy to toggle one off.

---

## VPN verification (media section)

```bash
# Confirm tunnel is up + exit IP is AirVPN
podman exec gluetun wget -qO- https://ipinfo.io
# Expect: Singapore (M247 Europe SRL) — NOT your home WAN IP

# Tunnel + firewall ports
podman logs gluetun | grep -E "allowed input port|VPN connection"
```

If the IP shows your home WAN, qBT is leaking. Check `network_mode: container:gluetun` on qBT service.

---

## First-time setup (or post-wipe re-deploy)

```bash
# 1. Configure media/.env (copy from .env.example, fill credentials + AirVPN keys)
cp media/.env.example media/.env
$EDITOR media/.env
#   Required: AIRVPN_*, QBIT_USER/QBIT_PASS, ARR_USER/ARR_PASS

# 2. Bring stack up
./scripts/up.sh media

# 3. Wire all services together (auth, Prowlarr↔arrs, qBT, Bazarr, root folders)
./media/scripts/provision.sh
```

`provision.sh` is idempotent — safe to re-run any time. It:
- Reads arr API keys from `media/data/<service>/config.{xml,yaml}` (auto-discovered, no manual copy)
- Sets Forms auth on Prowlarr/Sonarr/Radarr from `ARR_USER`/`ARR_PASS`, with login disabled for local addresses (no UI prompt from localhost/LAN)
- Sets qBittorrent permanent password from `QBIT_PASS` (replaces the temp from logs)
- Adds Sonarr+Radarr to Prowlarr (Apps), FlareSolverr proxy
- Adds qBittorrent as download client in Sonarr+Radarr
- Sets root folders `/tv` (Sonarr) and `/movies` (Radarr)
- Configures Bazarr to talk to Sonarr+Radarr

After it runs: optionally bulk-add indexers via:

```bash
./media/scripts/add-public-indexers.sh
```

Pulls Prowlarr's public-torrent indexer registry (~95 indexers as of 2026-05) and bulk-adds via API. Idempotent (skips already-added). Auto-creates a `flaresolverr` tag, attaches it to the FlareSolverr proxy, and tags every new indexer — Cloudflare-protected indexers route through FlareSolverr automatically. Expect ~70-75 success / ~20 fail (dead trackers, region blocks, redirected sites — these need manual addition or pruning).

---

## Common issues

### qBittorrent: temp password on first run / after reset
```bash
podman logs qbittorrent 2>&1 | grep "temporary password"
# A temporary password is provided for this session: X2Wm96dyp
```
Default user `admin`. Run `./media/scripts/provision.sh` to set the permanent password from `QBIT_PASS` in `.env` (idempotent). Or set via UI (Tools → Options → Web UI). Temp regenerates each container recreate; permanent persists in volume.

### Gluetun env changes don't take effect after `podman restart`
Restart preserves env baked at create time. To apply env changes:
```bash
./scripts/down.sh media && ./scripts/up.sh media
```

### AirVPN-specific config gotchas (from `commit 0238a98`)
1. **`AIRVPN_SERVER_COUNTRIES`** uses full names (`Singapore`), NOT ISO codes (`SG`).
2. **`AIRVPN_PORT_FORWARDING=false`** — gluetun doesn't auto-PF for AirVPN. PF is via airvpn.org client area.
3. **`AIRVPN_WIREGUARD_PRESHARED_KEY`** is mandatory — extract from AirVPN's `.conf` file `[Peer] PresharedKey`.
4. **PF wiring** = AirVPN client area port + `FIREWALL_VPN_INPUT_PORTS` in compose + qBT listening port (all three must match).

Full details: [AIRVPN-VALIDATION-CHECKLIST.md](AIRVPN-VALIDATION-CHECKLIST.md).

### Container UID issues editing `data/` from host
`data/` directories are container-owned (UID mapped via subuid). Use `podman unshare` for host-side ops:
```bash
podman unshare rm -rf media/data/qbittorrent/some-config
podman unshare chown -R 1000:1000 forge/data/
```

### GPU not available after driver upgrade
CDI auto-regenerates via `_lib.sh:check_nvidia_cdi_configuration`. If a section fails to start with GPU errors, manual regen:
```bash
nvidia-ctk cdi generate --output ~/.config/containers/cdi/nvidia.yaml
```

### Forge ai-dock image stale
- `vpred` SDXL models broken (Zero Terminal SNR ignored). Use epsilon-prediction checkpoints.
- Cold start ~3 minutes (xformers download); healthcheck waits 180s.
- Launch flags via `forge/forge_args.conf`, NOT just `WEBUI_FLAGS` env.

### Homarr tile pings fail
Homarr v1.x runs in container. For media stack tiles, use **Use different URL for ping**:
- Browser URL: `http://localhost:8096` (your view)
- Ping URL: `http://host.containers.internal:8096` (Homarr's view)

For AI sections (same `home-net` network), ping URL is container DNS: `http://home-forge:7860`.

### Dashboard wiped after container restart
Homarr v1.x stores state in SQLite. The compose mounts `./data:/appdata` (NOT `/data` — that path was wrong in earlier setup and wiped state). Verify mount:
```bash
podman inspect home-dashboard --format '{{json .Mounts}}' | python3 -m json.tool
```

---

## Daily checks

```bash
# Tray icon — first signal
# 🟢 = all good. 🟡 / ⚫ = open scripts/logs.sh

# VPN tunnel still up
podman exec gluetun wget -qO- https://ipinfo.io

# Disk space (downloads grow fast)
df -h /home/haint/Data
```

## Weekly maintenance

```bash
# Pull container updates
for s in media forge sillytavern dashboard; do
  podman-compose -f $s/compose.yml pull
done

# Recycle to apply
./scripts/down.sh all && ./scripts/up.sh all

# Backup dashboard config
./scripts/dashboard-backup.sh
```

---

## File map

```
home-server/
├── media/        compose.yml + .env + data/ + maintenance/   (Jellyfin + arr + qBT + VPN)
├── forge/        compose.yml + .env + data/                  (Stable Diffusion)
├── sillytavern/  compose.yml + .env + data/                  (LLM chat UI)
├── dashboard/    compose.yml + .env + data/ + backups/       (Homarr)
├── scripts/      up.sh down.sh logs.sh category.sh
│                 tray.py launcher.sh vram-guard.sh
│                 dashboard-backup.sh dashboard-restore.sh
│                 _lib.sh                                    (shared lib)
├── docs/         INDEX  README  QUICK-REF (this)
│   ├─ PODMAN  AIRVPN-VALIDATION-CHECKLIST
│   └─ media/   JELLYFIN-PERF  QBT-PERF  GPU-TIMING  BOOT-INVESTIGATION
└── .claude/  .githooks/  AGENTS.md  CLAUDE.md
```

---

## See also

- [README.md](README.md) — overview, requirements, install
- [INDEX.md](INDEX.md) — full doc map
- [PODMAN.md](PODMAN.md) — Podman fundamentals (rootless, SELinux, GPU)
- [AIRVPN-VALIDATION-CHECKLIST.md](AIRVPN-VALIDATION-CHECKLIST.md) — VPN setup
- [media/JELLYFIN-PERFORMANCE-OPTIMIZATION.md](media/JELLYFIN-PERFORMANCE-OPTIMIZATION.md) — transcoding tuning
- [media/QBITTORRENT-PERFORMANCE-OPTIMIZATION.md](media/QBITTORRENT-PERFORMANCE-OPTIMIZATION.md) — qBT through VPN
- Per-section READMEs: [forge/README.md](../forge/README.md), [sillytavern/README.md](../sillytavern/README.md), [dashboard/README.md](../dashboard/README.md)
