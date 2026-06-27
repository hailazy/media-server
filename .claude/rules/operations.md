---
paths:
  - "scripts/**"
  - "dashboard/**"
---

# Operations — Scripts CLI, system tray, dashboard setup. Auto-loads when working in scripts/ or dashboard/.

### Scripts (CLI)
- Start a section: `./scripts/up.sh {media|forge|sillytavern|dashboard|all}`
- Stop: `./scripts/down.sh <section>`
- Logs: `./scripts/logs.sh <section> -f [services...]`
- Toggle by category: `./scripts/category.sh {ai|media|all} {toggle|up|down|status}` (used by tray + .desktop Actions)
- Update images: `./scripts/update.sh` — pulls latest images for all sections, prompts to recycle running ones
- Dashboard backup/restore: `./scripts/dashboard-backup.sh` / `./scripts/dashboard-restore.sh <backup.tar.gz>`
- Pre-flight: GPU CDI auto-regen for media+forge (handled by `scripts/_lib.sh`)
- VRAM guard: `scripts/vram-guard.sh check <section>` runs before GPU-using sections start
- **Claude Code wrapper**: `./scripts/claude.sh` — sources `.env` (Civitai API key, etc.) before launching Claude Code. Required for project-scoped MCP servers (`.mcp.json`) that reference `${ENV_VAR}` from shell environment

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
