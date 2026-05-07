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
- ST RP image gen production-ready (2026-05-05): NoobAI XL prompt playbook at `sillytavern/PROMPT-PLAYBOOK.md` — **39 verified gotchas**. Reliable PNG-patch sequence: stop ST → patch PNG (V1+V2) AND cache file value → start ST (gotchas 5.34-5.36). `/st-setup --adv` flag (2026-05-05): redistributes bloated card description into specialized fields, anti-overlap rule.
- **Magnum image-prompt retired (2026-05-06)** — Workflow flip: prompt extraction moved OUT of ST, replaced by Claude skill `/st-gen-image-prompt` (gotcha 5.37). Skill reads chat full context + char card + persona + identity baseline → generates booru tags → user paste vào ST `🎨 Freestyle` button (`/sd {{input}}` Mode FREE pass-through, gotcha 5.39). char_prompts emptied, identity baselines moved sang `~/.claude/skills/st-gen-image-prompt/data/identity-baselines/` (gotcha 5.38). Mode 0/1/2/4/5 templates emptied; Mode 7 (BG) still LLM-handled. Tag verification via Danbooru DB lazy-fetch (~5MB cache trong `~/.cache/`). Magnum profile chỉ còn cần cho Summary (gotcha 5.33). QR ImageGen.json gọn lại 3 buttons: 🎨 Freestyle, 🌅 BG, 📝 Summary.
- **Forge config hardened (2026-05-06/07)** — 4 fixes: (1) ADetailer hand_yolov8n.pt enabled via ST patched index.js bind-mount + Forge ui-config.json 2nd slot default = `hand_yolov8n.pt` (gotcha 5.40); confidence 0.3, denoising 0.4 verified via API smoke test. Finger anatomy auto-fixed mỗi gen (+5-8s per image). (2) `forge_args.conf` lean cho 16GB cards — drop `--cuda-malloc / --cuda-stream / --pin-shared-memory` (gotcha 5.41); 3 args chỉ benefit cards <10GB. (3) Forge UI config persistence — `--ui-settings-file` + `--ui-config-file` flags redirect `config.json` + `ui-config.json` về mounted `data/forge/config/` (gotcha 5.42); XL preset stack (Euler+Karras+832×1216+CFG5+4x-AnimeSharp) + sd_model_checkpoint persist; ownership chown 525287 (container UID 1000). (4) InputAccordion master toggle source patch (gotcha 5.43) — `Hires. fix` + `ADetailer` enable checkbox không persist qua container restart vì gradio render từ hardcoded `value=False` constructor; fix bằng source edit `InputAccordion(True, ...)` cho cả 2 components, bind-mount `forge/patches/ui.py` + sed edit ADetailer extension. Cả 2 toggle giờ default-enabled mỗi container restart.
- **Civitai MCP integration (2026-05-07)** — Project-scoped MCP server `civitai-mcp-ultimate` (Python/FastMCP, 14 tools) registered via `home-server/.mcp.json` với `${CIVITAI_API_KEY}` env var ref. Key sống trong `.env` (mode 600, gitignored sẵn), loaded bởi `scripts/claude.sh` wrapper trước khi spawn `claude`. New skill `/civitai-model` (project-scoped tại `.claude/skills/civitai-model/`) cho 3 modes: search (search/top-loras/top-checkpoints), download (auto-route LoRA/Checkpoint/Embedding vào correct Forge paths, podman subuid 525287 mapping OK), prompts (mine generation params từ top community images, paste-ready cho `/st-gen-image-prompt --describe`). Free Civitai account đủ — không cần Pro. Wrapper script pattern thay vì global `~/.zshrc` để giữ secret per-project. `pip install --user civitai-mcp-ultimate` → CLI tại `~/.local/bin/civitai-mcp-ultimate`.
- Pending: Homarr widget upgrade for media tiles, optional reverse proxy for LAN access, add indexers in Prowlarr (per-user), Civitai E2E test sau khi user paste API key
