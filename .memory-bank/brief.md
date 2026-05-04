# Home Server

## One-Liner
Self-hosted personal services orchestrated as modular podman-compose sections (media, forge, sillytavern, dashboard) sharing scripts + KDE tray indicator.

## Key Facts
| Field | Value |
|-------|-------|
| Stack | Podman + podman-compose (rootless), KDE Plasma tray, RTX 4070 Ti SUPER (CDI) |
| Sections | media (Jellyfin+arr+gluetun+qBT), forge (SD WebUI), sillytavern, dashboard (Homarr) |
| Media VPN | AirVPN WireGuard via gluetun → Singapore exit, PF on port 54273 |
| Storage | `/home/haint/Data/{downloads,movies,tv-shows}` (NVMe) |
| Status | active — all 4 sections functional, media stack production-ready 2026-05-03 |

## Current Focus
- Hardening: media stack now fully self-hosted with VPN+PF, all 8 containers healthy
- Pattern alignment: media/ refactored to match canonical AI-section structure (`data/` per section, per-section `.gitignore`, no orphan `configs/` at root)
- Auto-provisioning: `media/scripts/provision.sh` wires Prowlarr↔arrs, qBT download client, Bazarr, root folders, qBT permanent password — idempotent, no UI needed
- ST RP image gen production-ready (2026-05-05): NoobAI XL prompt playbook documented at `sillytavern/PROMPT-PLAYBOOK.md` — 32 verified gotchas (newest 5.32: POV/view tag stacking → split composition), aspect ratio decision tree, composition patterns, Mode 4 template v7.1 (load-bearing POV dedup rule), MagnumStrict preset (temp 0.7, bound to Magnum profile via `bind_preset_to_connection`). Magnum v4 72B retained as Mode 4 extractor — alternatives (Hermes 3, Qwen3 32B) queued as future benchmark, defer until pain signal
- Pending: Homarr widget upgrade for media tiles, optional reverse proxy for LAN access, add indexers in Prowlarr (per-user)
