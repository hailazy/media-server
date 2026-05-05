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
- ST RP image gen production-ready (2026-05-05): NoobAI XL prompt playbook at `sillytavern/PROMPT-PLAYBOOK.md` — 33 verified gotchas. Mode 4 template stripped v7.1 → v8.2 (4258 → 2144 chars, 5 hard rules only — Magnum picks tags from booru training). Summary workflow added: manual via QR `[📝 Summary]` using `/dom action=click` workaround (gotcha 5.33: STscript path locks `is_send_press` → `/summarize` slash command silent fails; native DOM click on panel button bypasses lock). Settings stack: `prompt_builder=1 (RAW_BLOCKING)`, `SkipWIAN=True`, `promptInterval=0` (manual only), `source=main`. LALib enabled for `/dom`. GuidedGenerations Extension currently disabled (was disabled for diagnostic, can be re-enabled — not the culprit, doesn't affect /dom workaround). Magnum v4 72B retained as compliant non-RP extractor — alternatives queued as future benchmark
- Pending: Homarr widget upgrade for media tiles, optional reverse proxy for LAN access, add indexers in Prowlarr (per-user)
