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
- **Civitai MCP project-scoped:** `.mcp.json` ở root references `${CIVITAI_API_KEY}` (committable, no secret). Key sống trong `.env` (gitignored, mode 600). Env auto-loaded khi cd vào project nhờ zsh `chpwd` hook trong `~/.zshrc` — opt-in qua flag `CLAUDE_AUTOLOAD=1` ở dòng đầu `.env`. Hook reusable cho mọi project (chỉ cần thêm flag). Fallback: `./scripts/claude.sh` source `.env` rồi exec — dùng khi shell hook không available. Plain `claude` từ shell chưa load env → /doctor cảnh báo (cosmetic, MCP server vẫn auth được vì Claude Code đọc `.env` riêng cho MCP children). Skill `/civitai-model` (project-scoped tại `.claude/skills/civitai-model/`) dùng MCP để search/download/prompt-mine vào Forge paths. 2026-05-07.
- **Civitai MCP — 5 pending PRs to upstream (2026-05-07):** Local site-packages `~/.local/lib/python3.14/site-packages/civitai_mcp_ultimate/` đang chạy v0.3.0 + 5 patches local đã apply, AHEAD of upstream main. PRs: #1 format_model_card show all versions (formatter bug), #3 get_current_user 401 error message clarify (token type mismatch, not invalid key), #4 add `check_permissions` tool (early-access gate detection), #5 add `lookup_users` tool (ID/username lookup), #6 add `get_model_versions_by_hashes` + `CivitaiClient.post()` (bulk SHA256→version, plus first POST endpoint in client). All atomic — review/merge any order. **Don't `pip install --upgrade`** until PRs merge — sẽ overwrite 5 patches. Fork branch backups tại `haingt-dev/civitai-mcp-ultimate` (4 feature branches + 1 fix branch).
- **Civitai download MUST use podman unshare:** Forge model dirs (`forge/data/forge/models/Lora`, `Stable-diffusion`, etc.) owned by subuid `525287:525287` (container UID 1000). Plain `curl` từ host user `haint` fail với exit 23 (write error). Wrap downloads trong `podman unshare bash -c "curl ..."` — host user maps namespace root → writes appear as container UID 1000. Bash subprocess KHÔNG inherit env từ Claude Code parent (security isolation), phải `source .env` inline mỗi command. Verified 7-LoRA batch 1.3GB download 14s parallel. 2026-05-07.
- **Forge mem_limit (compose.yml line 29):** Bumped 12g → 16g on 2026-05-08. NoobAI XL checkpoint (~7GB) + 4 LoRAs stack (Parasite + Oviposition + 2 always-on quality) + ADetailer + xformers peak load thi thoảng vượt 12GB → container memcg OOM kill (exit 137), Forge tự restart, ST gen request gặp `unexpected EOF` trả về HTTP 500. Confirmed via `journalctl -k` cho thấy `oom_memcg=...libpod-...home-forge.scope/container` (container cgroup, NOT host). Host có 32GB nên 16g rộng rãi. Nếu sau này stack 5+ LoRA hoặc swap qua FLUX → bump tiếp lên 20g. 2026-05-08.
- **ST MCP server (`st`) — local stdio at `~/.local/bin/st-mcp`, source ở `sillytavern/mcp/st-mcp/`** (Python/FastMCP, scaffolded với guidance từ Anthropic `mcp-server-dev:build-mcp-server` plugin skill (plugin kept enabled cho future MCP work — forge/jellyfin/etc.; plugin loading từng có cache bug nên giữ enabled tránh re-debug)). Wraps 8 tools: `st_get_settings(path)`, `st_save_settings_path(path, value)`, `st_save_settings(full)`, `st_list_characters`, `st_get_character`, `st_get_recent_chat`, `st_get_worldinfo`, `st_save_worldinfo`. Registered project-scoped trong `home-server/.mcp.json` cùng civitai. **Auth: CSRF token + cookie session** — `/api/*` POSTs require `X-CSRF-Token` header from `GET /csrf-token`. Client lazy-fetches, retries 1 lần khi 403 (token rotation). Single-user mode + `SECURITYOVERRIDE=true` lets `requireLoginMiddleware` pass without basic auth. **CRITICAL save gotcha**: `/api/settings/save` writes `JSON.stringify(request.body)` directly to disk — body MUST be the bare settings dict, NOT `{"settings": <stringified>}`. Wrapping it nests `settings.settings.<actual>` in the file (corruption!). Fixed in client by sending unwrapped dict. **Token-cap gotcha**: full settings tree = 73KB → exceeds Claude's MCP output limit. ALL skill reads must be path-based (`extension_settings.sd`, `power_user.persona_descriptions`, etc. — each subtree <10KB). `st_save_settings_path` does surgical writes server-side without round-tripping the tree through Claude. Wrapper-level fields (`world_names`, `koboldai_settings`, `openai_settings`, etc.) accessible via the same path namespace via merged read view. **KEY WIN**: eliminates legacy stop-edit-start cycle trong /st-setup, /st-persona, /st-arc-save — `mcp__st__*` routes through ST's save handler (no `saveSettingsDebounced` race), ST hot-reloads automatically. /st-gen-image-prompt + /st-audit cũng đã update path-based. Skills retain direct file ops cho operations không có API equivalent (PNG copy, expression sprite gen, chat .jsonl message body fetch). 2026-05-08. **Dotted-key gotcha + fix (2026-05-24):** `_get_path` / `_set_path` ban đầu dùng naive `path.split(".")` → keys chứa `.` (vd `Naoko (Persona).png` trong `power_user.personas` / `power_user.persona_descriptions`) bị tách sai → tree corruption. Hit thật khi `/st-persona --new` register Naoko Hive Queen. Fix: thêm `_parse_path` hỗ trợ bracket-escape syntax `parent.path.["literal.key"]` (dot trước bracket optional). Backwards-compat với mọi path không có `["`. Skill `/st-persona` Phase 3 đã update dùng `persona_key = f'["{persona_avatar}"]'`. Khi caller cần leaf key chứa `.`, luôn dùng bracket form. Restart Claude Code sau khi sửa server source để MCP stdio reload (editable install).

## Security
**CRITICAL**: NEVER commit, push, or expose secrets, API keys, tokens, or credentials.

- Use `.env` files per section, never hardcode
- Verify `git diff --cached` before commit
- `.gitignore` must cover `.env*`, `*.key`, `*.pem`, `dashboard/data/`, `dashboard/backups/`
- Dashboard backups contain admin password hash + encryption key usage — treat as secrets
- ASK before committing sensitive-looking files
- If secret leaked: STOP, alert user, revoke, remove from history
