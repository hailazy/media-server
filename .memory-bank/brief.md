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
- ST RP image gen production-ready (2026-05-05): NoobAI XL prompt playbook at `sillytavern/PROMPT-PLAYBOOK.md` — **36 verified gotchas** (5.34: ST overwrites PNG when running; 5.35: V2 cards need V1 mirror sync; 5.36: ST disk cache `_cache/characters/<sha256>` is the source of truth, NOT the PNG — patches one-direction UI→file only, must patch cache `value` field directly to make UI see changes). Reliable PNG-patch sequence: stop ST → patch PNG (V1+V2) AND cache file value → start ST. Mode 4 template stripped v7.1 → v8.2 (4258 → 2144 chars, 5 hard rules only — Magnum picks tags from booru training). Summary workflow: manual via QR `[📝 Summary]` using `/dom action=click` workaround (gotcha 5.33). Settings stack: `prompt_builder=1 (RAW_BLOCKING)`, `SkipWIAN=True`, `promptInterval=0` (manual only), `source=main`. LALib enabled for `/dom`. `/st-setup --adv` flag added (2026-05-05): redistributes bloated card description into specialized fields (personality / scenario / mes_example / depth_prompt) via PNG tEXt patch, with mandatory ST stop/restart guard. Anti-overlap rule: each field has ONE job, no content lives in two places.
- Pending: Homarr widget upgrade for media tiles, optional reverse proxy for LAN access, add indexers in Prowlarr (per-user)
