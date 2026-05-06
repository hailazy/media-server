# Claude Code — Home Server

@~/.claude/brains/indie-ecosystem.md

## What This Is
Home server orchestrating self-hosted personal services. Single repo, modular sections (media, forge, sillytavern, dashboard) — each with own podman-compose stack, sharing scripts and dashboard.

## Sections
- `media/` — Jellyfin + arr stack (Sonarr/Radarr/Bazarr/Prowlarr) + qBittorrent + Gluetun VPN
- `forge/` — Stable Diffusion WebUI Forge (shared image gen, multi-model: NSFW + educational)
- `sillytavern/` — SillyTavern chat UI (calls Forge for image gen)
- `dashboard/` — Homarr (service launchpad, status pings)

## Project Values
- **Reliability over features** — Prefer battle-tested approaches. Stability > novelty.
- **Self-hosted first** — Avoid external dependencies. Privacy + control priority.
- **Minimal impact** — Smallest necessary change. No over-engineering.
- **No dirty state** — Verify changes work before marking task complete.
- **Reversibility** — Significant changes must be undoable.

## Operations

### Scripts (CLI)
- Start a section: `./scripts/up.sh {media|forge|sillytavern|dashboard|all}`
- Stop: `./scripts/down.sh <section>`
- Logs: `./scripts/logs.sh <section> -f [services...]`
- Toggle by category: `./scripts/category.sh {ai|media|all} {toggle|up|down|status}` (used by tray + .desktop Actions)
- Update images: `./scripts/update.sh` — pulls latest images for all sections, prompts to recycle running ones
- Dashboard backup/restore: `./scripts/dashboard-backup.sh` / `./scripts/dashboard-restore.sh <backup.tar.gz>`
- Pre-flight: GPU CDI auto-regen for media+forge (handled by `scripts/_lib.sh`)
- VRAM guard: `scripts/vram-guard.sh check <section>` runs before GPU-using sections start

### System tray (KDE Plasma)
- `scripts/tray.py` — PyQt6 tray indicator with dynamic state-aware menu
- Autostart entry: `~/.config/autostart/home-server-tray.desktop`
- Icon color: 🟢 all up · 🟡 partial · ⚫ all down
- Right-click menu: dynamic Start/Stop per category (AI, Media, All), Open Dashboard, Update Services, Refresh, Quit
- Update Services opens `update.sh` in a terminal (konsole → gnome-terminal → xterm fallback chain) so user sees pull progress + interactive recycle prompt
- Double-click: open Homarr dashboard (auto-starts if down)
- Only the tray itself autostarts on login. Sections (forge/ST/media) stay down until user toggles — saves VRAM.

### Dashboard one-time setup
Homarr v1.x stores config in SQLite — file-level seeding impractical (tRPC + bcrypt + encryption). Setup once via UI, then `dashboard-backup.sh` for instant recovery on container wipe.

After media stack is configured: upgrade Homarr tiles from plain "App" to specialty widgets (Current media server streams, Media releases, Indexer manager status, Download Client) — requires API keys per service.

## VRAM Budget (RTX 4070 Ti Super 16GB)
| Combo | Peak | Status |
|-------|------|--------|
| Forge SDXL alone | ~12GB | Safe |
| Jellyfin NVENC alone | ~2GB | Safe |
| Forge + Jellyfin idle | ~12GB | Safe |
| Forge + Jellyfin NVENC active | ~14GB | Tight, warn |
| Forge + Jellyfin 4K HEVC transcode | ~15-16GB | Refuse start |

`vram-guard.sh` enforces: soft warn at 13GB used, hard refuse at 15GB used.

## Boundaries
- Verify changes don't break media access before completing tasks
- Be cautious with data operations — media files large + irreplaceable
- Forge model swaps trigger VRAM spikes — let `vram-guard.sh` validate

## Gotchas

- **Forge port binding:** `127.0.0.1:7860` (localhost-only). Forge ai-dock image disables auth (`WEB_ENABLE_AUTH=false`); never bind to `0.0.0.0`. Container clients still reach it via `http://home-forge:7860` on `home-net`. If LAN/remote access is needed, add an authenticated reverse proxy in front (Caddy basic-auth, Tailscale Funnel, etc.).
- **Homarr v1.x volume:** mount `./data:/appdata:z` (NOT `/data` — earlier wrong path wiped setup on container restart)
- **Homarr container DNS:** Forge + ST cùng `home-net` → `http://home-forge:7860` etc. Media stack ở compose network khác → reach via `host.containers.internal:PORT`
- **Bind mount ownership:** Container UIDs map through subuid; use `podman unshare` for file ops on container-owned dirs (e.g., moving model files, tar/untar backups)
- **Forge forge_args.conf:** controls launch flags, NOT just `WEBUI_FLAGS` env var alone (ai-dock image quirk)
- **Forge ai-dock image stale:** vpred models broken (Zero Terminal SNR ignored); stick with epsilon-prediction checkpoints
- **Forge UI config persistence:** `config.json` + `ui-config.json` ở root webui dir KHÔNG nằm trong bind mount mặc định → ADetailer/sampler/UI defaults reset mỗi restart. Fix: `forge_args.conf` thêm `--ui-settings-file /opt/stable-diffusion-webui-forge/config/config.json --ui-config-file /opt/stable-diffusion-webui-forge/config/ui-config.json` để webui ghi vào mounted `data/forge/config/` thay vì root. Áp dụng 2026-05-06.
- **Forge InputAccordion master toggles:** `Hires. fix` + `ADetailer` enable checkbox không persist qua container restart dù Forge ghi đúng vào ui-config.json (gradio render từ hardcoded `value=False` constructor, setattr post-render không reflect). Fix: source patch — `forge/patches/ui.py` bind-mounted thay `modules/ui.py` (line 329 đổi `InputAccordion(False, ...)` → `True`), + sed edit `data/forge/extensions/adetailer/aaaaaa/ui.py` line 132 `value=False` → `value=True`. Re-patch khi Forge image hoặc ADetailer extension upgrade. 2026-05-07.

## Security
**CRITICAL**: NEVER commit, push, or expose secrets, API keys, tokens, or credentials.

- Use `.env` files per section, never hardcode
- Verify `git diff --cached` before commit
- `.gitignore` must cover `.env*`, `*.key`, `*.pem`, `dashboard/data/`, `dashboard/backups/`
- Dashboard backups contain admin password hash + encryption key usage — treat as secrets
- ASK before committing sensitive-looking files
- If secret leaked: STOP, alert user, revoke, remove from history
