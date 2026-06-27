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
Scripts, tray indicator, and dashboard one-time setup ops live in `.claude/rules/operations.md` (auto-loads when working in `scripts/` or `dashboard/`).

## Gotchas (pointers)
Detailed gotchas live in path-scoped rule files — loaded automatically when working in each section. Safety-critical facts always on:

- **Forge** (`forge/**` → `.claude/rules/forge.md`): localhost-only port 7860, mem_limit 16g (lower → OOM exit 137), UI/ADetailer persistence needs forge_args + patches, downloads need `podman unshare`; VRAM hard-refuse at 15GB.
- **SillyTavern** (`sillytavern/**` → `.claude/rules/sillytavern.md`): ST MCP reads must be path-based (full tree 73KB > MCP limit); save the BARE settings dict (wrapping corrupts).
- **Media/Ebooks** (`media/**`, `ebooks/**` → `.claude/rules/media-ebooks.md`): linuxserver + CWA images use PUID=0/PGID=0 under rootless podman; Calibre Library at `/home/haint/Data/Calibre Library`.

## Boundaries
- Verify changes don't break media access before completing tasks
- Be cautious with data operations — media files large + irreplaceable
- Forge model swaps trigger VRAM spikes — let `vram-guard.sh` validate

## Security
**CRITICAL**: NEVER commit, push, or expose secrets, API keys, tokens, or credentials.

- Use `.env` files per section, never hardcode
- Verify `git diff --cached` before commit
- `.gitignore` must cover `.env*`, `*.key`, `*.pem`, `dashboard/data/`, `dashboard/backups/`
- Dashboard backups contain admin password hash + encryption key usage — treat as secrets
- ASK before committing sensitive-looking files
- If secret leaked: STOP, alert user, revoke, remove from history
