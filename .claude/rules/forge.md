---
paths:
  - "forge/**"
---

# Forge Gotchas — VRAM budget, launch config, model downloads. Auto-loads when working in forge/.

## VRAM Budget (RTX 4070 Ti Super 16GB)
| Combo | Peak | Status |
|-------|------|--------|
| Forge SDXL alone | ~12GB | Safe |
| Jellyfin NVENC alone | ~2GB | Safe |
| Forge + Jellyfin idle | ~12GB | Safe |
| Forge + Jellyfin NVENC active | ~14GB | Tight, warn |
| Forge + Jellyfin 4K HEVC transcode | ~15-16GB | Refuse start |

`vram-guard.sh` enforces: soft warn at 13GB used, hard refuse at 15GB used.

## Gotchas

- **Forge port binding:** `127.0.0.1:7860` (localhost-only). Forge ai-dock image disables auth (`WEB_ENABLE_AUTH=false`); never bind to `0.0.0.0`. Container clients still reach it via `http://home-forge:7860` on `home-net`. If LAN/remote access is needed, add an authenticated reverse proxy in front (Caddy basic-auth, Tailscale Funnel, etc.).
- **Forge forge_args.conf:** controls launch flags, NOT just `WEBUI_FLAGS` env var alone (ai-dock image quirk)
- **Forge ai-dock image stale:** vpred models broken (Zero Terminal SNR ignored); stick with epsilon-prediction checkpoints
- **Forge UI config persistence:** `config.json` + `ui-config.json` ở root webui dir KHÔNG nằm trong bind mount mặc định → ADetailer/sampler/UI defaults reset mỗi restart. Fix: `forge_args.conf` thêm `--ui-settings-file /opt/stable-diffusion-webui-forge/config/config.json --ui-config-file /opt/stable-diffusion-webui-forge/config/ui-config.json` để webui ghi vào mounted `data/forge/config/` thay vì root. Áp dụng 2026-05-06.
- **Forge InputAccordion master toggles:** `Hires. fix` + `ADetailer` enable checkbox không persist qua container restart dù Forge ghi đúng vào ui-config.json (gradio render từ hardcoded `value=False` constructor, setattr post-render không reflect). Fix: source patch — `forge/patches/ui.py` bind-mounted thay `modules/ui.py` (line 329 đổi `InputAccordion(False, ...)` → `True`), + sed edit `data/forge/extensions/adetailer/aaaaaa/ui.py` line 132 `value=False` → `value=True`. Re-patch khi Forge image hoặc ADetailer extension upgrade. 2026-05-07.
- **Forge mem_limit (compose.yml line 29):** Bumped 12g → 16g on 2026-05-08. NoobAI XL checkpoint (~7GB) + 4 LoRAs stack (Parasite + Oviposition + 2 always-on quality) + ADetailer + xformers peak load thi thoảng vượt 12GB → container memcg OOM kill (exit 137), Forge tự restart, ST gen request gặp `unexpected EOF` trả về HTTP 500. Confirmed via `journalctl -k` cho thấy `oom_memcg=...libpod-...home-forge.scope/container` (container cgroup, NOT host). Host có 32GB nên 16g rộng rãi. Nếu sau này stack 5+ LoRA hoặc swap qua FLUX → bump tiếp lên 20g. 2026-05-08.
- **Civitai download MUST use podman unshare:** Forge model dirs (`forge/data/forge/models/Lora`, `Stable-diffusion`, etc.) owned by subuid `525287:525287` (container UID 1000). Plain `curl` từ host user `haint` fail với exit 23 (write error). Wrap downloads trong `podman unshare bash -c "curl ..."` — host user maps namespace root → writes appear as container UID 1000. Bash subprocess KHÔNG inherit env từ Claude Code parent (security isolation), phải `source .env` inline mỗi command. Verified 7-LoRA batch 1.3GB download 14s parallel. 2026-05-07.
